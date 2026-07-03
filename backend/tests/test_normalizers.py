from datetime import UTC, datetime

from app.services.parsers.normalizers.cloud import (
    normalize_azure,
    normalize_cloudtrail,
    normalize_kubernetes,
    normalize_vmware,
)
from app.services.parsers.normalizers.common import parse_timestamp, severity_from_text
from app.services.parsers.normalizers.text import (
    looks_like_syslog,
    normalize_generic,
    normalize_syslog_line,
)
from app.services.parsers.normalizers.windows import normalize_windows_event

WINDOWS_RECORD = {
    "System": {
        "Provider": {"@Name": "Microsoft-Windows-Security-Auditing"},
        "EventID": {"#text": "4625"},
        "Level": {"#text": "0"},
        "TimeCreated": {"@SystemTime": "2026-06-01T10:15:30.1234567Z"},
        "Computer": {"#text": "DC01.corp.local"},
        "Channel": {"#text": "Security"},
    },
    "EventData": {
        "Data": [
            {"@Name": "TargetUserName", "#text": "administrator"},
            {"@Name": "IpAddress", "#text": "10.0.0.55"},
            {"@Name": "LogonType", "#text": "3"},
        ]
    },
}

SYSMON_RECORD = {
    "System": {
        "Provider": {"@Name": "Microsoft-Windows-Sysmon"},
        "EventID": {"#text": "1"},
        "Level": {"#text": "4"},
        "TimeCreated": {"@SystemTime": "2026-06-01T10:00:00Z"},
        "Computer": {"#text": "WS-042"},
        "Channel": {"#text": "Microsoft-Windows-Sysmon/Operational"},
    },
    "EventData": {
        "Data": [
            {"@Name": "Image", "#text": "C:\\Windows\\Temp\\payload.exe"},
            {"@Name": "CommandLine", "#text": "payload.exe -enc AAAA"},
            {"@Name": "ParentImage", "#text": "C:\\Windows\\System32\\cmd.exe"},
        ]
    },
}


def test_windows_event():
    event = normalize_windows_event(WINDOWS_RECORD, "windows_event")
    assert event.event_id == "4625"
    assert event.host == "DC01.corp.local"
    assert event.timestamp == datetime(2026, 6, 1, 10, 15, 30, 123456, tzinfo=UTC)
    assert "TargetUserName=administrator" in event.message
    assert "IpAddress=10.0.0.55" in event.message


def test_sysmon_event_named():
    event = normalize_windows_event(SYSMON_RECORD, "sysmon")
    assert event.source == "sysmon"
    assert event.message.startswith("Process creation")
    assert "payload.exe" in event.message


def test_defender_threat_severity():
    record = {
        "System": {
            "Provider": {"@Name": "Microsoft-Windows-Windows Defender"},
            "EventID": {"#text": "1116"},
            "Level": {"#text": "3"},
            "TimeCreated": {"@SystemTime": "2026-06-01T09:00:00Z"},
            "Computer": {"#text": "WS-042"},
        },
        "EventData": {"Data": [{"@Name": "Threat Name", "#text": "Trojan:Win32/Emotet"}]},
    }
    event = normalize_windows_event(record, "defender")
    assert event.severity == "error"
    assert "Threat detected" in event.message


def test_cloudtrail_error():
    record = {
        "eventVersion": "1.08",
        "eventTime": "2026-06-01T12:00:00Z",
        "eventSource": "iam.amazonaws.com",
        "eventName": "DeleteUser",
        "awsRegion": "us-east-1",
        "sourceIPAddress": "203.0.113.10",
        "userIdentity": {"arn": "arn:aws:iam::123456789012:user/eve"},
        "errorCode": "AccessDenied",
        "errorMessage": "User is not authorized",
    }
    event = normalize_cloudtrail(record)
    assert event.source == "cloudtrail"
    assert event.severity == "warning"  # AccessDenied treated as policy signal
    assert "DeleteUser" in event.message
    assert "203.0.113.10" in event.message


def test_kubernetes_warning():
    record = {
        "kind": "Event",
        "type": "Warning",
        "reason": "BackOff",
        "message": "Back-off restarting failed container",
        "involvedObject": {"kind": "Pod", "name": "api-7f9", "namespace": "prod"},
        "lastTimestamp": "2026-06-01T12:30:00Z",
        "count": 17,
    }
    event = normalize_kubernetes(record)
    assert event.severity == "error"
    assert "Pod/api-7f9" in event.message
    assert "(x17)" in event.message
    assert event.host == "prod"


def test_azure_alert_schema():
    record = {
        "data": {
            "essentials": {
                "alertRule": "CPU above 95%",
                "severity": "Sev1",
                "monitorCondition": "Fired",
                "firedDateTime": "2026-06-01T08:00:00Z",
                "alertTargetIDs": ["/subscriptions/x/resourceGroups/rg/vms/web-01"],
                "description": "Sustained CPU pressure",
            }
        }
    }
    event = normalize_azure(record)
    assert event.severity == "error"
    assert event.host == "web-01"
    assert "CPU above 95%" in event.message


def test_azure_activity_log():
    record = {
        "operationName": {"value": "Microsoft.Compute/virtualMachines/deallocate/action"},
        "level": "Warning",
        "resourceId": "/subscriptions/x/rg/providers/vm/web-02",
        "status": {"value": "Succeeded"},
        "caller": "eve@contoso.com",
        "eventTimestamp": "2026-06-01T07:00:00Z",
    }
    event = normalize_azure(record)
    assert event.source == "azure"
    assert event.host == "web-02"
    assert "eve@contoso.com" in event.message


def test_vmware_alarm():
    record = {
        "eventTypeId": "AlarmStatusChangedEvent",
        "fullFormattedMessage": "Alarm 'Datastore usage' changed from Yellow to Red",
        "createdTime": "2026-06-01T06:00:00Z",
        "host": {"name": "esxi-03.lab.local"},
        "to": "red",
        "alarm": {"name": "Datastore usage on disk"},
    }
    event = normalize_vmware(record)
    assert event.severity == "critical"
    assert event.host == "esxi-03.lab.local"


def test_syslog_line():
    line = "Jun  1 03:04:05 web01 sshd[1234]: Failed password for root from 198.51.100.7 port 22"
    assert looks_like_syslog(line)
    event = normalize_syslog_line({"line": line})
    assert event.source == "syslog"
    assert event.host == "web01"
    assert event.event_id == "sshd"
    assert event.severity == "error"


def test_generic_structured():
    record = {
        "timestamp": "2026-06-01T05:00:00Z",
        "level": "ERROR",
        "hostname": "app-3",
        "message": "connection pool exhausted",
    }
    event = normalize_generic(record)
    assert event.severity == "error"
    assert event.host == "app-3"
    assert event.message == "connection pool exhausted"


def test_parse_timestamp_variants():
    assert parse_timestamp("2026-06-01T10:00:00Z") is not None
    assert parse_timestamp("2026-06-01 10:00:00") is not None
    assert parse_timestamp(1750000000) is not None
    assert parse_timestamp(1750000000000) is not None  # milliseconds
    assert parse_timestamp("1750000000") is not None
    assert parse_timestamp("not a date") is None
    assert parse_timestamp(None) is None


def test_severity_keywords():
    assert severity_from_text("FATAL: out of memory") == "critical"
    assert severity_from_text("request failed with 500") == "error"
    assert severity_from_text("retrying connection") == "warning"
    assert severity_from_text("user logged in") == "info"
