"""Helpers shared by all normalizers."""

import re
from datetime import UTC, datetime

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}")
# RFC3164: "Jan  2 03:04:05"
_SYSLOG_TS_RE = re.compile(r"^([A-Z][a-z]{2})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})")
_MONTHS = {
    m: i + 1
    for i, m in enumerate(
        ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    )
}

SEVERITY_KEYWORDS = (
    ("critical", ("critical", "crit", "fatal", "emerg", "panic", "alert")),
    ("error", ("error", "err", "fail", "failed", "failure", "denied", "refused", "exception")),
    ("warning", ("warning", "warn", "deprecat", "timeout", "retry", "throttl")),
    ("debug", ("debug", "trace", "verbose")),
)


def parse_timestamp(value) -> datetime | None:
    """Parse a timestamp from ISO strings, epoch numbers, or syslog format."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        # Heuristic: epoch milliseconds vs seconds
        ts = float(value)
        if ts > 1e12:
            ts /= 1000.0
        try:
            return datetime.fromtimestamp(ts, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    # ISO 8601 (with or without Z / offset / fractional seconds)
    if _ISO_RE.match(value):
        cleaned = value.replace("Z", "+00:00").replace(" ", "T", 1)
        # Trim sub-microsecond precision (Windows emits 7 digits)
        cleaned = re.sub(r"(\.\d{6})\d+", r"\1", cleaned)
        try:
            dt = datetime.fromisoformat(cleaned)
            return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
        except ValueError:
            pass
    # Syslog RFC3164 (no year: assume current year)
    m = _SYSLOG_TS_RE.match(value)
    if m:
        month = _MONTHS.get(m.group(1))
        if month:
            now = datetime.now(UTC)
            try:
                return datetime(
                    now.year, month, int(m.group(2)),
                    int(m.group(3)), int(m.group(4)), int(m.group(5)), tzinfo=UTC,
                )
            except ValueError:
                return None
    # Epoch encoded as string
    if re.fullmatch(r"\d{10}(\.\d+)?|\d{13}", value):
        return parse_timestamp(float(value))
    return None


def severity_from_text(text: str, default: str = "info") -> str:
    lowered = text.lower()
    for severity, keywords in SEVERITY_KEYWORDS:
        if any(k in lowered for k in keywords):
            return severity
    return default


def first_str(record: dict, *keys: str) -> str:
    """Return the first non-empty string value among keys (case-insensitive)."""
    lowered = {k.lower(): v for k, v in record.items()}
    for key in keys:
        value = lowered.get(key.lower())
        if isinstance(value, str) and value.strip():
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
    return ""
