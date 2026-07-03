import uuid
from datetime import UTC, datetime, timedelta

from app.models.upload import LogEvent
from app.services.analysis.sampler import build_digest, render_digest


def _event(severity: str, minutes: int, message: str = "msg", event_id: str = "1") -> LogEvent:
    return LogEvent(
        id=uuid.uuid4(),
        upload_id=uuid.uuid4(),
        timestamp=datetime(2026, 6, 1, tzinfo=UTC) + timedelta(minutes=minutes),
        source="syslog",
        host="web01",
        severity=severity,
        event_id=event_id,
        message=message,
        raw={},
    )


def test_digest_stats_and_priority():
    events = (
        [_event("info", i, f"info {i}", "10") for i in range(50)]
        + [_event("critical", 60, "kernel panic", "99")]
        + [_event("error", 55, "disk failure", "42")]
    )
    digest = build_digest(events)
    assert digest.total == 52
    assert digest.severity_counts["critical"] == 1
    sampled_messages = [e.message for e in digest.sampled]
    assert "kernel panic" in sampled_messages
    assert "disk failure" in sampled_messages


def test_duplicate_signatures_collapsed():
    events = [_event("error", i, "same failure message", "7") for i in range(100)]
    digest = build_digest(events)
    assert len(digest.sampled) <= 3  # MAX_PER_SIGNATURE


def test_render_digest_contains_sections():
    events = [_event("warning", 0, "cert expiring", "77")]
    text = render_digest(build_digest(events), "syslog")
    assert "Log source: syslog" in text
    assert "SAMPLED EVENTS" in text
    assert "cert expiring" in text
    assert "WARNING" in text


def test_events_without_timestamps():
    event = LogEvent(
        id=uuid.uuid4(), upload_id=uuid.uuid4(), timestamp=None, source="generic",
        host="", severity="error", event_id="", message="no ts", raw={},
    )
    digest = build_digest([event])
    assert "unknown" in digest.time_range
    assert digest.sampled[0].message == "no ts"
