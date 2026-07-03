from app.services.analysis.engine import _coerce_result


def test_full_valid_payload():
    parsed = {
        "summary": "Disk filled up",
        "root_cause": "Log rotation disabled",
        "severity": "high",
        "confidence": 0.87,
        "affected_systems": [{"name": "web01", "role": "web server", "evidence": "df 100%"}],
        "remediation": [{"step": 1, "action": "Enable logrotate", "rationale": "prevent refill"}],
        "scripts": {"bash": "#!/bin/bash\nlogrotate -f /etc/logrotate.conf", "powershell": ""},
        "evidence": ["disk full at 12:00"],
        "alternative_hypotheses": ["runaway process"],
    }
    result = _coerce_result(parsed)
    assert result["severity"] == "high"
    assert result["confidence"] == 0.87
    assert result["affected_systems"][0]["name"] == "web01"
    assert result["scripts"]["bash"].startswith("#!/bin/bash")
    assert result["scripts"]["terraform"] == ""
    assert any("Alternative hypothesis" in e for e in result["evidence"])


def test_garbage_is_neutralized():
    parsed = {
        "summary": 123,
        "severity": "catastrophic",
        "confidence": "very high",
        "affected_systems": "web01",
        "remediation": [{"no_action": True}, {"action": "do the thing"}],
        "scripts": {"bash": ["not", "a", "string"], "powershell": "Get-Process"},
        "evidence": "not a list",
    }
    result = _coerce_result(parsed)
    assert result["severity"] == "medium"
    assert result["confidence"] == 0.0
    assert result["affected_systems"] == []
    assert len(result["remediation"]) == 1
    assert result["scripts"]["bash"] == ""
    assert result["scripts"]["powershell"] == "Get-Process"
    assert result["evidence"] == []


def test_confidence_clamped():
    assert _coerce_result({"confidence": 1.7})["confidence"] == 1.0
    assert _coerce_result({"confidence": -3})["confidence"] == 0.0
