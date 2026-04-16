# ContextIngest API — Scaffolding Plan

> **Current status:** see [`batches/README.md`](./batches/README.md) for the live tracker.

This document is the living plan for building ContextIngest API from an empty directory to a v0 release. It exists so anyone (including future-me) can see what was decided, why, and what's left.

For the *what it is* and *how it works*, read [`README.md`](../README.md) and [`ARCHITECTURE.md`](../ARCHITECTURE.md). This file is about *how it gets built*.

---

## Goal

Ship a public, reputation-grade open-source RAG backend that:

- Mirrors a layered FastAPI + Postgres + pgvector + OpenAI stack proven in production.
- Adds full GitHub Community Standards hygiene (CoC, SecurityPolicy, CI, issue/PR templates).
- Adds modern Python tooling (Ruff, pre-commit, pyproject.toml, mypy config).
- Is single-tenant, opinionated, and small enough that one person can hold the whole codebase in their head.

**Non-goals for v0:** multi-tenancy, authentication, background queues, streaming responses, conversation memory, plugin systems.

---

## Stack

| Layer         | Choice                                        |
|---------------|-----------------------------------------------|
| Web framework | FastAPI 0.116 (async)                         |
| Database      | PostgreSQL 17 with pgvector                   |
| ORM           | SQLAlchemy 2.0 (async) + asyncpg              |
| Migrations    | Alembic + raw SQL in `db/migrations/sql/`     |
| Embeddings    | OpenAI `text-embedding-3-small` (1536 dims)   |
| Answer LLM    | OpenAI `gpt-5.4-mini` (configurable)          |
| Content fetch | `trafilatura` + `httpx`                       |
| Chunking      | `tiktoken`-based, token-aware with overlap    |
| Lint/format   | Ruff (replaces black + isort + flake8)        |
| Type checking | mypy (advisory in v0, not CI-gated)           |
| CI            | GitHub Actions: Ruff + py3.11/3.12 smoke + Docker build |
| Hooks         | pre-commit (Ruff + file hygiene)              |
| Python        | 3.11+                                          |
| License       | MIT                                            |

---

## Decisions (and why)

| Question | Decision | Reasoning |
|---|---|---|
| Project name | `context-ingest-api` | Descriptive, broader than "blog" so it can grow into docs sites. |
| Code of Conduct | Contributor Covenant 2.1 (linked, not duplicated) | Industry standard. Linking the canonical file means upstream version bumps stay current automatically and avoids reproducing trigger text. |
| Security policy | Private email reporting, 3-day ack, 90-day default disclosure | OpenSSF baseline; matches how mature OSS projects (FastAPI, Django) handle disclosures. |
| Lint/format tool | Ruff only | One Rust-fast tool replaces black + isort + flake8; configured in `pyproject.toml`. |
| Type checking gate | mypy configured but not CI-enforced | Don't gate PRs on type errors before code exists. Tighten later. |
| Issue templates | YAML Forms syntax | GitHub's recommended format since 2022; produces structured, validated reports. |
| CI matrix | Ubuntu × Python 3.11, 3.12 | Covers Docker base image + next stable. Adding 3.13 once it's broadly adopted. |
| Dependency updates | Dependabot weekly (pip, actions, docker) | Set-and-forget; one weekly PR digest beats unbounded daily noise. |
| Versioning | SemVer, currently `0.1.0a0` | "Alpha" signals "API may change" honestly. Public bump to `1.0` only when contracts are frozen. |
| Branch model | `main` only, trunk-based | Smallest possible workflow for a one-maintainer OSS project. |
| Multi-tenancy | None in v0 | Single Postgres, single namespace. Operators run one instance per tenant. |
| Auth | None in v0 | Documented as "put a reverse proxy in front of it." Avoids API-key scaffolding for a feature most self-hosters don't need. |
| Ingest over HTTP | None in v0 — CLI only | Ingest is an **operator** action, not a user action. With no auth in v0, exposing arbitrary URL ingest over HTTP lets any stranger drive an operator's OpenAI bill. CLI (`scripts/ingest_all.py` reading `data/sources.json`, plus `scripts/ingest_one.py` for ad-hoc single items) keeps the action reusable for a future manifest-triggered refresh endpoint. See "Future: manifest-driven refresh" below. |
| Conversation memory | None in v0 | Each query independent. Multi-turn lives in the frontend or a thin layer above ContextIngest. |
| Background jobs | None in v0 | Ingestion is synchronous in the request handler; large sites use the CLI. |

---

## Directory tree (target)

```
context-ingest-api/
│
├── README.md                     ✅
├── ARCHITECTURE.md               ✅
├── CONTRIBUTING.md               ✅
├── CHANGELOG.md                  ✅
├── LICENSE                       ✅
├── CODE_OF_CONDUCT.md            ✅
├── SECURITY.md                   ✅
├── pyproject.toml                ✅
├── .pre-commit-config.yaml       ✅
├── .editorconfig                 ✅
├── .python-version               ✅
├── .env.example                  ✅
├── .gitignore                    ✅
├── Dockerfile                    ✅
├── docker-compose.yaml           ✅
├── requirements.txt              ✅
│
├── .github/                      ✅
│   ├── CODEOWNERS
│   ├── dependabot.yml
│   ├── PULL_REQUEST_TEMPLATE.md
│   ├── ISSUE_TEMPLATE/
│   │   ├── config.yml
│   │   ├── bug_report.yml
│   │   └── feature_request.yml
│   └── workflows/
│       └── ci.yml
│
├── api/                          ⏳ Batch 2
│   ├── run.sh
│   ├── routes/
│   │   ├── health.py
│   │   ├── query.py              (stub → real in B3b)
│   │   └── feedback.py           (stub → real in B3c)
│   └── server/
│       ├── run_api.py
│       ├── middleware.py
│       ├── errorhandlers.py
│       └── request_validation.py
│
├── configs/                      ⏳ Batch 2
│   ├── common.py
│   ├── db.py
│   ├── llm.py
│   └── rate_limit.py
│
├── core/                         ⏳ Batch 2 (schema) + Batch 3 (logic)
│   ├── actions/                  Batch 3
│   │   ├── ingest_document.py
│   │   ├── query_document.py
│   │   └── record_feedback.py
│   ├── ingestion/                Batch 3
│   │   ├── fetcher.py
│   │   ├── cleaner.py
│   │   ├── chunker.py
│   │   └── pipeline.py
│   ├── retrieval/                Batch 3
│   │   ├── vector.py
│   │   ├── fulltext.py
│   │   └── hybrid.py
│   ├── orchestrator/             Batch 3
│   │   └── answer_composer.py
│   ├── services/                 Batch 3
│   │   ├── embeddings.py
│   │   ├── llm.py
│   │   └── prompts.py
│   ├── schema/                   Batch 2
│   │   ├── ingest.py
│   │   ├── query.py
│   │   ├── feedback.py
│   │   └── retrieval_result.py
│   └── rate_limit/               Batch 3
│       └── ip_limiter.py
│
├── db/                           ⏳ Batch 2
│   ├── connections/
│   │   └── context_ingest_db.py
│   ├── models/
│   │   ├── base.py
│   │   ├── documents.py
│   │   ├── chunks.py
│   │   ├── queries.py
│   │   └── feedback.py
│   ├── sqlalchemy/
│   │   └── transaction.py
│   └── migrations/
│       ├── alembic.ini
│       ├── env.py
│       ├── migrate.sh
│       ├── sql/0001.sql
│       └── versions/0001.py
│
├── libs/                         ⏳ Batch 2
│   └── logger.py
│
├── scripts/                      ⏳ Batch 3a/3e
│   ├── ingest_all.py             Batch 3a — zero-arg, reads data/sources.json (URLs + local files)
│   ├── ingest_one.py             Batch 3a — ad-hoc single --url or --file for testing
│   └── reembed_all.py            Batch 3e — re-embed existing chunks without refetching
│
├── docs/                         (this file ✅; rest in Batch 3)
│   ├── scaffolding-plan.md       ← you are here
│   ├── api/
│   │   ├── ingest.md
│   │   ├── query.md
│   │   └── feedback.md
│   ├── architecture/
│   │   ├── overview.md
│   │   ├── ingestion-pipeline.md
│   │   ├── retrieval.md
│   │   └── schema.md
│   └── guides/
│       ├── quickstart.md
│       ├── self-hosting.md
│       └── tuning-retrieval.md
│
└── skills/                       ⏳ Batch 3
    ├── context-ingest-api-backend/
    │   ├── SKILL.md
    │   ├── agents/openai.yaml
    │   └── references/
    │       ├── stack_rules.md
    │       ├── api_rules.md
    │       ├── layering_rules.md
    │       ├── migration_rules.md
    │       └── logging_rules.md
    └── context-ingest-rag-pipeline/
        ├── SKILL.md
        ├── agents/openai.yaml
        └── references/
            ├── ingestion_rules.md
            ├── retrieval_rules.md
            ├── prompt_eval_rules.md
            └── contract_rules.md
```

---

## Batches

Each batch has its own file under [`batches/`](./batches/). This section is an index; open the file for goal, scope, files, acceptance, and design notes.

> **Live status tracker:** [`batches/README.md`](./batches/README.md) is the single source of truth for which batch is done, in progress, or blocked. The one-line statuses below are a convenience mirror and may lag the tracker — when they disagree, trust the tracker.

### Batch 1 — Repo skeleton & OSS hygiene
- ✅ [`batches/batch1/1-repo-skeleton.md`](./batches/batch1/1-repo-skeleton.md) — README, ARCHITECTURE, CONTRIBUTING, CHANGELOG, LICENSE, Dockerfile, compose, env.
- ✅ [`batches/batch1/1.5-oss-hygiene.md`](./batches/batch1/1.5-oss-hygiene.md) — CoC, SECURITY, pyproject, pre-commit, issue/PR templates, CI.

### Batch 2 — App skeleton → contracts → schema
- ✅ [`batches/batch2/2a-app-skeleton.md`](./batches/batch2/2a-app-skeleton.md) — App boots, `/health` works, `/v1/query` + `/v1/feedback` are 501 stubs, empty init migration, no tables, model/schema files as TODO stubs.
- ⏳ [`batches/batch2/2b-contracts-and-schemas.md`](./batches/batch2/2b-contracts-and-schemas.md) — Contract-first: `docs/api/query.md` + `docs/api/feedback.md` first, then Pydantic classes. Ratifies error envelope, citation shape, confidence label, rating domain.
- ⏳ [`batches/batch2/2c-migrations-and-tables.md`](./batches/batch2/2c-migrations-and-tables.md) — `0001_documents_and_chunks.sql`, `0002_queries_and_feedback.sql`, ORM models.

### Batch 3 — Pipeline → query → feedback → docs
- ⏸ [`batches/batch3/3a-ingestion-pipeline.md`](./batches/batch3/3a-ingestion-pipeline.md) — CLI-only ingestion (fetcher, cleaner, chunker, pipeline, action, scripts). Paused on 2b/2c.
- ⏳ [`batches/batch3/3b-query-path.md`](./batches/batch3/3b-query-path.md) — Real `POST /v1/query` with hybrid RRF retrieval + answer composer.
- ⏳ [`batches/batch3/3c-feedback.md`](./batches/batch3/3c-feedback.md) — Real `POST /v1/feedback` with replace semantics.
- ⏳ [`batches/batch3/3d-ratelimit.md`](./batches/batch3/3d-ratelimit.md) — Real per-IP rate limiter wired into the Batch 2a pass-through middleware.
- ⏳ [`batches/batch3/3e-reembed.md`](./batches/batch3/3e-reembed.md) — `scripts/reembed_all.py` operator CLI + narrow `Chunk` read/write helpers.
- ✅ [`batches/batch3/3g-safety-classifier.md`](./batches/batch3/3g-safety-classifier.md) — Lightweight two-layer pre-LLM safety gate: regex heuristics + cheap LLM classifier, detecting prompt injection and jailbreak. One switch (`SAFETY_ENABLED`), no DB migration, no persistence of refused queries. Also added client-facing `status` field to response and consolidated `query_responses` columns into `response_payload` JSONB.
- ✅ [`batches/batch3/3h-refresh-endpoint.md`](./batches/batch3/3h-refresh-endpoint.md) — `POST /v1/ingest` endpoint. Manifest-driven ingestion over HTTP, no request body, rerun-safe. Shared action in `core/actions/ingest_manifest.py` used by both route and CLI. Returns `{"data": {"ok": true}}` on success, 500 on failure.
- ✅ [`batches/batch3/3f-docs.md`](./batches/batch3/3f-docs.md) — Public docs for every shipped surface. README + ARCHITECTURE refreshed; architecture docs, guides, API contract polish.


---

## Out of scope for v0 (deliberately)

These are intentionally deferred. If you want any of them in v0, say so before the relevant batch.

- **API key authentication.** Documented as "put a reverse proxy in front of it."
- **Multi-tenancy.** One database, one namespace.
- **Ingest over HTTP.** v0 is CLI-only — see "Future: manifest-driven refresh API" below.
- **`robots.txt` awareness in the fetcher.** Operators ingest content they already own; respecting `robots.txt` on self-hosted ingestion adds a per-request fetch and a cache layer without a corresponding user benefit in v0.
- **Streaming SSE responses.** `/v1/query` returns the full answer.
- **Conversation memory.** Each query is independent.
- **Background queue.** Ingestion is synchronous; CLI for batch.
- **Reranker / cross-encoder retrieval.** Hybrid RRF only.
- **Non-URL ingestion sources** (PDF, Notion, GitHub READMEs). v0 is URL + raw text.
- **Pytest suite.** Manual verification only in v0; PRs adding tests are welcome.
- **Frontend.** ContextIngest is a backend primitive. Bring your own UI.

### Future: manifest-driven refresh API

v0 ships without an ingest HTTP route. The manifest already exists as `data/sources.json` and is consumed today by `scripts/ingest_all.py`. A future batch may add a single trigger endpoint — `POST /v1/refresh` — that takes **no content in the body** and reuses the same manifest the CLI already reads:

```json
[
  { "url": "https://example.com/posts/one", "title": "Post One" },
  { "url": "https://example.com/posts/two" },
  { "url": "knowledge://faq-setup", "title": "Setup FAQ", "file": "data/knowledge/faq-setup.md" }
]
```

The endpoint iterates the manifest and calls `core/actions/ingest_document.ingest_document` for each entry — the same loop the CLI uses today. Because ingestion is rerun-safe via SHA-256 content hashing, unchanged entries short-circuit before any embedding or DB write — an attacker hitting the endpoint 1,000 times a second produces 1,000 cheap hash lookups and zero OpenAI spend.

Why this shape is safe to expose without auth:

1. The operator controls the manifest (it lives in their repo). Attackers cannot inject new ingestion targets through the request body.
2. Rerun-safety collapses repeat calls to no-ops — no unbounded embedding cost.
3. The per-IP rate limit from Batch 3d still applies as a secondary safety net.

Why this is better than v0's original "take a URL in the body" shape:

- Ingestion targets are version-controlled and reviewable.
- The manifest doubles as documentation of what is in the RAG index.
- CI can trigger the refresh after every manifest change to keep the index in sync with the repo.

The `core/actions/ingest_document` action built in Batch 3a is designed to be the single callable both CLI scripts and the future refresh loop share. No refactor will be required to add the endpoint — it is one route file, one small manifest parser, and one loop.

---

## Open questions

None right now. Update this section when something is undecided.

---

## Deviations from the original plan

- **Batch 2 split into 2a/2b/2c.** The original Batch 2 bundled the app skeleton, the full database schema, and the full Pydantic contracts into one block. That let a lot of contract and schema design happen implicitly — columns and response shapes got decided while wiring routes, not while discussing contracts. The split forces three distinct checkpoints: 2a ships a booting app with *empty* migrations and stub models/schemas; 2b is a contract-first discussion that produces `docs/api/{query,feedback}.md` and then the Pydantic classes; 2c turns those contracts into tables and ORM models, with deliberate design choices (request/response split, FK cascades, `source_url` not nullable, no `authority` column). A small "2a reconciliation" PR will gut the current code on `main` (empty the init migration, remove table/schema bodies) before 2b/2c land — not executed until this plan is approved.
- **Batch 2:** dropped `api/server/dependencies.py`. The original plan included it as a no-op `authorize()` placeholder mirroring the reference repo. Phase rules forbid adding auth before an auth batch, and v0 explicitly ships with no authentication, so a placeholder would be dead code. An auth-focused future batch will introduce this file along with the real dependency.
- **Batch 2:** migration filenames are bare numeric (`0001.sql`, `0002.sql`, …) — no descriptive suffix. The raw SQL mirror in `sql/` and the Alembic wrapper in `versions/` share the exact filename, and the Alembic wrapper derives its `revision` id from the filename. The docker-compose init mount and the repo skill's `migration_rules.md` reflect this.
- **Batch 3 split into 3a/3b/3c/3d/3e/3f.** The original Batch 3 bundled ingestion, retrieval, feedback, rate limiting, scripts, and all docs into one block. Each sub-batch ships one coherent slice, keeps diffs reviewable, and lets early adopters start using the CLI ingestion path before the query path is finished. The original 3c (feedback + rate limit + reembed) was first split into 3c (feedback only) and 3d (rate limit + reembed), pushing docs to 3e. 3d was then further split into 3d (rate limiter only) and 3e (reembed script only) because the two operator concerns share no code, no contract, and no review surface — merging them was a scheduling convenience, not a cohesion signal. Docs moved to 3f.
- **Batch 3a:** dropped the `POST /v1/ingest` route. Ingest is an operator action, and exposing arbitrary-URL ingest over an unauthenticated HTTP endpoint in v0 would let any stranger drive an operator's OpenAI bill. The action in `core/actions/ingest_document.py` is still written, still called by the Batch 3a scripts, and is deliberately shaped so a future "manifest-driven refresh" endpoint can reuse it without refactoring. See "Future: manifest-driven refresh API" above.
- **Batch 3a:** no `docs/api/ingest.md`. Because there is no public ingest HTTP contract in v0, the CLI is documented in `docs/guides/ingestion.md` (Batch 3f) instead.
- **Batch 3a (post-ship consolidation):** the original two-script CLI (`scripts/ingest_url.py` single URL + `scripts/ingest_batch.py` newline-delimited URL list) was consolidated into one manifest-driven script, `scripts/ingest_all.py`, which reads `data/sources.json` and handles both URL and local-file entries (entries with a `file` key are read, cleaned, and ingested under a stable synthetic identifier like `knowledge://...`). A second script, `scripts/ingest_one.py`, was added for ad-hoc single-item testing without touching the manifest (`--url` or `--file`, mutually exclusive). Both old scripts were deleted. Rationale: the manifest is the operator's source of truth and matches the shape the future `POST /v1/refresh` endpoint will reuse. Batch 3f docs now point at `ingest_all.py` / `ingest_one.py`.
- **`query_responses` schema consolidated** (2026-04-16). The five individual response columns (`answer text`, `citations jsonb`, `confidence text`, `retrieved_chunk_ids text[]`, `next_actions jsonb`) were collapsed into a single `response_payload jsonb` column. `status` remains a top-level column because it is indexed and filtered for analytics. Rationale: none of the collapsed columns were ever queried, filtered, or indexed independently — the separate columns added migration cost for every response shape change without providing any query benefit. The existing `0002.sql` migration was rewritten in place (no new migration). Matches the pattern used in itrstats-api's `assistant_query_responses` table.
- **Batch 3h: `/v1/refresh` renamed to `/v1/ingest`** (2026-04-16). The original plan called the endpoint `POST /v1/refresh`. During implementation, "ingest" was chosen as the canonical verb — it matches the project name (ContextIngest), the CLI script (`ingest_all.py`), the action module (`ingest_manifest.py`), and the domain language throughout the codebase. "Refresh" was too generic and implied cache invalidation semantics the endpoint doesn't have. Rate limiting deviation: the plan stated the IP/min middleware covers this route, but `IPRateLimitMiddleware` scopes to `/v1/query` and `/v1/feedback` only — `/v1/ingest` is exempt. Correct behavior: ingest is an operator action, and the content-hash gate already makes repeated calls free.
- **Safety classifier promoted from deferred to in-scope as Batch 3g** (2026-04-16). The original plan listed a pre-LLM safety gate as post-v0. Landed in a lightweight shape: two layers (regex heuristics + cheap LLM classifier) catching prompt injection and jailbreak attempts only, gated behind a single `SAFETY_ENABLED` toggle. Adds `"refused"` to `LLMAnswer.status`, a new `core/safety/` package mirroring the layering rules of `core/rate_limit/`, and two env vars under a new `SafetyConfig` (`SAFETY_ENABLED`, `SAFETY_LLM_MODEL`). No DB migration, no persistence of refused queries, no corpus-topic knob — off-topic questions flow through to the existing Batch 3b grounding guardrail which already returns `no_answer` when retrieval finds nothing relevant. Inserted **before** 3f so the contract change is shipped when the public docs describe it. Two earlier drafts (six-layer comprehensive; three-category with corpus topic) were rejected in favor of the current minimal surface. Full plan in [`batches/batch3/3g-safety-classifier.md`](./batches/batch3/3g-safety-classifier.md).

---

## How to update this plan

When a batch ships, change its status emoji at the top and add any deviations from the original plan in a "Deviations" subsection under that batch. When a non-goal becomes a goal, move it from "Out of scope" to a new batch. When a decision is reversed, leave the original row in the table and add a strikethrough — the history is the point.
