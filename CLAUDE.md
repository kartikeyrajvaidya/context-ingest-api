# ContextIngest API

Open-source, self-hosted RAG backend: FastAPI + Postgres (pgvector) + OpenAI. MIT licensed.

Read these first:

- [ARCHITECTURE.md](./ARCHITECTURE.md): module map, layering rules, response envelope.
- [CONTRIBUTING.md](./CONTRIBUTING.md): dev setup, migrations, code style, PR hygiene.
- `.claude/skills/`: deeper backend and RAG pipeline rules, loaded on demand.

## Public repo rule

This repository is public and standalone. Never name, link or describe any other project, private repository, website or product in code, docs, comments, commit messages, PR text or the CHANGELOG. Examples use neutral placeholders (`example.com`, `internal://faq`).

## Layering (full list in ARCHITECTURE.md)

- HTTP -> action -> service -> model. Routes in `api/routes/` call actions in `core/actions/`.
- Actions orchestrate services and models and own transactions.
- `core/services/` is the only place that imports `openai`. Prompts live in `core/services/prompts.py`.
- Pydantic schemas live in `core/schema/`. No `fastapi` imports in `core/`.
- `db/models/` never imports from `core/` or `api/`. Only `configs/` reads env vars.
- Success responses are `{"data": {...}}`; errors are `{"message": "..."}` (validation errors add `errors`).

## Local dev

| Service | Port | Source |
|---|---|---|
| API | 8080 | `docker-compose.yaml`, `api/run.sh` |
| Postgres | 5432 (override with `POSTGRES_HOST_PORT`) | `docker-compose.yaml` |

```bash
pip install -r requirements-dev.txt
ruff check . && ruff format --check .
bash .github/scripts/mypy_ratchet.sh
pytest
```

DB-backed tests skip when Postgres is down. Start it with `docker compose up postgres -d` and apply migrations with `bash db/migrations/migrate.sh`. OpenAI is always mocked in tests.

## Rules for changes

- Migrations go in both `db/migrations/versions/` and `db/migrations/sql/` (see CONTRIBUTING).
- Add a CHANGELOG entry under `[Unreleased]` for any user-visible change.
- No new runtime dependency without a stated reason in the PR.
- New behaviour comes with a test in `tests/`. Never weaken or delete a failing test to get CI green.
- mypy runs as a ratchet: new errors fail CI. Fix errors rather than adding them to `.github/mypy-baseline.txt`.
- A PostToolUse hook (`.claude/settings.json`) runs ruff on every edited `.py` file. Fix what it reports.

## Deferred (do not build unless asked)

- Deployment docs (production hosting, managed Postgres, secrets, scaling). Local docker compose is the only supported path today.
- A broader pre-LLM safety classifier. The shipped gate in `core/safety/` only blocks prompt injection and jailbreak attempts; wider abuse categories were deferred.
