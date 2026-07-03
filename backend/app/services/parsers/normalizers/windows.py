"""Normalizers for Windows Event Log records (EVTX/XML shape), including
Sysmon and Microsoft Defender events."""

from app.services.parsers.base import ParsedEvent
from app.services.parsers.normalizers.common import parse_timestamp

# Windows event Level -> severity
LEVEL_MAP = {"1": "critical", "2": "error", "3": "warning", "4": "info", "5": "debug", "0": "info"}

SYSMON_EVENTS = {
    "1": "Process creation",
    "2": "File creation time changed",
    "3": "Network connection",
    "4": "Sysmon service state changed",
    "5": "Process terminated",
    "6": "Driver loaded",
    "7": "Image loaded",
    "8": "CreateRemoteThread",
    "9": "RawAccessRead",
    "10": "ProcessAccess",
    "11": "File created",
    "12": "Registry object added or deleted",
    "13": "Registry value set",
    "14": "Registry key or value renamed",
    "15": "FileCreateStreamHash",
    "17": "Pipe created",
    "18": "Pipe connected",
    "19": "WmiEventFilter activity",
    "20": "WmiEventConsumer activity",
    "21": "WmiEventConsumerToFilter activity",
    "22": "DNS query",
    "23": "File delete (archived)",
    "24": "Clipboard change",
    "25": "Process tampering",
    "26": "File delete (logged)",
    "27": "File block (executable)",
    "28": "File block (shredding)",
    "29": "File executable detected",
}

DEFENDER_EVENTS = {
    "1006": "Malware or unwanted software detected",
    "1007": "Action performed to protect the system",
    "1008": "Action failed",
    "1009": "Item restored from quarantine",
    "1015": "Suspicious behavior detected",
    "1116": "Threat detected",
    "1117": "Protection action taken",
    "1118": "Protection action failed (non-critical)",
    "1119": "Protection action failed (critical)",
    "1121": "ASR rule blocked an action",
    "1122": "ASR rule audited an action",
    "2000": "Definitions updated",
    "2001": "Definitions update failed",
    "5001": "Real-time protection disabled",
    "5007": "Platform configuration changed",
    "5010": "Antimalware scanning disabled",
    "5012": "Antivirus scanning disabled",
}

# EventData fields most useful as evidence, in display priority
_INTERESTING_FIELDS = (
    "Image", "CommandLine", "ParentImage", "ParentCommandLine", "User", "TargetFilename",
    "DestinationIp", "DestinationPort", "DestinationHostname", "SourceIp", "QueryName",
    "QueryResults", "TargetObject", "Details", "ImageLoaded", "Signature", "SignatureStatus",
    "ThreatName", "Threat Name", "Path", "Process Name", "Severity Name", "Category Name",
    "TargetUserName", "IpAddress", "WorkstationName", "LogonType", "Status", "FailureReason",
    "ServiceName", "ServiceFileName", "AccountName", "SubjectUserName",
)


def _system_field(system: dict, key: str):
    value = system.get(key)
    if isinstance(value, dict):
        return value
    return value


def _text_of(value) -> str:
    if isinstance(value, dict):
        return str(value.get("#text", "")).strip()
    if value is None:
        return ""
    return str(value).strip()


def extract_event_data(record: dict) -> dict:
    """Flatten <EventData><Data Name="X">v</Data>...</EventData> into a dict."""
    event_data = record.get("EventData") or record.get("UserData") or {}
    result: dict = {}
    if not isinstance(event_data, dict):
        return result
    data = event_data.get("Data")
    if data is None:
        # UserData nests arbitrary elements; keep one flat level of text values
        for value in event_data.values():
            if isinstance(value, dict):
                for k2, v2 in value.items():
                    text = _text_of(v2)
                    if text:
                        result[k2.lstrip("@")] = text
        return result
    entries = data if isinstance(data, list) else [data]
    unnamed = 0
    for entry in entries:
        if isinstance(entry, dict):
            name = entry.get("@Name")
            text = _text_of(entry)
            if name:
                result[name] = text
            elif text:
                result[f"Data{unnamed}"] = text
                unnamed += 1
        elif isinstance(entry, str) and entry.strip():
            result[f"Data{unnamed}"] = entry.strip()
            unnamed += 1
    return result


def windows_provider(record: dict) -> str:
    system = record.get("System") or {}
    provider = system.get("Provider")
    if isinstance(provider, dict):
        return str(provider.get("@Name", ""))
    return ""


def windows_channel(record: dict) -> str:
    system = record.get("System") or {}
    return _text_of(system.get("Channel"))


def normalize_windows_event(record: dict, source: str = "windows_event") -> ParsedEvent:
    system = record.get("System") or {}
    event_id = _text_of(system.get("EventID"))
    level = _text_of(system.get("Level")) or "4"
    time_created = system.get("TimeCreated")
    timestamp = None
    if isinstance(time_created, dict):
        timestamp = parse_timestamp(time_created.get("@SystemTime"))
    host = _text_of(system.get("Computer"))
    provider = windows_provider(record)
    data = extract_event_data(record)

    title = ""
    if source == "sysmon":
        title = SYSMON_EVENTS.get(event_id, "")
    elif source == "defender":
        title = DEFENDER_EVENTS.get(event_id, "")

    parts = []
    if title:
        parts.append(title)
    elif provider:
        parts.append(f"{provider} event {event_id}")
    highlights = [f"{k}={data[k]}" for k in _INTERESTING_FIELDS if data.get(k)]
    if highlights:
        parts.append("; ".join(highlights[:8]))
    message = " | ".join(parts) if parts else f"Event {event_id}"

    severity = LEVEL_MAP.get(level, "info")
    # Defender threat / protection-failure events are high-signal regardless of Level
    critical_defender = ("1119", "5001", "5010", "5012")
    if source == "defender" and event_id in critical_defender + ("1116", "1117", "1118"):
        severity = "critical" if event_id in critical_defender else "error"

    return ParsedEvent(
        timestamp=timestamp,
        source=source,
        host=host,
        severity=severity,
        event_id=event_id,
        message=message[:4000],
        raw={"System": system, "EventData": data},
    )
