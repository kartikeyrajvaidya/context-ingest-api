# Architecture

The full architecture lives at [`docs/architecture/overview.md`](./docs/architecture/overview.md). This file is a quick reference for contributors.

## Design goals

1. **One stack.** FastAPI + Postgres + OpenAI. No swappable backends, no plugin systems.
2. **Everything in Postgres.** Documents, chunks, embeddings, queries, feedback. One database, one backup.
3. **Strict layering.** HTTP -> action -> service -> model. Each layer has one job.
4. **Rerun-safe ingestion.** Same URL twice = no-op unless content changed.
5. **Public-internet safe.** Rate limiting, safety gate, and input validation are on by default.

## Module map

```
api/          HTTP layer (routes, middleware, error handlers)
configs/      Env-driven config (one class per subsystem)
core/
  actions/    One file per use case (ingest_document, query_document, etc.)
  ingestion/  Fetch -> clean -> chunk pipeline
  safety/     Pre-LLM safety gate (heuristics + classifier)
  rate_limit/ Rate limiting logic
  schema/     Pydantic request/response models
  services/   External adapters (OpenAI embeddings, LLM, prompts)
db/
  models/     SQLAlchemy models with query methods
  migrations/ Alembic wrappers + raw SQL
libs/         Logger
scripts/      CLI tools
```

## Layering rules

1. `api/routes/` calls `core/actions/` only.
2. `core/actions/` orchestrates services and models. Owns transactions.
3. `core/services/` is the only place that imports `openai`.
4. `core/safety/` and `core/rate_limit/` have no `db/models/` imports.
5. `db/models/` never imports from `core/` or `api/`.
6. Only `configs/` reads env vars.
7. Prompts live in `core/services/prompts.py` only.
8. Pydantic schemas live in `core/schema/` only.
9. No `fastapi` imports anywhere in `core/`.

## Response envelope

```
Success:  {"data": {...}}
Error:    {"message": "..."}
```

## Deep dives

- [Architecture overview](./docs/architecture/overview.md) -- module layout, request lifecycles
- [Database schema](./docs/architecture/schema.md) -- tables, indexes, FK topology
- [Ingestion pipeline](./docs/architecture/ingestion-pipeline.md) -- fetch, clean, chunk, embed, persist
- [Hybrid retrieval](./docs/architecture/retrieval.md) -- vector + FTS + RRF, grounding, safety
