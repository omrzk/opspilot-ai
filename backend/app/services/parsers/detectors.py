"""Detect which log source a batch of raw records came from."""

from app.services.parsers.normalizers.text import looks_like_syslog
from app.services.parsers.normalizers.windows import windows_channel, windows_provider

SAMPLE_SIZE = 25


def _is_windows_event(record: dict) -> bool:
    system = record.get("System")
    return isinstance(system, dict) and ("EventID" in system or "Provider" in system)


def _classify_windows(record: dict) -> str:
    provider = windows_provider(record).lower()
    channel = windows_channel(record).lower()
    if "sysmon" in provider or "sysmon" in channel:
        return "sysmon"
    if "windows defender" in provider or "windows defender" in channel:
        return "defender"
    return "windows_event"


def _is_cloudtrail(record: dict) -> bool:
    if "eventVersion" in record and "eventSource" in record:
        return True
    return "eventTime" in record and "eventName" in record and "awsRegion" in record


def _is_kubernetes(record: dict) -> bool:
    if record.get("kind") == "Event":
        return True
    if "involvedObject" in record and "reason" in record:
        return True
    return "regarding" in record and "reason" in record  # events.k8s.io/v1


def _is_azure(record: dict) -> bool:
    data = record.get("data")
    if isinstance(data, dict) and isinstance(data.get("essentials"), dict):
        return True
    if isinstance(record.get("essentials"), dict):
        return True
    has_operation = "operationName" in record
    has_resource = any(k in record for k in ("resourceId", "resourceUri", "resourceGroupName"))
    return has_operation and (has_resource or "correlationId" in record)


def _is_vmware(record: dict) -> bool:
    if any(k in record for k in ("eventTypeId", "fullFormattedMessage", "vmwareEvent")):
        return True
    if isinstance(record.get("alarm"), dict) and "chainId" in record:
        return True
    line = record.get("line", "")
    if isinstance(line, str):
        return any(marker in line for marker in ("vpxd", "hostd", "vmkernel", "vsanmgmt"))
    return False


def detect_source(fmt: str, records: list[dict]) -> str:
    """Inspect a sample of records and vote on the log source."""
    if not records:
        return "generic"
    sample = records[:SAMPLE_SIZE]
    votes: dict[str, int] = {}

    for record in sample:
        if _is_windows_event(record):
            votes[_classify_windows(record)] = votes.get(_classify_windows(record), 0) + 1
        elif _is_cloudtrail(record):
            votes["cloudtrail"] = votes.get("cloudtrail", 0) + 1
        elif _is_kubernetes(record):
            votes["kubernetes"] = votes.get("kubernetes", 0) + 1
        elif _is_azure(record):
            votes["azure"] = votes.get("azure", 0) + 1
        elif _is_vmware(record):
            votes["vmware"] = votes.get("vmware", 0) + 1
        elif fmt == "text" and looks_like_syslog(record.get("line", "")):
            votes["syslog"] = votes.get("syslog", 0) + 1

    if not votes:
        return "generic"
    winner, count = max(votes.items(), key=lambda kv: kv[1])
    # Require a plausible share of the sample to avoid misclassifying mixed files
    if count >= max(2, len(sample) // 4) or len(sample) < 4:
        return winner
    return "generic"
