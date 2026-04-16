# Batch 3f — Public docs ✅

> **Status:** ✅ shipped 2026-04-16.
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Upstream:** every prior batch. 3f is the "close the loop" pass that turns shipped surfaces into something a stranger can adopt.
> **Skills consulted:** `context-ingest-api-backend`, `context-ingest-rag-pipeline`

## 1. Goal

After 3f, someone who has never seen this repo can:

1. Land on `README.md`, understand what ContextIngest is in under 60 seconds, and know which doc to open next.
2. Follow `docs/guides/quickstart.md` and have a running instance answering a query in under 10 minutes.
3. Self-host via `docs/guides/self-hosting.md` without reading source code.
4. Ingest their own corpus via `docs/guides/ingestion.md`.
5. Understand *why* retrieval works the way it does via `docs/architecture/retrieval.md`.
6. Tune grounding/retrieval knobs via `docs/guides/tuning-retrieval.md`.
7. Call both public endpoints from `docs/api/query.md` and `docs/api/feedback.md`.

3f ships docs only. No code, no schema, no dependency changes. If a doc reveals a bug, fix it in a separate commit — 3f does not silently bundle fixes.

## 2. Scope

### In

- `README.md` — rewrite the hygiene placeholder into a real landing page.
- `ARCHITECTURE.md` — refresh to match what shipped; pointer to `docs/architecture/overview.md` + 10-line module map + layering rules.
- `docs/api/query.md` — add `429` row, add "Multi-turn conversations" subsection matching 3b's silent re-mint + history cap, reorder example JSON to match `LLMAnswer` field order.
- `docs/api/feedback.md` — add `429` row, expand "Replace semantics" with the upsert SQL snippet showing which columns are preserved.
- `docs/architecture/overview.md` (new) — module layout, layering rules, request lifecycle swimlanes for `/v1/query` and `/v1/feedback`.
- `docs/architecture/ingestion-pipeline.md` (new) — fetch → clean → chunk → embed → persist flow, rerun safety via SHA-256, transaction boundary.
- `docs/architecture/retrieval.md` (new) — the load-bearing page. Hybrid retrieval end-to-end: embed → vector top-N + FTS top-N → RRF `1/(k+rank_vec) + 1/(k+rank_fts)` with `k=60` → top-M into context → `LLMAnswer` structured output → two-write durable persistence → grounding refusal.
- `docs/architecture/schema.md` (new) — tour of the five tables, index shapes (HNSW / GIN / b-tree), FK topology, the two-table `query_requests` + `query_responses` split, feedback upsert.
- `docs/guides/quickstart.md` (new) — 10-minute path from zero to a working query.
- `docs/guides/self-hosting.md` (new) — env vars, DB volume, reverse proxy (with `X-Forwarded-For` set for the rate limiter), log shipping, OpenAI budget, upgrade flow.
- `docs/guides/ingestion.md` (new) — operator manual for the manifest (`data/sources.json`) + `scripts/ingest_all.py` + `scripts/ingest_one.py`, content-hash rerun semantics, chunk-size guidance, inspection queries, when to run `reembed_all.py`.
- `docs/guides/tuning-retrieval.md` (new) — symptom → knob → env var → direction table. Covers `CHUNK_*`, `RRF_K`, `VECTOR_TOP_N`/`FTS_TOP_N`, `CONTEXT_TOKEN_BUDGET`, grounding refusal threshold, `CONVERSATION_HISTORY_TURN_LIMIT`.
- `CHANGELOG.md` — one `[Unreleased]` bullet listing the shipped docs.

### Out (deferred)

| Item | Why |
|---|---|
| Generated OpenAPI site (Redoc, Swagger) | Post-v0. Hand-written docs are the v0 contract. |
| Docs website (mkdocs, docusaurus, Astro) | Post-v0. Markdown renders fine on GitHub. |
| `docs/guides/deployment.md` | Deferred to end of batches per plan memory. |
| `docs/architecture/security.md` | No auth in v0 — a security doc would be a lie or a disclaimer. |
| Tutorial video / screencast | Out of scope. |
| Non-English translations | Out of scope. |
| Benchmarks (retrieval@k, latency p99) | No benchmark harness — made-up numbers are worse than none. |
| Comparison matrix vs. other RAG projects | Moving-target maintenance burden. |

## 3. Rules

1. **No code changes.** Docs-only batch. Bugs surfaced while writing docs go in a follow-up commit, linked from "Deviations".
2. **Docs match shipped behavior.** Every claim must be reproducible against the live compose stack on the day it's written. Unshipped behavior is marked "planned" with a link, never stated bare.
3. **Link, don't copy.** Contracts live in `docs/api/*.md`. Architecture docs link to them; they do not paraphrase.
4. **One source of truth per fact.** Retrieval is explained in `docs/architecture/retrieval.md`. Quickstart/README/tuning link to it and never re-explain RRF.
5. **Reader-first.** Every doc opens with "who this is for" and "what you'll be able to do after reading this".
6. **Terse beats thorough.** Public docs are the entry point; readers click through to batch files for depth.
7. **No aspirational diagrams.** Mermaid/ASCII only where they genuinely compress text.
8. **Hand-written markdown.** No mkdocs, docusaurus, sphinx, or RST.
9. **No emojis in public docs.** (Batch files can use ✅/⏳; reader-facing docs don't.)

## 4. Implementation order

Docs are written in dependency order so cross-links never point at placeholders.

1. **Architecture first.** `overview.md` → `schema.md` → `ingestion-pipeline.md` → `retrieval.md`.
2. **API polish.** `docs/api/query.md` and `docs/api/feedback.md` — light edits.
3. **Guides.** `quickstart.md` → `ingestion.md` → `tuning-retrieval.md` → `self-hosting.md`.
4. **Entry points last.** `README.md` and `ARCHITECTURE.md` link everywhere — written last so links land on real content.
5. **CHANGELOG.** Single `[Unreleased]` bullet.
6. **Acceptance pass (§9).**

## 5. File-by-file

### 5.1 `docs/architecture/overview.md`

The architectural TOC. Sections: (1) what this service is in two sentences; (2) module layout — tree of `api/`, `core/`, `db/`, `configs/`, `scripts/`, `libs/` with one-line purposes; (3) the nine layering rules (no `fastapi` in `core/`, no `db/` in `core/services/`, no `openai` outside `core/services/`, env only in `configs/`, prompts only in `core/services/prompts.py`, etc.) — literal list, future PRs grep for it; (4) request lifecycle for `POST /v1/query` as an ASCII swimlane HTTP → middleware → route → action → services → models → DB; (5) request lifecycle for `POST /v1/feedback` — shorter; (6) ingestion is CLI-only in v0, pointer to `ingestion-pipeline.md`; (7) further reading links.

ASCII swimlanes preferred (render in terminal `cat` + on GitHub).

### 5.2 `docs/architecture/schema.md`

Tour of the database. One subsection per table (`documents`, `chunks`, `query_requests`, `query_responses`, `feedback`) with columns, FKs, indexes, "why it looks like this". Separate sections for: index shapes (HNSW vector, GIN tsvector, b-tree timestamps), the two-write durable flow motivation for `query_requests` + `query_responses`, feedback upsert SQL preserving `id` + `created_at`, retention guidance (nothing deleted in v0; operators can `DELETE FROM query_requests WHERE created_at < ...` and FK cascades handle the rest).

### 5.3 `docs/architecture/ingestion-pipeline.md`

The 3a pipeline explained for someone who won't read the batch file. Sections: (1) why CLI-only in v0; (2) the five stages (fetch / clean / chunk / embed / persist), each with input, output, failure modes, recovery — no code; (3) rerun safety via SHA-256 content hashing, why a URL change produces a new row rather than a mutation; (4) error semantics, how `status: "failed"` maps to non-fatal errors and when an exception bubbles; (5) "when to rerun", link to `docs/guides/ingestion.md`.

### 5.4 `docs/architecture/retrieval.md`

The most load-bearing page — most likely to be shared standalone, so the opening paragraph must stand on its own.

Sections: (1) who this doc is for; (2) the full flow as a numbered 8-step list; (3) hybrid retrieval — the `Chunk.hybrid_search` CTE copied verbatim from `db/models/chunks.py` with inline comments, why two CTEs, why `FULL OUTER JOIN`, why `LIMIT 20` per branch; (4) RRF — the `1/(k+rank_vec) + 1/(k+rank_fts)` formula, why `k=60` (TREC default), why rank-based fusion dodges the "vector and ts_rank aren't on the same scale" problem, what alternatives would cost; (5) context assembly — `CONTEXT_TOKEN_BUDGET`, how chunks are stitched, what happens when one chunk exceeds the budget; (6) LLM call — single call, `LLMAnswer` structured output, why single-call not retrieve-then-critique, why `next_actions` is capped at 3; (7) grounding refusal — when the LLM returns `status: "no_answer"` and why the server trusts it; (8) multi-turn — `session_id`, `conversation_id`, silent re-mint, history cap; (9) knob reference table pointing each decision at its env var → `tuning-retrieval.md`.

### 5.5 `docs/api/query.md` (polish)

- Add a `429 — Rate limit exceeded` row to the responses table.
- Add a "Multi-turn conversations" subsection: `session_id` as a client-supplied opaque string, `conversation_id` supplied or server-minted, silent re-mint on stale `conversation_id` (not a 400), `CONVERSATION_HISTORY_TURN_LIMIT` cap (default 10).
- Reorder example JSON to match `LLMAnswer` field order: `status`, `answer`, `citations`, `next_actions`, `session_id`, `conversation_id`, `query_id`.
- No changes to field semantics.

### 5.6 `docs/api/feedback.md` (polish)

- Add a `429 — Rate limit exceeded` row.
- Expand "Replace semantics" with a two-line SQL snippet showing preserved (`id`, `created_at`) vs advanced (`rating`, `reason`, `updated_at`). Link to `schema.md` §Feedback.
- Retain rating-vocabulary block verbatim.
- No changes to field semantics.

### 5.7 `docs/guides/quickstart.md`

Zero-to-one in ten minutes for someone with Docker and an OpenAI key.

Sections: (1) what you'll have at the end, with one example response; (2) prerequisites — Docker Desktop, OpenAI key, ports 8050 and 5433 free; (3) clone + configure — `git clone`, `cp .env.example .env`, drop in the key; (4) boot — `docker compose up --build`, expected log lines; (5) ingest the demo corpus via `docker compose exec context-ingest-api python -m scripts.ingest_all` (reads `data/sources.json`), with a note that ad-hoc one-offs use `python -m scripts.ingest_one --url ...` or `--file ...`; (6) ask a question with one `curl`, expected truncated response, pointers for which fields to inspect; (7) record feedback with one `curl`; (8) what's next — links to the other three guides.

Every command is copy-pasteable. Tested end-to-end on a fresh machine before merge (§9 D1).

### 5.8 `docs/guides/self-hosting.md`

Sections: (1) who this is for; (2) env vars grouped (DB, LLM, retrieval, rate limiting, chunking) — each row: name, default, purpose, where read; (3) volume + backup, one paragraph on why `query_responses` is the audit table; (4) reverse proxy — sample nginx block terminating TLS in front of `:8050` with `X-Forwarded-For` set so the 3d rate limiter sees the real client IP; (5) log shipping — `docker logs` or mount `/var/log`; (6) OpenAI budget — rough back-of-envelope pointing at OpenAI's pricing page; (7) upgrade flow — `git pull && docker compose up --build -d`; (8) what this guide does not cover (TLS cert provisioning, Kubernetes, cloud-provider specifics).

### 5.9 `docs/guides/ingestion.md`

Sections: (1) the manifest + two scripts — `data/sources.json` as the operator's source of truth (each entry has `url`, optional `title`, and optional `file` for local content under a synthetic `knowledge://...` identifier), `scripts/ingest_all.py` as the zero-arg manifest-driven ingester ("add a line, run the script"), and `scripts/ingest_one.py` for ad-hoc single-item testing (`--url` or `--file`, mutually exclusive) without touching the manifest — with example invocations for both; (2) the content-hash gate, when rerunning is free and when it isn't (the manifest is safe to re-run every deploy); (3) chunk-size guidance (short pages → smaller chunks, API reference → smaller with more overlap, long-form prose → larger) — reference-only, actual knobs live in `tuning-retrieval.md`; (4) inspection queries — three `psql` queries operators actually run (count per domain, chunks per doc, most recent ingested); (5) when to run `scripts/reembed_all.py` — after a chunker change or embedding model bump, link to 3e; (6) failure handling — what `status: "failed"` in `documents` means, how to see the error, how to retry.

### 5.10 `docs/guides/tuning-retrieval.md`

Sections: (1) how to tell something is wrong — three symptoms (answers shallow, wrong chunk cited, refuses when it shouldn't); (2) knob reference table — symptom → knob → env var → direction (covers `CHUNK_SIZE_TOKENS`, `CHUNK_OVERLAP_TOKENS`, `RRF_K`, `VECTOR_TOP_N`/`FTS_TOP_N`, `CONTEXT_TOKEN_BUDGET`, grounding refusal threshold, `CONVERSATION_HISTORY_TURN_LIMIT`); (3) one paragraph per knob — what it does and when to touch it; (4) when to reach for `reembed_all.py`, link to 3e; (5) what the feedback table is for — the thumbs-up/down signal is the intended input to manual tuning decisions.

### 5.11 `README.md` (rewrite)

Replaces the pre-3a hygiene placeholder. ≤200 lines.

Sections: (1) tagline — one sentence; (2) what this is in 60 seconds — three bullets; (3) what this is *not* — three bullets (not a hosted product, not a vector DB, not a LangChain replacement); (4) 30-second quickstart — the three shell commands, pointer to the full guide; (5) where to go next — small table "I want to ___ / read ___"; (6) repo status — link to `docs/batches/README.md`; (7) license (MIT); (8) community — CoC + SECURITY + CONTRIBUTING links.

### 5.12 `ARCHITECTURE.md` (refresh)

Sections: (1) one-sentence "the real architecture lives at `docs/architecture/overview.md`"; (2) 10-line module map; (3) the nine layering rules, duplicated from overview — the one intentional violation of Rule 4, because contributors look here first; (4) links to deep-dive pages.

### 5.13 `CHANGELOG.md`

One bullet under `[Unreleased] → Added`:

> Public documentation (Batch 3f): `README.md` and `ARCHITECTURE.md` refreshed; new `docs/architecture/{overview,ingestion-pipeline,retrieval,schema}.md`; new `docs/guides/{quickstart,self-hosting,ingestion,tuning-retrieval}.md`; `docs/api/{query,feedback}.md` polished for 3d rate-limiting and 3b multi-turn behavior. No code changes.

## 6. Contract / logging / DB / config / deps

**None.** Docs-only batch. Contract, log surface, DB, env vars, and dependencies are all byte-identical before and after 3f. The only additive changes to contract docs are the `429` row and the multi-turn subsection, both describing behavior that already shipped.

## 7. Acceptance test

The bar for a docs batch is "would a stranger succeed by following this?". Partial automation only.

### Preconditions

A clean checkout of `main` with 3a–3e shipped. `docker compose down -v && docker compose up --build -d` produces a running API on `:8050` and Postgres on `:5433`. A scratch directory on a machine that has Docker + an OpenAI key and has never seen this repo.

### Test cases

**D1. Quickstart dry-run on a clean machine.** Follow `docs/guides/quickstart.md` line by line. Every command must succeed. Final `curl POST /v1/query` returns `200` with non-empty `answer` and ≥1 `citation`. No "figure out X yourself" moments.

**D2. Self-hosting env-var round trip.** Pick one env var from each of the five groups (`POSTGRES_PASSWORD`, `OPENAI_API_KEY`, `RRF_K`, `RATE_LIMIT_IP_PER_MINUTE`, `CHUNK_SIZE_TOKENS`). For each, grep for its default in `configs/*.py` and confirm the doc's "default" column matches.

**D3. Links resolve.** `rg -o 'docs/[a-z/]+\.md' docs/ README.md ARCHITECTURE.md | xargs -I{} test -f {}`. Every internal link points at an existing file.

**D4. Retrieval doc matches the code.** The SQL block in `docs/architecture/retrieval.md` must match `db/models/chunks.py` `hybrid_search` verbatim (modulo whitespace). `k=60` must match `RRF_K`'s default in `configs/*.py`.

**D5. Tuning guide knobs exist.** Every env var mentioned in `docs/guides/tuning-retrieval.md` grep-matches a real `os.getenv(...)` call in `configs/*.py`. Aspirational knobs get cut.

**D6. API docs reachable from README in ≤2 clicks.** Every 3f doc is reachable in ≤2 clicks from `README.md`.

**D7. No implementation jargon in guides.** `rg -i 'fastapi|pydantic|httpexception|asyncsession' docs/guides/` → zero hits. (Architecture pages can use these freely.)

**D8. No stale "planned" claims.** `rg 'planned|TBD|TODO|coming soon' docs/api/ docs/architecture/ docs/guides/` → zero hits for anything that already shipped. The only tolerated occurrences are forward links to `docs/batches/*`.

**D9. Layering rules consistent.** `docs/architecture/overview.md`, `ARCHITECTURE.md`, and `skills/context-ingest-api-backend/*` carry the same nine rules (wording can vary; the rules cannot).

**D10. CHANGELOG bullet covers every file.** The `[Unreleased]` bullet from §5.13 names every file created or touched.

## 8. Rollout / rollback

**Commits:**
1. `docs(architecture): add overview, schema, ingestion-pipeline, retrieval`
2. `docs(api): polish query and feedback contracts for 3d/3b behavior`
3. `docs(guides): add quickstart, self-hosting, ingestion, tuning-retrieval`
4. `docs: refresh README and ARCHITECTURE as entry points`
5. `docs/CHANGELOG: record 3f`

Commit 4 goes last because it's what a reader sees first.

**Rollback.** Additive except the README + ARCHITECTURE rewrites. `git revert` per commit backs out the batch; reverting the rewrite commit restores the hygiene placeholder. Zero DB/config/dep impact. No compose restart needed.

## 9. Deviations from this plan

**Kept crisp.** The original plan called for very detailed docs with ASCII swimlanes, SQL blocks copied verbatim from source, and 9-rule layering lists duplicated across files. The shipped docs are deliberately shorter and more scannable — link-heavy, no duplication. Reader can click through for depth.

**`docs/api/ingest.md` shipped in 3h.** The plan listed it under 3f scope, but it was created alongside the endpoint in Batch 3h.

**No `docs/guides/deployment.md`.** Deferred per project memory. `self-hosting.md` covers the essentials.
