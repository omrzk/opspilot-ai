"""Normalizers for AWS CloudTrail, Azure (activity logs + alerts), Kubernetes
events, and VMware (vCenter events/alarms)."""

from app.services.parsers.base import ParsedEvent
from app.services.parsers.normalizers.common import first_str, parse_timestamp, severity_from_text


def normalize_cloudtrail(record: dict) -> ParsedEvent:
    user_identity = record.get("userIdentity") or {}
    actor = (
        user_identity.get("arn")
        or user_identity.get("userName")
        or user_identity.get("type")
        or "unknown"
    )
    error_code = record.get("errorCode", "")
    parts = [
        f"{record.get('eventName', 'UnknownAction')} on {record.get('eventSource', 'unknown')}",
        f"by {actor}",
    ]
    if record.get("sourceIPAddress"):
        parts.append(f"from {record['sourceIPAddress']}")
    if error_code:
        parts.append(f"ERROR {error_code}: {record.get('errorMessage', '')}")
    severity = "error" if error_code else "info"
    if error_code in ("AccessDenied", "UnauthorizedOperation", "AccessDeniedException"):
        severity = "warning"  # access denials are policy signals, often expected noise
    if record.get("readOnly") is False and not error_code:
        severity = severity_from_text(record.get("eventName", ""), "info")
    return ParsedEvent(
        timestamp=parse_timestamp(record.get("eventTime")),
        source="cloudtrail",
        host=record.get("awsRegion", ""),
        severity=severity,
        event_id=record.get("eventName", ""),
        message=" ".join(parts)[:4000],
        raw=record,
    )


def normalize_kubernetes(record: dict) -> ParsedEvent:
    involved = record.get("involvedObject") or record.get("regarding") or {}
    obj = f"{involved.get('kind', 'Object')}/{involved.get('name', 'unknown')}"
    namespace = involved.get("namespace") or (record.get("metadata") or {}).get("namespace", "")
    event_type = record.get("type", "Normal")
    reason = record.get("reason", "")
    note = record.get("message") or record.get("note") or ""
    count = record.get("count") or (record.get("series") or {}).get("count")
    message = f"[{reason}] {obj}: {note}"
    if count and int(count) > 1:
        message += f" (x{count})"
    severity = "warning" if event_type == "Warning" else "info"
    if reason in ("Failed", "FailedScheduling", "FailedMount", "BackOff", "OOMKilling",
                  "CrashLoopBackOff", "Evicted", "NodeNotReady", "Unhealthy", "FailedCreate"):
        severity = "error"
    timestamp = parse_timestamp(
        record.get("lastTimestamp")
        or record.get("eventTime")
        or record.get("firstTimestamp")
        or (record.get("metadata") or {}).get("creationTimestamp")
    )
    source_component = (record.get("source") or {}).get("component") or record.get(
        "reportingController", ""
    )
    return ParsedEvent(
        timestamp=timestamp,
        source="kubernetes",
        host=namespace or source_component,
        severity=severity,
        event_id=reason,
        message=message[:4000],
        raw=record,
    )


_AZURE_LEVELS = {
    "critical": "critical",
    "error": "error",
    "warning": "warning",
    "informational": "info",
    "verbose": "debug",
    "sev0": "critical",
    "sev1": "error",
    "sev2": "warning",
    "sev3": "info",
    "sev4": "debug",
}


def normalize_azure(record: dict) -> ParsedEvent:
    # Common Alert Schema
    essentials = ((record.get("data") or {}).get("essentials")) or record.get("essentials")
    if isinstance(essentials, dict):
        severity = _AZURE_LEVELS.get(str(essentials.get("severity", "")).lower(), "warning")
        targets = essentials.get("alertTargetIDs") or []
        target = targets[0].split("/")[-1] if targets else ""
        message = (
            f"[{essentials.get('monitorCondition', 'Fired')}] "
            f"{essentials.get('alertRule', 'Azure alert')}: "
            f"{essentials.get('description', '')}"
        )
        return ParsedEvent(
            timestamp=parse_timestamp(essentials.get("firedDateTime")),
            source="azure",
            host=target,
            severity=severity,
            event_id=essentials.get("alertRule", ""),
            message=message[:4000],
            raw=record,
        )
    # Activity log
    operation = record.get("operationName")
    if isinstance(operation, dict):
        operation = operation.get("localizedValue") or operation.get("value", "")
    status = record.get("status")
    if isinstance(status, dict):
        status = status.get("localizedValue") or status.get("value", "")
    level = str(record.get("level", "")).lower()
    severity = _AZURE_LEVELS.get(level, severity_from_text(str(status or ""), "info"))
    resource = record.get("resourceId") or record.get("resourceUri") or ""
    resource_name = str(resource).split("/")[-1] if resource else ""
    caller = record.get("caller", "")
    message = f"{operation or 'Azure operation'} — status: {status or 'n/a'}"
    if caller:
        message += f" — caller: {caller}"
    return ParsedEvent(
        timestamp=parse_timestamp(record.get("eventTimestamp") or record.get("time")),
        source="azure",
        host=resource_name,
        severity=severity,
        event_id=str(operation or ""),
        message=message[:4000],
        raw=record,
    )


def normalize_vmware(record: dict) -> ParsedEvent:
    # vCenter event export shape (eventTypeId / fullFormattedMessage)
    message = record.get("fullFormattedMessage") or record.get("FullFormattedMessage") or ""
    event_type = record.get("eventTypeId") or record.get("EventTypeId") or ""
    if not message:
        message = first_str(record, "message", "description", "line")
    host = ""
    for key in ("host", "vm", "computeResource"):
        entity = record.get(key)
        if isinstance(entity, dict) and entity.get("name"):
            host = entity["name"]
            break
    alarm = record.get("alarm")
    if isinstance(alarm, dict) and alarm.get("name"):
        message = f"Alarm '{alarm['name']}': {message}"
    to_status = str(record.get("to", "")).lower()
    severity_map = {"red": "critical", "yellow": "warning", "green": "info", "gray": "info"}
    severity = severity_map.get(to_status) or severity_from_text(f"{event_type} {message}")
    return ParsedEvent(
        timestamp=parse_timestamp(record.get("createdTime") or record.get("CreatedTime")),
        source="vmware",
        host=host,
        severity=severity,
        event_id=str(event_type),
        message=str(message)[:4000],
        raw=record,
    )
