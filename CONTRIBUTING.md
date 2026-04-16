# Contributing to ContextIngest API

Thanks for your interest in improving ContextIngest API. This document covers how to set up a dev environment, the conventions the codebase follows, and what a good PR looks like.

> Before contributing, please read our [Code of Conduct](./CODE_OF_CONDUCT.md). For security issues, see [SECURITY.md](./SECURITY.md) — **do not** file vulnerabilities as public issues.

## Ground rules

1. **Small PRs, clearly scoped.** One change per PR. "Refactor + new feature + docs update" is three PRs.
2. **Docs are part of the change.** If you add a route, update `docs/api/`. If you change the schema, update `docs/architecture/schema.md`. If you touch ingestion or retrieval behavior, update the architecture doc.
3. **No new dependencies without a reason.** Every line in `requirements.txt` is there because nothing in the standard library could do the job. If you add one, explain why in the PR description.
4. **The layering is load-bearing.** Routes do not call services. Services do not import routes. Actions own transactions. If a change makes you want to cross a layer, stop and ask — there is almost always a better shape.

## Dev setup

```bash
git clone https://github.com/kartikeyrajvaidya/context-ingest-api.git
cd context-ingest-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pre-commit ruff
pre-commit install
cp .env.example .env
```

`pre-commit install` wires the hooks defined in [`.pre-commit-config.yaml`](./.pre-commit-config.yaml) into your local `git commit`. They run `ruff check --fix`, `ruff format`, and a few file-hygiene checks on every commit. CI runs the same hooks, so anything pre-commit catches locally also blocks merges.

Set `OPENAI_API_KEY` in `.env`. Then either:

**Option A — full Docker:**

```bash
docker compose up --build -d
```

**Option B — local Postgres, Python on host:**

```bash
docker compose up postgres -d
bash db/migrations/migrate.sh
bash api/run.sh api
```

Verify:

```bash
curl -sS http://127.0.0.1:8000/health
```

## Running migrations

Migrations live in two places that must stay in sync:

- `db/migrations/versions/NNNN_*.py` — Alembic scripts, used for incremental upgrades.
- `db/migrations/sql/NNNN.sql` — raw SQL mirror, used by Docker Compose to initialize a fresh database in one shot.

When you add a migration:

1. Write the Alembic script first.
2. Run `bash db/migrations/migrate.sh` to verify it applies cleanly.
3. Hand-copy the equivalent SQL into `db/migrations/sql/NNNN.sql`.
4. Tear down your Docker volume (`docker compose down -v`) and `docker compose up --build -d` to verify the init path also works.

This dual maintenance is deliberate — it lets the Docker bootstrap be a single SQL file and keeps Alembic available for production upgrades.

## Code style

- **Python 3.11+.** Use modern typing (`list[str]`, `str | None`, `Annotated`).
- **Async everywhere on the HTTP path.** Routes, actions, services that touch I/O — all async. Synchronous helpers are fine for pure computation.
- **Pydantic for contracts.** Every request and response body is a Pydantic model in `core/schema/`. No `dict[str, Any]` crossing layer boundaries.
- **No comments that explain *what*.** Good names do that. Comments explain *why* — a constraint, a workaround, a non-obvious invariant.
- **No print statements.** Use `libs/logger.py`.
- **Lint and format with Ruff.** Configured in [`pyproject.toml`](./pyproject.toml). Ruff replaces black, isort, and flake8 in this project. Run `ruff check .` and `ruff format .` before pushing — pre-commit will do this for you automatically.

## Testing a change manually

For now the project does not ship an automated test suite (PRs adding pytest coverage are extremely welcome). When you make a change, at minimum:

1. Restart the API and hit `/health`.
2. Ingest a fresh URL and verify the document and chunks appear in Postgres.
3. Run a query against that URL and confirm the citations point at the right chunks.
4. Record a feedback row and confirm it lands in the `feedback` table.

For ingestion changes, also run the same URL twice and verify the second run reports `status: "unchanged"`.

## Adding a new route

1. Define request and response models in `core/schema/`.
2. Write the action in `core/actions/` — one function, async, takes the request model, returns the response model.
3. Wire the route in `api/routes/` — it calls the action and shapes the envelope.
4. Register the router in `api/server/run_api.py`.
5. Document the contract in `docs/api/`.
6. Add a curl example to `README.md` if the endpoint is public-facing.

## Adding a new ingestion source type

v0 supports URLs and raw text. If you want to add PDFs, GitHub READMEs, Notion exports, etc.:

1. Add a new fetcher in `core/ingestion/` — it must produce the same `(title, text, content_hash)` tuple the existing fetcher produces.
2. Extend `core/schema/ingest.py` with the new input shape.
3. Route to the new fetcher inside `core/actions/ingest_document.py` based on input shape.

Do **not** add a plugin system or a fetcher registry. Two or three sources is a short `match` statement; ContextIngest's simplicity is its promise.

## Adding a new retrieval strategy

The hybrid retriever (vector + full-text fused with RRF) is deliberate and well-studied. If you want to experiment with rerankers, cross-encoders, or MMR, open an issue first — we want these to live behind an opt-in config flag, not replace the default.

## Commit and PR hygiene

- **Commits:** imperative mood, under 72 chars in the subject. `Add feedback endpoint`, not `Added feedback endpoint` or `feat: feedback stuff`.
- **PR description:** what changed, why, and how you verified it. If it touches a contract, paste the before/after curl.
- **No "fix lint" / "address review" commits in the final history.** Squash or rebase before merging.

## Security

If you find a vulnerability, **do not open a public issue**. Follow the private disclosure process in [`SECURITY.md`](./SECURITY.md). You can expect an acknowledgement within 3 business days and a fix or mitigation within 30 days for high-severity issues.

## License

By contributing, you agree your contributions will be released under the [MIT License](./LICENSE).
