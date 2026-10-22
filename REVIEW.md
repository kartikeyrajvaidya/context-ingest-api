# Automated review guide

Instructions for the automated reviewer on pull requests to this repository. Human maintainers approve and merge. The automated reviewer never approves a PR: it leaves comments only, and states clearly when it found nothing.

Report each finding with the file and line, what rule it breaks, and a concrete fix. Only comment on lines the PR adds or changes. Existing code that predates a rule is not a finding unless the PR touches it.

## What to check

### 1. Layering (ARCHITECTURE.md)

Flag any new import or call that breaks the rules in `ARCHITECTURE.md` "Layering rules", in particular:

- A route in `api/routes/` calling a service or model directly instead of an action.
- `openai` imported outside `core/services/`.
- Prompt text outside `core/services/prompts.py`.
- Pydantic request or response models defined outside `core/schema/`.
- `fastapi` imported anywhere in `core/`.
- `db/models/` importing from `core/` or `api/`.
- `os.environ` / `os.getenv` outside `configs/` (test setup in `tests/conftest.py` excepted).
- Transactions (`commit_transaction_async`) opened outside `core/actions/` (operator CLIs in `scripts/` excepted).

### 2. Response envelope

- Success bodies are `{"data": {...}}`.
- Error bodies are `{"message": "..."}`. Validation errors may add an `errors` list. No `detail`, `error`, or bare strings.
- A contract change updates the matching file in `docs/api/`.

### 3. Migrations

Any schema change adds a migration in both places, with the same number:

- `db/migrations/versions/NNNN.py` (Alembic)
- `db/migrations/sql/NNNN.sql` (raw SQL used by the Docker init path)

Flag a PR that edits one without the other, or that edits an already released migration instead of adding a new one. `docs/architecture/schema.md` changes with it.

### 4. CHANGELOG

A user-visible change (API contract, config, behaviour, dependency, migration) adds an entry under `## [Unreleased]` in `CHANGELOG.md`. Pure refactors, tests and CI-only changes may skip it.

### 5. Dependencies

A new line in `requirements.txt` or `requirements-dev.txt` must be justified in the PR description: what it does that the standard library or an existing dependency cannot. Versions are pinned with `==`.

### 6. Tests and CI

- New behaviour has a test in `tests/`. A bug fix has a test that fails without the fix.
- Flag any test that is deleted, skipped, or weakened, and any CI step that is removed or made non-blocking, unless the PR explains why.
- Flag new entries in `.github/mypy-baseline.txt`. The baseline should only shrink.
- Tests must not call OpenAI or any external network. Mock `core/services/` calls.

### 7. Public repository rule

This is a public, standalone, MIT-licensed project. Flag any mention of another project, private repository, company website or product by name, link or description, in code, comments, docs, commit messages, PR text or the CHANGELOG. Generic tool and library names (FastAPI, Postgres, OpenAI) are fine.

Also flag secrets, API keys, `.env` values, real personal data or real email addresses other than the maintainer contact already in the repo.

### 8. Style

- No em dashes in new docs or comments.
- No `print` in application code; use `libs/logger.py`.
- Comments explain why, not what.
