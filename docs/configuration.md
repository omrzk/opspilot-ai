# Configuration

All configuration is environment-driven (12-factor). Copy `.env.example` to `.env`.

## Core

| Variable | Default | Notes |
|---|---|---|
| `OPSPILOT_SECRET_KEY` | dev value | **Set a long random string in production.** Signs JWTs. |
| `OPSPILOT_ENVIRONMENT` | `development` | informational |
| `OPSPILOT_CORS_ORIGINS` | `http://localhost:3000` | comma-separated |
| `OPSPILOT_UPLOAD_DIR` | `/data/uploads` | must be writable by api + worker |

## Database & queue

| Variable | Default |
|---|---|
| `POSTGRES_HOST` / `POSTGRES_PORT` | `db` / `5432` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `opspilot` |
| `REDIS_URL` | `redis://redis:6379/0` |

PostgreSQL needs the `vector` extension — the provided `pgvector/pgvector:pg16` image has it;
the initial migration runs `CREATE EXTENSION IF NOT EXISTS vector`.

## Chat LLM

Set `LLM_PROVIDER` to one of:

### `anthropic`
| Variable | Example |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-…` |
| `ANTHROPIC_MODEL` | `claude-sonnet-5` |

### `openrouter`
| Variable | Example |
|---|---|
| `OPENROUTER_API_KEY` | `sk-or-…` |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-5`, `meta-llama/llama-3.1-70b-instruct`, … |

### `ollama`
| Variable | Example |
|---|---|
| `OLLAMA_BASE_URL` | `http://host.docker.internal:11434` (compose) / `http://localhost:11434` |
| `OLLAMA_MODEL` | `llama3.1:8b`, `qwen2.5:14b`, … |

### `openai_compatible`
Any endpoint speaking the OpenAI `chat/completions` dialect (vLLM, LM Studio, LiteLLM, …):

| Variable | Example |
|---|---|
| `OPENAI_COMPATIBLE_BASE_URL` | `http://vllm:8000/v1` |
| `OPENAI_COMPATIBLE_API_KEY` | optional |
| `OPENAI_COMPATIBLE_MODEL` | server-defined model name |

## Embeddings (RAG)

| Variable | Default | Notes |
|---|---|---|
| `EMBEDDING_PROVIDER` | `ollama` | `ollama` or `openai_compatible` |
| `EMBEDDING_MODEL` | `nomic-embed-text` | `ollama pull nomic-embed-text` |
| `EMBEDDING_DIM` | `768` | **must match the model** |

### Changing `EMBEDDING_DIM` on an existing database

The `document_chunks.embedding` column is created with the dimension in effect at migration
time. If you switch to a model with a different dimension you must recreate the column:

```sql
ALTER TABLE document_chunks DROP COLUMN embedding;
ALTER TABLE document_chunks ADD COLUMN embedding vector(1024);  -- new dim
CREATE INDEX ix_document_chunks_embedding ON document_chunks
  USING hnsw (embedding vector_cosine_ops);
```

then re-ingest your documents (embeddings from different models are not comparable anyway).

## Tuning

| Variable | Default | Purpose |
|---|---|---|
| `llm_timeout_seconds` (settings) | 180 | HTTP timeout per LLM call |
| `rag_chunk_size` / `rag_chunk_overlap` | 1200 / 150 | chunking |
| `rag_top_k` | 6 | chunks retrieved per query |
| `max_upload_mb` | 200 | upload size cap |
