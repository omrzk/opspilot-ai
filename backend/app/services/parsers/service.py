"""Parsing orchestrator: file -> format reader -> source detection -> normalization."""

import logging
from collections.abc import Callable
from pathlib import Path

from app.services.parsers.base import ParsedEvent, ParseResult
from app.services.parsers.detectors import detect_source
from app.services.parsers.formats import read_file
from app.services.parsers.normalizers.cloud import (
    normalize_azure,
    normalize_cloudtrail,
    normalize_kubernetes,
    normalize_vmware,
)
from app.services.parsers.normalizers.text import (
    normalize_generic,
    normalize_syslog_line,
)
from app.services.parsers.normalizers.windows import normalize_windows_event

logger = logging.getLogger(__name__)

_NORMALIZERS: dict[str, Callable[[dict], ParsedEvent]] = {
    "windows_event": lambda r: normalize_windows_event(r, "windows_event"),
    "sysmon": lambda r: normalize_windows_event(r, "sysmon"),
    "defender": lambda r: normalize_windows_event(r, "defender"),
    "cloudtrail": normalize_cloudtrail,
    "kubernetes": normalize_kubernetes,
    "azure": normalize_azure,
    "vmware": normalize_vmware,
    "syslog": normalize_syslog_line,
    "generic": normalize_generic,
}


def parse_file(path: Path, filename: str) -> ParseResult:
    """Parse any supported upload into normalized events."""
    fmt, records = read_file(path, filename)
    source_type = detect_source(fmt, records)
    normalize = _NORMALIZERS[source_type]

    events: list[ParsedEvent] = []
    warnings: list[str] = []
    failures = 0
    for record in records:
        try:
            events.append(normalize(record))
        except Exception:
            failures += 1
            if failures <= 3:
                logger.exception("Failed to normalize record from %s", filename)
    if failures:
        warnings.append(f"{failures} of {len(records)} records could not be normalized")

    logger.info(
        "Parsed %s: format=%s source=%s events=%d warnings=%d",
        filename, fmt, source_type, len(events), len(warnings),
    )
    return ParseResult(source_type=source_type, events=events, warnings=warnings)
