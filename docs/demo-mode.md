# Demo mode

Demo mode turns an OpsPilot deployment into a public, self-service showcase: visitors
click **Launch demo** and get their own isolated, pre-seeded, sandboxed session that runs
the real product (real parsers, real database, real AI calls) and resets automatically.

## Enabling it

Backend (`.env`):

```bash
OPSPILOT_DEMO_MODE=true
OPSPILOT_DEMO_TTL_MINUTES=45        # sessions expire after this long
OPSPILOT_DEMO_MAX_ANALYSES=5        # AI analyses per session (protects your API budget)
OPSPILOT_DEMO_MAX_CHAT_MESSAGES=40  # chat messages per session
OPSPILOT_DEMO_MAX_UPLOAD_MB=5       # upload size cap per file
```

Frontend (build-time):

```bash
NEXT_PUBLIC_DEMO_MODE=true
```

You must also run **Celery beat** so expired sessions get purged:

```bash
celery -A app.workers.celery_app beat --loglevel=info
```

(The bundled demo deployment runs a combined `worker -B` for this.)

## What each visitor gets

`POST /api/v1/demo/start` creates a fresh ephemeral user (`demo-<token>@demo.opspilot.local`)
and returns a short-lived JWT scoped to the TTL. The session is seeded with:

- **Four realistic log files**, parsed through the real pipeline:
  - `web-prod-01_auth.log` — an SSH brute-force that succeeds, then persistence (syslog)
  - `k8s-shop-events.json` — an OOMKilled CrashLoopBackOff outage (Kubernetes)
  - `cloudtrail-us-east-1.json` — a leaked access key doing recon + exfil (AWS CloudTrail)
  - `FIN-WKS-24_sysmon.xml` — malicious PowerShell from Office with C2 (Sysmon)
- **A completed AI analysis** of the SSH incident (root cause, affected systems,
  remediation, generated Bash/Ansible) so the value is visible immediately.
- **Three knowledge-base articles** (runbooks + severity policy) for RAG.
- **A welcome conversation** explaining what to try.

Visitors can then upload the other seeded files and run the AI themselves.

## Isolation & safety

- Every session is a separate user; all queries are user-scoped, so sessions never see
  each other's data.
- Public registration returns `403` while demo mode is on — the only way in is a demo session.
- Per-session caps on analyses, chat messages and upload size bound your LLM spend.
- A Celery beat job (`opspilot.purge_demo_sessions`, every 5 min) deletes expired demo
  users; the cascade removes their conversations, uploads, events, analyses, reports and
  knowledge documents, and the job unlinks upload files from disk first.

## Hosting under a sub-path

To serve the demo under e.g. `https://example.com/opspilot`, build the frontend with:

```bash
NEXT_PUBLIC_BASE_PATH=/opspilot
```

Next.js then emits all routes and assets under that prefix.
