# Deployment

## Docker Compose (recommended)

```bash
cp .env.example .env   # set OPSPILOT_SECRET_KEY + provider keys
docker compose up -d --build
```

Services:

| Service | Image | Port |
|---|---|---|
| `db` | `pgvector/pgvector:pg16` | 5432 |
| `redis` | `redis:7-alpine` | 6379 |
| `api` | `backend/Dockerfile` | 8000 |
| `worker` | same image, Celery command | — |
| `frontend` | `frontend/Dockerfile` (standalone Next.js) | 3000 |

The `api` container runs `alembic upgrade head` on startup, so schema is always current.
Uploads live in the shared `uploads` volume (api writes, worker reads).

### Using Ollama on the host

The compose default points at `http://host.docker.internal:11434`. On Linux add:

```yaml
services:
  api:
    extra_hosts: ["host.docker.internal:host-gateway"]
  worker:
    extra_hosts: ["host.docker.internal:host-gateway"]
```

## Production hardening checklist

- [ ] Set a strong `OPSPILOT_SECRET_KEY` (e.g. `openssl rand -hex 32`).
- [ ] Change the PostgreSQL password; don't publish ports 5432/6379 beyond the compose network.
- [ ] Put the API and frontend behind TLS (Caddy/Traefik/nginx). SSE needs proxy buffering
      off for `/api/v1/chat` (the API already sends `X-Accel-Buffering: no`).
- [ ] Set `OPSPILOT_CORS_ORIGINS` to your real frontend origin.
- [ ] Back up the `pgdata` volume (analyses, knowledge base) and `uploads`.
- [ ] Scale workers by increasing `--concurrency` or adding `worker` replicas.

## Kubernetes sketch

The images are stateless apart from the uploads volume:

- `api` Deployment (+ HPA) with `alembic upgrade head` as an initContainer
- `worker` Deployment
- `frontend` Deployment
- PostgreSQL with pgvector (e.g. CloudNativePG + `pgvector` extension) and Redis
- ReadWriteMany PVC (or S3-backed storage class) mounted at `/data/uploads` in api + worker

## Health & observability

- `GET /api/v1/health` reports API/DB/Redis status — wire it to your probes.
- Logs are structured single-line stdout from both API and workers.
