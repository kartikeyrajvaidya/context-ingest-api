# Batch 2a — App skeleton (no schema, no tables) ✅

**Goal:** The FastAPI app boots end-to-end against a Postgres that has no application tables yet. `GET /health` returns 200. `POST /v1/query` and `POST /v1/feedback` exist as route stubs returning `501 Not Implemented`. Alembic is wired up and runs successfully, but the initial migration is an **empty placeholder** — no `CREATE TABLE`, no `CREATE EXTENSION`, nothing. Model files exist as minimal stub classes (id column + `get_id_prefix` only) so future batches can drop bodies in without touching imports.

**Why this is a separate batch:** Batch 2 originally bundled the app skeleton *and* the full database schema *and* the full Pydantic contracts into one block. That let a lot of schema/contract design happen by default rather than by discussion. Splitting it gives 2b and 2c the space to be explicit about those decisions before any rows or routes depend on them.

**Hard rule:** 2a ships **no schema design**. Every column, index, and constraint is a 2c concern. If a decision about table shape comes up while working on 2a, it gets deferred — not answered inline.

## Files — present with real content

- `configs/{common,db,llm,rate_limit}.py` — config classes reading `os.environ`; only place env vars are touched.
- `db/connections/context_ingest_db.py` — async engine + `async_scoped_session` scoped by `current_task`, `NullPool`.
- `db/sqlalchemy/transaction.py` — transaction decorator.
- `db/migrations/alembic.ini`, `db/migrations/env.py`, `db/migrations/migrate.sh` — standard Alembic wiring.
- `db/migrations/sql/0001.sql` — **empty placeholder** *at the time 2a shipped*. Comment header only, no DDL. The wrapper tolerated an empty file and no-opped. **Superseded by 2c**, which overwrites `0001.sql` with the real documents + chunks schema (the "init" suffix that made the placeholder feel load-bearing was dropped when filenames went bare-numeric; there was no longer any reason for 0001 to be empty).
- `db/migrations/versions/0001.py` — Alembic wrapper that reads `0001.sql`. The empty-file guard was removed in 2c once 0001 gained real content.
- `api/server/{run_api,middleware,errorhandlers,request_validation}.py` — app factory, pass-through rate-limit middleware (real limiter comes in 3d), exception handlers, request validation helpers.
- `api/run.sh` — uvicorn launcher.
- `api/routes/health.py` — functional.
- `api/routes/{query,feedback}.py` — return `501 Not Implemented` with the stable error envelope.
- `libs/logger.py` — structured logger factory.
- `docker-compose.yml` + `Dockerfile`.
- All `__init__.py` files.

## Files — present as stubs (bodies filled later)

- `db/models/base.py` — `DeclarativeBase` + `BaseModel` with `created_at`, `get_by_id`, and the `_generate_random_string` id helper. No table classes here.
- `db/models/{documents,chunks,queries,feedback}.py` — each has a minimal class with `__tablename__`, an `id` column, and `get_id_prefix()`. **No business columns.** Every real column (source_url, embedding, FK to queries, UNIQUE, updated_at, etc.) is a 2c concern. Keeping the class shells here stabilises imports in `db/models/__init__.py` so 2c is a pure body-fill.
- `core/schema/{ingest,query,feedback,retrieval_result}.py` — existed as empty stubs at the end of 2a. **Bodies landed in Batch 2b** as the contract-first work. 2a itself owes nothing more here.

## Acceptance

- `docker compose up --build -d` boots cleanly.
- `curl http://localhost:8000/health` → `200 {"data": {"status": "ok"}}`.
- `curl -X POST http://localhost:8000/v1/query -d '{}'` → `501 Not Implemented` with the standard error envelope.
- `curl -X POST http://localhost:8000/v1/feedback -d '{}'` → `501 Not Implemented`.
- `psql` shows **zero application tables** — only Alembic's `alembic_version` row pointing at `0001`.
- `db/models/{documents,chunks,queries,feedback}.py` each define a class with `__tablename__`, an `id` column, and `get_id_prefix()` — nothing else. Importing the module succeeds.
- Ruff and pre-commit pass on the full tree. CI is green.

## Reconciliation (folded in — no separate PR)

The code originally merged as part of the old Batch 2 had full table bodies in `0001.sql` and full column definitions in each model. Reconciliation was applied directly on `main`:

1. **Emptied** `db/migrations/sql/0001.sql` — comment header only, no DDL.
2. **Stripped** `db/models/{documents,chunks,queries,feedback}.py` bodies down to the minimal stub shape described above.
3. **Hardened** `db/migrations/versions/0001.py` to no-op on an empty SQL file.
4. `api/routes/ingest.py` was already deleted during the 3a prep — left as is.
5. `core/schema/*` were **not** re-emptied, because 2b had already written the frozen contract bodies. 2a's "empty stubs" column is therefore a historical snapshot; current reality is "bodies owned by 2b".

After reconciliation, 2a's acceptance bullets all pass and 2c has a clean slate to own the real schema.
