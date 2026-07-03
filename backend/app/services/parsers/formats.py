"""File-format readers: turn EVTX/JSON/CSV/XML/TXT files into raw record dicts.

Format readers know nothing about log semantics — they only produce dicts.
Source detection and normalization happen in detectors.py / normalizers/."""

import csv
import io
import json
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_RECORDS = 50_000  # hard cap to protect memory on huge files
MAX_TEXT_LINES = 100_000


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def xml_element_to_dict(element: ET.Element) -> dict:
    """Convert an XML element tree into nested dicts (attributes prefixed with @)."""
    node: dict = {}
    for key, value in element.attrib.items():
        node[f"@{_strip_ns(key)}"] = value
    children = list(element)
    if children:
        for child in children:
            child_dict = xml_element_to_dict(child)
            tag = _strip_ns(child.tag)
            if tag in node:
                existing = node[tag]
                if not isinstance(existing, list):
                    node[tag] = [existing]
                node[tag].append(child_dict)
            else:
                node[tag] = child_dict
    text = (element.text or "").strip()
    if text:
        if node:
            node["#text"] = text
        else:
            return {"#text": text} if element.attrib else {"#text": text, **node}
    return node


def read_evtx(path: Path) -> list[dict]:
    """Read a Windows EVTX file into per-record dicts via python-evtx."""
    import Evtx.Evtx as evtx  # imported lazily: heavy, and only needed for .evtx

    records: list[dict] = []
    with evtx.Evtx(str(path)) as log:
        for record in log.records():
            try:
                root = ET.fromstring(record.xml())
            except ET.ParseError:
                continue
            records.append(xml_element_to_dict(root))
            if len(records) >= MAX_RECORDS:
                break
    return records


def read_json(path: Path) -> list[dict]:
    """Read a JSON file: single object, array, or NDJSON (one object per line)."""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # NDJSON fallback
        records = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                records.append(obj)
            if len(records) >= MAX_RECORDS:
                break
        return records
    if isinstance(data, list):
        return [r for r in data[:MAX_RECORDS] if isinstance(r, dict)]
    if isinstance(data, dict):
        # Common envelope shapes: CloudTrail {"Records": [...]}, K8s list {"items": [...]}
        for key in ("Records", "records", "items", "events", "value"):
            inner = data.get(key)
            if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                return inner[:MAX_RECORDS]
        return [data]
    return []


def read_csv(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8", errors="replace")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    records = []
    for row in reader:
        records.append({(k or "").strip(): (v or "") for k, v in row.items()})
        if len(records) >= MAX_RECORDS:
            break
    return records


def read_xml(path: Path) -> list[dict]:
    """Read an XML file. If the root has repeated children, treat each as a record."""
    try:
        root = ET.fromstring(path.read_text(encoding="utf-8", errors="replace"))
    except ET.ParseError:
        return []
    children = list(root)
    if len(children) > 1:
        tags = {_strip_ns(c.tag) for c in children}
        if len(tags) == 1:  # homogeneous list of records
            return [xml_element_to_dict(c) for c in children[:MAX_RECORDS]]
    return [xml_element_to_dict(root)]


def read_text(path: Path) -> list[dict]:
    """Read a plain-text log: one record per non-empty line."""
    records = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            if i >= MAX_TEXT_LINES:
                break
            line = line.rstrip("\n")
            if line.strip():
                records.append({"line": line})
    return records


def read_file(path: Path, filename: str) -> tuple[str, list[dict]]:
    """Dispatch on extension (with content sniffing for missing/wrong extensions).

    Returns (format, records)."""
    ext = Path(filename).suffix.lower()
    if ext == ".evtx":
        return "evtx", read_evtx(path)
    if ext in (".json", ".ndjson", ".jsonl"):
        return "json", read_json(path)
    if ext in (".csv", ".tsv"):
        return "csv", read_csv(path)
    if ext == ".xml":
        return "xml", read_xml(path)
    if ext in (".txt", ".log", ""):
        # Sniff: EVTX magic, JSON, XML — users rename files all the time.
        head = path.open("rb").read(512)
        if head.startswith(b"ElfFile"):
            return "evtx", read_evtx(path)
        stripped = head.lstrip()
        if stripped.startswith((b"{", b"[")):
            records = read_json(path)
            if records:
                return "json", records
        if stripped.startswith(b"<"):
            records = read_xml(path)
            if records:
                return "xml", records
        return "text", read_text(path)
    raise ValueError(f"Unsupported file type: {ext or 'no extension'}")
