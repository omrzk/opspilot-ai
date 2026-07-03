"""Demo fixtures and seeding logic. Parsing/detection is exercised without any
external services; DB-dependent seeding is covered by the integration smoke test."""

import pathlib
import tempfile

from app.services.demo import fixtures
from app.services.demo.seed import DEMO_EMAIL_DOMAIN, is_demo_user
from app.services.parsers.service import parse_file


class _FakeUser:
    def __init__(self, email: str):
        self.email = email


def test_demo_files_parse_to_expected_sources():
    expected = {
        "web-prod-01_auth.log": "syslog",
        "k8s-shop-events.json": "kubernetes",
        "cloudtrail-us-east-1.json": "cloudtrail",
        "FIN-WKS-24_sysmon.xml": "sysmon",
    }
    seen = {}
    for spec in fixtures.demo_files():
        suffix = pathlib.Path(spec.filename).suffix
        path = pathlib.Path(tempfile.mktemp(suffix=suffix))
        path.write_text(spec.content, encoding="utf-8")
        result = parse_file(path, spec.filename)
        seen[spec.filename] = result.source_type
        assert len(result.events) > 0
    assert seen == expected


def test_ssh_log_shows_bruteforce_then_success():
    spec = next(f for f in fixtures.demo_files() if f.filename == "web-prod-01_auth.log")
    path = pathlib.Path(tempfile.mktemp(suffix=".log"))
    path.write_text(spec.content, encoding="utf-8")
    events = parse_file(path, spec.filename).events
    failures = [e for e in events if "Failed password" in e.message]
    successes = [e for e in events if "Accepted password" in e.message]
    assert len(failures) >= 50
    assert len(successes) == 1
    assert any(e.severity == "error" for e in failures)


def test_seeded_analysis_is_wellformed():
    spec = next(f for f in fixtures.demo_files() if f.analysis)
    a = spec.analysis
    assert a["severity"] == "critical"
    assert 0.0 <= a["confidence"] <= 1.0
    assert a["affected_systems"] and all("name" in s for s in a["affected_systems"])
    assert a["remediation"] and all("action" in r for r in a["remediation"])
    assert a["scripts"]["bash"].startswith("#!/usr/bin/env bash")
    # Only relevant script types are populated
    assert a["scripts"]["powershell"] == ""
    assert a["scripts"]["terraform"] == ""


def test_demo_docs_present():
    docs = fixtures.demo_docs()
    assert len(docs) >= 3
    assert any(d.doc_type == "runbook" for d in docs)
    assert all(d.text.strip() for d in docs)


def test_demo_conversation_has_welcome():
    convo = fixtures.demo_conversation()
    assert convo.messages[0][0] == "user"
    assert convo.messages[1][0] == "assistant"
    assert "demo" in convo.messages[1][1].lower()


def test_is_demo_user():
    assert is_demo_user(_FakeUser(f"demo-abc123@{DEMO_EMAIL_DOMAIN}"))
    assert not is_demo_user(_FakeUser("real.user@company.com"))
