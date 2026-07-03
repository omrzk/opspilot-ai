# API reference

Interactive OpenAPI docs are served at **`/docs`** (Swagger UI) and **`/redoc`** when the
API is running. All endpoints are prefixed with `/api/v1`. Authentication is a Bearer JWT
from `/auth/register` or `/auth/login`.

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Create account (first account becomes admin). Returns token + user. |
| POST | `/auth/login` | Returns token + user. |
| GET | `/auth/me` | Current user. |

## Chat

| Method | Path | Description |
|---|---|---|
| POST | `/chat` | Send a message. **SSE stream**: `meta` (conversation id, model, RAG sources) → `delta` (text chunks) → `done`. Body: `{message, conversation_id?, upload_ids?, use_rag?}` |
| GET | `/chat/conversations` | List conversations. |
| GET | `/chat/conversations/{id}` | Conversation with messages. |
| DELETE | `/chat/conversations/{id}` | Delete conversation. |

## Uploads

| Method | Path | Description |
|---|---|---|
| POST | `/uploads` | Multipart upload (`.evtx .json .ndjson .jsonl .csv .tsv .xml .txt .log`). Parsing runs async. |
| GET | `/uploads` | List uploads with status and detected `source_type`. |
| GET | `/uploads/{id}` | Upload detail. |
| GET | `/uploads/{id}/events?offset&limit&severity` | Paginated normalized events. |
| DELETE | `/uploads/{id}` | Delete upload, its file and events. |

## Analyses

| Method | Path | Description |
|---|---|---|
| POST | `/analyses` | Queue AI analysis. Body: `{upload_id, instructions?}`. Returns 202 with the queued row. |
| GET | `/analyses` | List analyses. |
| GET | `/analyses/{id}` | Full result: summary, root_cause, severity, confidence, affected_systems, remediation, scripts, evidence. |
| DELETE | `/analyses/{id}` | Delete. |

## Incidents

CRUD at `/incidents` (`POST`, `GET`, `PATCH /{id}`, `DELETE /{id}`).
Statuses: `open → investigating → mitigated → resolved/closed`.

## Reports

| Method | Path | Description |
|---|---|---|
| POST | `/reports` | Queue generation. Body: `{kind, analysis_id? , incident_id?, title?, instructions?}` where kind ∈ `incident_report, executive_summary, technical_report, postmortem, runbook`. |
| GET | `/reports` / `/reports/{id}` | List / detail (Markdown in `content_md`). |
| GET | `/reports/{id}/download` | Download as `.md`. |
| DELETE | `/reports/{id}` | Delete. |

## Knowledge base

| Method | Path | Description |
|---|---|---|
| POST | `/knowledge/documents` | Ingest text (`{title, text, doc_type, source?}`), chunked + embedded async. |
| GET | `/knowledge/documents` | List documents. |
| GET | `/knowledge/documents/{id}/stats` | Chunk count. |
| DELETE | `/knowledge/documents/{id}` | Delete document and chunks. |
| POST | `/knowledge/search` | Semantic search: `{query, top_k?}` → scored chunks. |

## Health

`GET /health` → `{status, api, database, redis, llm_provider}`.
