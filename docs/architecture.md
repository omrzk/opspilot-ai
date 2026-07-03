# Architecture

## Overview

OpsPilot AI is a three-tier system: a Next.js frontend, a FastAPI API, and Celery workers,
backed by PostgreSQL (with pgvector) and Redis. All AI calls go through a provider-agnostic
LLM layer.

## Request flows

### Upload → parse → analyze

1. `POST /api/v1/uploads` streams the file to disk (size-capped) and creates an `Upload` row.
2. The API enqueues `opspilot.parse_upload`. The worker:
   - reads the file with the right **format reader** (`services/parsers/formats.py`):
     EVTX (python-evtx), JSON/NDJSON (incl. `Records`/`items` envelopes), CSV (sniffed
     delimiter), XML (repeated-children detection), plain text. Files with wrong extensions
     are content-sniffed (EVTX magic, JSON/XML lead bytes).
   - runs **source detection** (`detectors.py`): votes over a sample of records to classify
     the batch as `windows_event`, `sysmon`, `defender`, `azure`, `vmware`, `cloudtrail`,
     `kubernetes`, `syslog` or `generic`.
   - applies the matching **normalizer** (`normalizers/`), producing unified `LogEvent`
     rows: timestamp, host, severity, event_id, human-readable message, raw payload.
3. `POST /api/v1/analyses` enqueues `opspilot.analyze`. The **analysis engine**
   (`services/analysis/engine.py`):
   - builds an **evidence digest** (`sampler.py`): severity distribution, top hosts and
     event IDs, time range, plus up to 120 highest-signal events with duplicates collapsed
     — so a 50k-event file fits in one prompt without losing the incident's shape.
   - retrieves related runbooks/incidents from the knowledge base (pgvector cosine search).
   - calls the configured LLM with a strict JSON contract and validates/coerces the result
     (`_coerce_result`) so malformed output can never corrupt the database.
   - persists root cause, affected systems, remediation steps, generated scripts
     (PowerShell/Bash/Terraform/Ansible), evidence and a clamped confidence score.

### Chat

`POST /api/v1/chat` returns an SSE stream (`meta` → `delta`* → `done`). The system prompt is
assembled per request from: the OpsPilot persona, retrieved knowledge-base chunks (with
scores, cited back to the client in `meta.sources`), and digests of any attached parsed
uploads. History is windowed to the last 20 messages. The assistant message is persisted
after the stream completes.

### Reports

`POST /api/v1/reports` enqueues `opspilot.generate_report`. The generator serializes the
linked analysis/incident into a fact block and instructs the LLM with a per-kind template
(incident report, executive summary, technical report, postmortem, runbook). The writer
prompt forbids invented facts — missing data becomes `TBD`.

## LLM provider layer

`services/llm/` defines two small interfaces:

- `ChatProvider.chat()` / `.stream()` — implemented natively for the Anthropic Messages API
  and once for the OpenAI `chat/completions` dialect, which covers OpenRouter, Ollama
  (`/v1`), vLLM, LM Studio, LiteLLM and any other compatible endpoint.
- `EmbeddingProvider.embed()` — Ollama native (`/api/embed`) or OpenAI-compatible
  (`/v1/embeddings`).

`factory.py` builds providers from settings; nothing else in the codebase knows which
vendor is in use. All HTTP goes through httpx with retry/backoff (tenacity).

`json_utils.extract_json_object()` recovers JSON from fenced blocks, surrounding prose and
raw control characters inside string literals — the three ways models actually break JSON.

## RAG

Documents are chunked paragraph-aware (~1200 chars, 150 overlap), embedded in batches and
stored in `document_chunks` with an HNSW cosine index. Retrieval is per-user and fails soft:
if the embedding endpoint is down, chat/analysis proceed without context instead of erroring.

## Data model

`users`, `conversations`/`messages`, `uploads`/`log_events`, `analyses`, `incidents`,
`reports`, `documents`/`document_chunks`. All rows are user-scoped; every API handler checks
ownership. Schema is managed by Alembic (`backend/alembic/versions/0001_initial.py`).

## Workers

Celery (Redis broker/backend), `acks_late`, prefetch 1, 20-minute hard time limit. Tasks
run async code via `asyncio.run` with a per-task NullPool engine so asyncpg connections
never outlive their event loop.

## Security notes

- Passwords: bcrypt. Sessions: HS256 JWTs signed with `OPSPILOT_SECRET_KEY`.
- Upload size is enforced during streaming; extensions are allow-listed and content-sniffed.
- The API never exposes provider API keys; they live only in server-side env vars.
