"""Evidence sampling: reduce thousands of events to a high-signal digest that
fits in an LLM context window without losing the shape of the incident."""

from collections import Counter
from dataclasses import dataclass, field

from app.models.upload import LogEvent

SEVERITY_ORDER = {"critical": 0, "error": 1, "warning": 2, "info": 3, "debug": 4}
MAX_SAMPLE_EVENTS = 120
MAX_SAMPLE_CHARS = 24_000
MAX_PER_SIGNATURE = 3  # cap duplicates of the same (event_id, message-prefix)


@dataclass
class EventDigest:
    total: int
    time_range: str
    severity_counts: dict[str, int]
    top_hosts: list[tuple[str, int]]
    top_event_ids: list[tuple[str, int]]
    sampled: list[LogEvent] = field(default_factory=list)


def _signature(event: LogEvent) -> tuple[str, str]:
    return (event.event_id, event.message[:80])


def build_digest(events: list[LogEvent]) -> EventDigest:
    severity_counts = Counter(e.severity for e in events)
    host_counts = Counter(e.host for e in events if e.host)
    event_id_counts = Counter(e.event_id for e in events if e.event_id)

    timestamps = sorted(e.timestamp for e in events if e.timestamp)
    if timestamps:
        time_range = f"{timestamps[0].isoformat()} to {timestamps[-1].isoformat()}"
    else:
        time_range = "unknown (no parseable timestamps)"

    # Highest severity first, then chronological within severity
    ranked = sorted(
        events,
        key=lambda e: (
            SEVERITY_ORDER.get(e.severity, 5),
            e.timestamp.timestamp() if e.timestamp else 0,
        ),
    )
    sampled: list[LogEvent] = []
    seen: Counter = Counter()
    used_chars = 0
    for event in ranked:
        sig = _signature(event)
        if seen[sig] >= MAX_PER_SIGNATURE:
            continue
        cost = len(event.message) + 60
        if used_chars + cost > MAX_SAMPLE_CHARS or len(sampled) >= MAX_SAMPLE_EVENTS:
            break
        seen[sig] += 1
        sampled.append(event)
        used_chars += cost
    # Present evidence chronologically
    sampled.sort(key=lambda e: e.timestamp.timestamp() if e.timestamp else 0)

    return EventDigest(
        total=len(events),
        time_range=time_range,
        severity_counts=dict(severity_counts),
        top_hosts=host_counts.most_common(10),
        top_event_ids=event_id_counts.most_common(15),
        sampled=sampled,
    )


def render_digest(digest: EventDigest, source_type: str) -> str:
    lines = [
        f"Log source: {source_type}",
        f"Total events: {digest.total}",
        f"Time range: {digest.time_range}",
        f"Severity distribution: {digest.severity_counts}",
    ]
    if digest.top_hosts:
        lines.append("Top hosts/scopes: " + ", ".join(f"{h} ({n})" for h, n in digest.top_hosts))
    if digest.top_event_ids:
        lines.append(
            "Top event IDs/reasons: " + ", ".join(f"{e} ({n})" for e, n in digest.top_event_ids)
        )
    lines.append("")
    lines.append(f"=== SAMPLED EVENTS ({len(digest.sampled)} of {digest.total}, "
                 "highest severity first, duplicates collapsed) ===")
    for event in digest.sampled:
        ts = event.timestamp.isoformat() if event.timestamp else "no-timestamp"
        host = f" host={event.host}" if event.host else ""
        eid = f" id={event.event_id}" if event.event_id else ""
        lines.append(f"[{ts}] {event.severity.upper()}{host}{eid} :: {event.message}")
    return "\n".join(lines)
