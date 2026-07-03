"""Normalizers for syslog / plain-text lines and generic structured records."""

import re

from app.services.parsers.base import ParsedEvent
from app.services.parsers.normalizers.common import (
    first_str,
    parse_timestamp,
    severity_from_text,
)

# RFC3164: "Jan  2 03:04:05 hostname process[pid]: message"
SYSLOG_RE = re.compile(
    r"^(?:<\d+>)?"
    r"(?P<ts>[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"(?P<host>\S+)\s+"
    r"(?P<proc>[\w./-]+)(?:\[(?P<pid>\d+)\])?:\s*"
    r"(?P<msg>.*)$"
)
# RFC5424: "<pri>1 2026-01-02T03:04:05Z host app pid msgid - message"
SYSLOG_5424_RE = re.compile(
    r"^<\d+>\d\s+(?P<ts>\S+)\s+(?P<host>\S+)\s+(?P<app>\S+)\s+\S+\s+\S+\s+(?:\[.*?\]|-)\s*"
    r"(?P<msg>.*)$"
)
# Generic app log: "2026-01-02T03:04:05... LEVEL message" / "2026-01-02 03:04:05 [LEVEL] ..."
APP_LOG_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}[\w.:+-]*)\s+"
    r"[\[(]?(?P<level>[A-Za-z]+)[\])]?[: ]\s*(?P<msg>.*)$"
)

_LEVEL_WORDS = {
    "fatal": "critical", "critical": "critical", "crit": "critical", "emerg": "critical",
    "alert": "critical", "error": "error", "err": "error", "warning": "warning",
    "warn": "warning", "notice": "info", "info": "info", "debug": "debug", "trace": "debug",
}


def looks_like_syslog(line: str) -> bool:
    return bool(SYSLOG_RE.match(line) or SYSLOG_5424_RE.match(line))


def normalize_syslog_line(record: dict) -> ParsedEvent:
    line = record.get("line", "")
    m = SYSLOG_RE.match(line) or SYSLOG_5424_RE.match(line)
    if not m:
        return normalize_text_line(record)
    groups = m.groupdict()
    proc = groups.get("proc") or groups.get("app") or ""
    message = groups.get("msg", "")
    return ParsedEvent(
        timestamp=parse_timestamp(groups.get("ts")),
        source="syslog",
        host=groups.get("host", ""),
        severity=severity_from_text(message),
        event_id=proc,
        message=f"{proc}: {message}"[:4000] if proc else message[:4000],
        raw={"line": line},
    )


def normalize_text_line(record: dict) -> ParsedEvent:
    line = record.get("line", "")
    m = APP_LOG_RE.match(line)
    if m:
        level = _LEVEL_WORDS.get(m.group("level").lower())
        return ParsedEvent(
            timestamp=parse_timestamp(m.group("ts")),
            source="generic",
            severity=level or severity_from_text(m.group("msg")),
            message=m.group("msg")[:4000],
            raw={"line": line},
        )
    return ParsedEvent(
        source="generic",
        severity=severity_from_text(line),
        message=line[:4000],
        raw={"line": line},
    )


def normalize_generic(record: dict) -> ParsedEvent:
    """Best-effort normalization of arbitrary structured records (JSON/CSV/XML)."""
    if set(record.keys()) == {"line"}:
        return normalize_text_line(record)
    timestamp = parse_timestamp(
        first_str(
            record, "timestamp", "@timestamp", "time", "eventTime", "date", "datetime",
            "created_at", "TimeGenerated",
        )
        or record.get("timestamp")
        or record.get("time")
    )
    message = first_str(
        record, "message", "msg", "description", "summary", "text", "detail", "error", "line"
    )
    if not message:
        # Render the record compactly so nothing is lost
        pairs = [f"{k}={v}" for k, v in record.items() if isinstance(v, (str, int, float)) and v]
        message = "; ".join(pairs[:12])
    level = first_str(record, "severity", "level", "loglevel", "priority").lower()
    severity = _LEVEL_WORDS.get(level) or severity_from_text(message)
    return ParsedEvent(
        timestamp=timestamp,
        source="generic",
        host=first_str(record, "host", "hostname", "computer", "machine", "node", "instance"),
        severity=severity,
        event_id=first_str(record, "event_id", "eventid", "id", "code", "event"),
        message=message[:4000],
        raw=record,
    )
