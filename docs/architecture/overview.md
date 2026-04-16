# Architecture Overview

ContextIngest API is a self-hosted RAG backend: ingest content, ask questions, get cited answers. FastAPI + PostgreSQL + pgvector + OpenAI.

## Module layout

```
api/          HTTP layer — routes, middleware, error handlers
configs/      Env-driven config (one class per subsystem)
core/
  actions/    Use-case orchestrators (one file per endpoint)
  ingestion/  Fetch, clean, chunk pipeline
  safety/     Pre-LLM safety gate (heuristics + classifier)
  rate_limit/ Rate limiting logic
  schema/     Pydantic request/response models
  services/   External adapters (OpenAI, prompts)
db/
  models/     SQLAlchemy 2.0 declarative models
  migrations/ Alembic + raw SQL
libs/         Logger, shared utilities
scripts/      CLI tools (ingest, reembed)
```

## Layering rules

These are enforced by convention and checked in acceptance tests.

1. `api/routes/` calls `core/actions/` only — never `core/services/` or `db/` directly.
2. `core/actions/` orchestrates services and models. Owns transaction boundaries.
3. `core/services/` is the only place that imports `openai`.
4. `core/safety/` and `core/rate_limit/` never import from `db/models/` — they use injected counts.
5. `db/models/` never imports from `core/` or `api/`.
6. `configs/` reads env vars. No other module calls `os.getenv`.
7. Prompts live in `core/services/prompts.py` only.
8. Pydantic schemas live in `core/schema/` — not in routes, not in models.
9. No `fastapi` imports anywhere in `core/`.

## Request lifecycle — POST /v1/query

```
Client
  |
  v
IPRateLimitMiddleware    (layer 1: per-IP/min, in-memory)
  |
  v
api/routes/query.py      validate request, check session/conversation rate limits
  |
  v
core/safety/gate.py      regex heuristics -> LLM classifier (if SAFETY_ENABLED)
  |  blocked? -> return {status: "refused"}
  v
core/actions/query_document.py
  |-- write query_requests row
  |-- embed question          (core/services/embeddings.py)
  |-- hybrid retrieval        (db/models/chunks.py — vector + FTS + RRF)
  |-- compose answer          (core/services/llm.py — structured output)
  |-- write query_responses row
  v
200 {data: {query_id, status, answer, citations, confidence, next_actions}}
```

## Request lifecycle — POST /v1/ingest

```
Client (or scripts/ingest_all.py)
  |
  v
core/actions/ingest_manifest.py    read data/sources.json
  |
  v  (for each entry)
core/actions/ingest_document.py
  |-- fetch URL or read local file
  |-- clean HTML/markdown          (core/ingestion/cleaner.py)
  |-- hash content -> skip if unchanged
  |-- chunk                        (core/ingestion/chunker.py)
  |-- embed all chunks             (core/services/embeddings.py)
  |-- persist document + chunks    (one transaction)
  v
200 {data: {ok: true}}  (or 500 if any entry failed)
```

## Further reading

- [Database schema](./schema.md)
- [Ingestion pipeline](./ingestion-pipeline.md)
- [Retrieval deep-dive](./retrieval.md)
- [API contracts](../api/)
- [Tuning guide](../guides/tuning-retrieval.md)
