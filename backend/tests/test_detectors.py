from app.services.parsers.detectors import detect_source


def test_detect_cloudtrail():
    records = [
        {"eventVersion": "1.08", "eventSource": "s3.amazonaws.com", "eventName": "GetObject"}
    ] * 3
    assert detect_source("json", records) == "cloudtrail"


def test_detect_kubernetes():
    records = [{"kind": "Event", "reason": "BackOff", "involvedObject": {"kind": "Pod"}}] * 3
    assert detect_source("json", records) == "kubernetes"


def test_detect_sysmon_vs_windows():
    sysmon = {
        "System": {"Provider": {"@Name": "Microsoft-Windows-Sysmon"}, "EventID": {"#text": "1"}}
    }
    windows = {
        "System": {"Provider": {"@Name": "Service Control Manager"}, "EventID": {"#text": "7031"}}
    }
    assert detect_source("evtx", [sysmon] * 4) == "sysmon"
    assert detect_source("evtx", [windows] * 4) == "windows_event"


def test_detect_defender():
    record = {
        "System": {
            "Provider": {"@Name": "Microsoft-Windows-Windows Defender"},
            "EventID": {"#text": "1116"},
        }
    }
    assert detect_source("evtx", [record] * 2) == "defender"


def test_detect_azure_alert():
    records = [{"data": {"essentials": {"alertRule": "x", "severity": "Sev2"}}}] * 2
    assert detect_source("json", records) == "azure"


def test_detect_vmware():
    records = [{"eventTypeId": "VmPoweredOffEvent", "fullFormattedMessage": "VM powered off"}] * 2
    assert detect_source("json", records) == "vmware"


def test_detect_syslog_text():
    records = [
        {"line": "Jun  1 03:04:05 web01 sshd[1234]: Accepted publickey for deploy"},
        {"line": "Jun  1 03:04:06 web01 systemd[1]: Started session."},
        {"line": "Jun  1 03:04:07 web01 kernel: eth0 link up"},
    ]
    assert detect_source("text", records) == "syslog"


def test_detect_generic_fallback():
    assert detect_source("json", [{"foo": "bar"}] * 5) == "generic"
    assert detect_source("json", []) == "generic"


def test_mixed_file_prefers_majority():
    records = [{"eventVersion": "1", "eventSource": "ec2.amazonaws.com", "eventName": "X"}] * 6 + [
        {"foo": 1}
    ] * 2
    assert detect_source("json", records) == "cloudtrail"
