# Contributing to OpsPilot AI

Thanks for considering a contribution!

## Development setup

See the *Local development* section of the [README](README.md).

## Before you open a PR

```bash
# Backend
cd backend
ruff check app tests
pytest -q

# Frontend
cd frontend
npm run lint
npm run typecheck
npm run build
```

CI runs the same checks plus an Alembic migration roundtrip against PostgreSQL + pgvector
and Docker image builds.

## Guidelines

- Keep modules small and focused; parsers, providers and report kinds are all designed to be
  added without touching unrelated code.
- New log sources: add a detector in `app/services/parsers/detectors.py`, a normalizer under
  `app/services/parsers/normalizers/`, register it in `service.py`, and add tests.
- New LLM providers: implement `ChatProvider` (and `EmbeddingProvider` if applicable) in
  `app/services/llm/` and wire it into `factory.py`.
- No placeholder implementations — code must work end to end.
- By contributing you agree your work is licensed under AGPL-3.0-or-later.
