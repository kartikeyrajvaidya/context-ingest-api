# Layering Rules

This file encodes the exact layering the repo enforces. Read it once before writing any new file. The layering is load-bearing: most "this is awkward to do" feelings come from trying to cross a layer that should not be crossed.

For the high-level picture, see `../../../ARCHITECTURE.md`. This file is the working-rule version of that document.

## The five layers

```
┌─────────────────────────────────────────────────────────┐
│                      api/ (HTTP)                        │
│  routes, middleware, request validation, error handlers │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                     core/actions/                       │
│     thin orchestration — one file per use case          │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│           core/{ingestion,retrieval,orchestrator}/      │
│             pipeline / domain logic modules             │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                      core/services/                     │
│         external-world adapters (LLM, embeddings)       │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│                          db/                            │
│       SQLAlchemy models, migrations, transactions       │
└─────────────────────────────────────────────────────────┘
```

## Layer ownership

### `api/` (HTTP)

Owns: request envelope parsing, dependency wiring, response shaping, HTTP status codes.

Forbidden: business logic, DB access, prompt text, OpenAI calls, cross-action orchestration.

A route is at most ~20 lines. If it grows, the new code belongs in the action.

### `core/actions/`

Owns: one use case per file. Owns the transaction boundary. Calls into pipeline modules and services. Returns a domain object that the route shapes into the contract.

Forbidden: HTTP types (`Request`, `Response`, `HTTPException`), prompt text, raw SQL.

Naming: by operation, not by layer name. `ingest_document.py`, `query_document.py`, `record_feedback.py`. Never `document_service.py` or `query_handler.py`.

### `core/{ingestion,retrieval,orchestrator}/`

Owns: pipeline stages and domain logic. Pure-ish modules that take typed inputs and return typed outputs. May call services.

Forbidden: HTTP types, FastAPI imports, transaction management.

### `core/services/`

Owns: the only place that imports `openai`, `httpx`, or any other external SDK. Wraps batching, retries, and timeouts.

Forbidden: business decisions. A service does not know what a chunk is or what makes an answer valid. It only knows how to call the external thing reliably.

### `db/`

Owns: SQLAlchemy models, migrations, the async engine, the transaction context manager.

Forbidden: business logic, prompt text, OpenAI calls.

Model fetch helpers for one concrete table live as classmethods on that model class — not in `core/utils/` and not in route files.

## Cross-cutting rules

### Transactions

- Actions own the transaction. The transaction context manager lives in `db/sqlalchemy/transaction.py`.
- One action = one transaction. If two actions need to coordinate, that's a sign one of them should be merged into the other.
- A failed action leaves the database untouched.

### Pydantic schemas

- Every request body and every response body is a Pydantic model in `core/schema/`.
- `dict[str, Any]` does not cross layer boundaries. If you find yourself reaching for `Any`, write a model.
- Schemas are the contract. Treat them with the same care as the migration files.

### Prompts

- Prompt text lives in exactly one file per skill area: `core/services/prompts.py`.
- Routes, actions, and orchestrator modules import prompts. They do not contain prompt strings.
- Prompts have stable names. Renaming a prompt is a contract change.

### Configuration

- All configuration is environment-driven via `configs/`.
- `os.environ` does not appear outside `configs/`. Everything else imports from `configs/`.
- Each module in `configs/` reads exactly the env vars it needs and exposes them as typed constants. No YAML files. No magic loaders.

### Logging

- The only logger is `libs/logger.py`. No `print`. No `logging.getLogger(...)` directly.
- See `logging_rules.md` for what to log and what not to log.

## Smoke tests for "is this layered correctly?"

If any of these are true, the layering is wrong and the code needs to move:

- A route imports from `core/services/`.
- A route imports from `db/`.
- An action imports `fastapi`.
- A service module knows what a "document" or "chunk" is.
- A `db/models/` file imports from `core/services/`.
- The `openai` package is imported anywhere outside `core/services/`.
- A prompt string appears in any file other than `core/services/prompts.py`.
- A migration version file contains business logic instead of SQL execution.
- An env var is read with `os.environ` outside `configs/`.

## What this layering is for

It is for **predictable change**. When a contract changes, the diff is one route + one schema + one action + maybe one model. When a model changes, the diff stays inside `db/models/` and the actions that touch it. When a prompt changes, the diff is one file.

The cost is a little more file-juggling for small changes. The benefit is that changes never accidentally cascade across the whole codebase. For a public OSS project where reviewers are not the author, that predictability is the difference between a maintainable repo and a tangle.
