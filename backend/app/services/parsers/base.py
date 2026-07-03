"""Shared parsing types."""

from dataclasses import dataclass, field
from datetime import datetime

# Log sources OpsPilot understands natively. "generic" is the fallback.
SOURCE_TYPES = (
    "windows_event",
    "sysmon",
    "defender",
    "azure",
    "vmware",
    "cloudtrail",
    "kubernetes",
    "syslog",
    "generic",
)


@dataclass
class ParsedEvent:
    """A single normalized event, regardless of origin."""

    timestamp: datetime | None = None
    source: str = "generic"
    host: str = ""
    severity: str = "info"  # critical | error | warning | info | debug
    event_id: str = ""
    message: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class ParseResult:
    source_type: str
    events: list[ParsedEvent]
    warnings: list[str] = field(default_factory=list)
