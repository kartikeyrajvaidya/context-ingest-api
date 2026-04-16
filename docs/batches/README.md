# Batch Status

Single source of truth for "where are we right now" in the ContextIngest API build-out. Update the status column and the "Last updated" line whenever a batch changes state; do not edit individual batch files just to change their status — this file wins.

For the *architectural plan* (stack, decisions, directory tree, non-goals), see [`../scaffolding-plan.md`](../scaffolding-plan.md). For the *per-batch detail* (goal, files, acceptance), open the linked batch file.

**Last updated:** 2026-04-16 — **3f shipped**, flipped to ✅. Two-layer safety gate (regex heuristics + cheap LLM classifier) catching prompt injection and jailbreak, gated behind `SAFETY_ENABLED`. All 8 acceptance tests pass (G1–G8): heuristic block, classifier injection/jailbreak, off-topic passes gate, safe in-scope, borderline legitimate, disabled toggle, fail-closed on classifier error. 3 layering checks clean (zero fastapi/openai/db imports in `core/safety/`). Also shipped in 3g: client-facing `status` field on `QueryResponseSchema` (`answered|no_answer|refused|error`) and `response_payload` JSONB consolidation on `query_responses` table. Next up: **3f** (public docs).

**Earlier:** 2026-04-16 — **3e shipped + acceptance pass complete**, flipped to ✅. `scripts/reembed_all.py` verified end-to-end: dry-run (18/18 chunks, 2.1s) → live (18/18 chunks, 2.4s across 4 batches of 5) → row count unchanged → retrieval healthy post-reembed. SQLAlchemy `text()` bind-param parser trips on `::vector` shorthand, so the bulk update uses `CAST(:emb AS vector)` instead. Initial Batch 3g plan also drafted (later rewritten — see above).

**Earlier still:** 2026-04-15 — **3d shipped + acceptance pass complete**, flipped to ✅. All three rate-limit layers verified end-to-end against the live compose stack: layer 1 (IP/min, in-memory middleware, `/v1/query` + `/v1/feedback` scoped, `/health` exempt, XFF per-IP isolation, Cloudflare header precedence, `Retry-After: 60`), layer 2 (session/hour, Postgres-backed, route-level check before action), layer 3 (conversation turns, Postgres-backed, first-turn short-circuit). WARNING log surface in place. `docker-compose.yaml` env wiring fixed to pipe all three new `RATE_LIMIT_*` vars into the container. Layering clean: zero `RateLimitConfig` refs in `core/actions/`, `core/rate_limit/` imports only `Request` from fastapi. Alongside 3d, **3a was consolidated post-ship**: `scripts/ingest_url.py` + `scripts/ingest_batch.py` were replaced with `scripts/ingest_all.py` (zero-arg, reads `data/sources.json`, handles URL + local-file entries) and `scripts/ingest_one.py` (ad-hoc single-item testing). The consolidation is recorded in `../scaffolding-plan.md` §Deviations. Next up: **3e** (reembed).

## Legend

| Symbol | Meaning |
|---|---|
| ✅ | Done — shipped on `main` and acceptance criteria met. |
| 🟡 | Done with caveats — shipped, but a follow-up PR is owed (see notes). |
| ⏳ | Next up — not started, but unblocked and ready to begin. |
| ⏸ | Paused — blocked on another batch. |
| ⬜ | Future — not yet scheduled. |

## Progress

| Batch | Status | Notes | File |
|---|---|---|---|
| 1 — Repo skeleton & meta docs | ✅ | README, ARCHITECTURE, LICENSE, Docker, env. | [1-repo-skeleton.md](./batch1/1-repo-skeleton.md) |
| 1.5 — OSS hygiene | ✅ | CoC, SECURITY, pyproject, pre-commit, CI, issue/PR templates. | [1.5-oss-hygiene.md](./batch1/1.5-oss-hygiene.md) |
| 2a — App skeleton (no schema, no tables) | ✅ | Reconciled on `main`: 0001 temporarily emptied; model bodies stripped to id-only stubs; Alembic wrapper tolerated empty SQL. Subsequently superseded by 2c, which overwrote `0001.sql` with the real schema once the "init" suffix was dropped. | [2a-app-skeleton.md](./batch2/2a-app-skeleton.md) |
| 2b — API contracts & schemas (contract-first) | ✅ | Both contracts frozen; schemas updated; `docs/api/{query,feedback}.md` shipped and linked from README. Feedback uses **replace semantics** (atomic upsert; carry-over to 2c = `UNIQUE(query_id)` + `created_at`→`updated_at`). | [2b-contracts-and-schemas.md](./batch2/2b-contracts-and-schemas.md) |
| 2c — Database schema & migrations | ✅ | Live-verified 2026-04-15: `docker compose up --build` on a fresh volume applied `0001.sql` and `0002.sql` clean, Alembic ran both migrations, API booted. | [2c-migrations-and-tables.md](./batch2/2c-migrations-and-tables.md) |
| 3a — Ingestion pipeline (CLI-only) | ✅ | Shipped + acceptance pass 2026-04-15. Fetcher, cleaner (HTML + markdown), recursive chunker, rerun-safe pipeline, action owning the transaction, OpenAI embeddings adapter with sub-batch splitting. CLI subsequently consolidated to `scripts/ingest_all.py` (manifest-driven, reads `data/sources.json`) + `scripts/ingest_one.py` (ad-hoc single item); see scaffolding-plan §Deviations. | [3a-ingestion-pipeline.md](./batch3/3a-ingestion-pipeline.md) |
| 3b — Query path (retrieval + answer) | ✅ | Shipped + acceptance pass 2026-04-15. Hybrid retrieval (pgvector + tsvector + RRF), single-call structured-output `LLMAnswer`, two-write durable flow, multi-turn conversations with silent re-mint of stale `conversation_id`, grounding guardrail (refuse when context insufficient). | [3b-query-path.md](./batch3/3b-query-path.md) |
| 3c — Feedback | ✅ | Shipped + acceptance pass 2026-04-15. Real `POST /v1/feedback` with atomic replace semantics on `query_id` (PK preserved across upserts), 404 on unknown query, 400 validation errors. Action layer free of fastapi imports. | [3c-feedback.md](./batch3/3c-feedback.md) |
| 3d — Rate limiting | ✅ | Shipped + acceptance pass 2026-04-15. Three layers: IP/min in-memory middleware, session/hour Postgres, conversation-turn Postgres. All scoped to `/v1/query` (+ `/v1/feedback` for layer 1); `/health` exempt. `WEB_CONCURRENCY>1` startup warning. | [3d-ratelimit.md](./batch3/3d-ratelimit.md) |
| 3e — Reembed | ✅ | Shipped + acceptance pass 2026-04-15. `scripts/reembed_all.py` walks every chunk via keyset-paginated async generator, bulk-writes new embeddings per batch in a single `UPDATE ... FROM (VALUES ...)`. `--batch-size` + `--dry-run`. Manual pass on 18-chunk corpus: dry-run 2.1s, live 2.4s across 4 batches, retrieval verified post-reembed. | [3e-reembed.md](./batch3/3e-reembed.md) |
| 3g — Safety classifier | ✅ | Shipped + acceptance pass 2026-04-16. Two-layer pre-LLM gate (regex heuristics + LLM classifier), `SAFETY_ENABLED` toggle, client-facing `status` field on response, `response_payload` JSONB consolidation. | [3g-safety-classifier.md](./batch3/3g-safety-classifier.md) |
| 3h — Ingest endpoint | ✅ | Shipped + acceptance pass 2026-04-16. `POST /v1/ingest` — manifest-driven ingestion over HTTP. No request body, reads `data/sources.json`, rerun-safe. Returns `{"data": {"ok": true}}` on success, 500 on failure. Shared action in `core/actions/ingest_manifest.py` used by both route and CLI script. | [3h-refresh-endpoint.md](./batch3/3h-refresh-endpoint.md) |
| 3f — Public docs | ✅ | Shipped 2026-04-16. README + ARCHITECTURE refreshed, architecture docs (overview, schema, ingestion-pipeline, retrieval), guides (quickstart, ingestion, tuning-retrieval, self-hosting). No code changes. | [3f-docs.md](./batch3/3f-docs.md) |

## Currently in flight

All Phase 3 batches shipped. Next steps TBD.

## Blocked / open decisions

_None — all 2c design questions resolved on 2026-04-14. See [2c spec](./batch2/2c-migrations-and-tables.md#resolved-in-2c-2026-04-14)._

## How to update this file

- When a batch **starts**: flip its row to ⏳ → 🟡/✅ on completion, bump "Last updated".
- When a batch is **blocked**: set to ⏸, add a one-line note about what it's blocked on.
- When a decision above is **resolved**: delete the bullet (the commit history is the trail).
- When a new batch is **added**: append a row, cross-link from [`../scaffolding-plan.md`](../scaffolding-plan.md) §Batches.
- Do **not** duplicate per-batch detail here — link to the batch file instead.
