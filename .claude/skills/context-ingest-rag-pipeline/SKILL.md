---
name: context-ingest-rag-pipeline
description: Use when planning or implementing the RAG ingestion, retrieval, prompts, or answer composition. Enforces schema-first contracts, guardrails, prompt discipline, retrieval boundaries, and eval/tracing rules.
---

# RAG Pipeline Skill

## When To Use

Use this skill for any work related to the retrieval-augmented generation pipeline, especially when touching:

- `POST /v1/query` — query route, retrieval, answer composition, action
- `POST /v1/feedback` — feedback route, action, persistence
- ingestion (CLI in v0, future manifest-triggered refresh endpoint) — `core/actions/ingest_document.py`, pipeline modules in `core/ingestion/`, and the wrapper scripts in `scripts/`
- retrieval modules (`core/retrieval/`)
- orchestrator and answer composer (`core/orchestrator/`)
- prompt files and LLM service adapter (`core/services/prompts.py`, `core/services/llm.py`)
- embeddings service (`core/services/embeddings.py`)
- response contracts, evals, or tracing related to the above

This skill is the implementation guardrail for the RAG side of the repo.

## Required Companion Skill

This skill assumes the generic backend rules still apply.

Also read:

- `../context-ingest-api-backend/SKILL.md`

Use this RAG skill for pipeline-specific constraints, and the backend skill for FastAPI, layering, migration, and logging conventions.

## Non-Negotiables

- Keep the source of truth in sync with `../../docs/scaffolding-plan.md` and `../../docs/api/`.
- The v0 public HTTP endpoints are `POST /v1/query` and `POST /v1/feedback`. Do not add new public endpoints in the current batch. Ingestion is a CLI-only operator action in v0 (`scripts/ingest_url.py`, `scripts/ingest_batch.py`). A future batch may add a manifest-triggered refresh endpoint; until that batch is active, do not scaffold a `/v1/ingest` or `/v1/refresh` route.
- The current implementation target is the active batch named in `references/phase_rules.md`. Implement only what that batch requires.
- Each query route has one factual source of truth: retrieved chunks from `chunks` (filtered by document, relevance, or recency). Do not invent additional sources.
- The query answer composer must ground its answer in retrieved chunks. If retrieval returns nothing or everything is below the relevance threshold, return a low-confidence "not enough information" answer — do not call the LLM without grounding.
- Keep request and response contracts schema-first and explicit.
- Do not add generic `context`, `metadata`, conversation memory, streaming, or out-of-batch features.
- Do not expose internal-only fields like `retrieved_chunk_ids` or raw `embedding` vectors in the public response unless the contract changes first.
- Do not let the model invent citations, URLs, or source titles that are not in the retrieval result.
- Do not let prior conversation history (when a future batch adds it) override current-turn safety rules.

## Workflow

1. Read `../../docs/scaffolding-plan.md`.
2. Read `../../ARCHITECTURE.md` for the request flow you are touching.
3. Read only the reference files needed for the current task.
4. Implement the smallest pipeline change that satisfies the active batch.
5. Validate contract compliance, batch compliance, and safety behavior.
6. Update docs first if a contract or batch boundary changes.

## Reference Map

- `references/phase_rules.md`
  Use for rollout boundaries, current batch target, and what must not be implemented early.

- `references/route_rules.md`
  Use as the index of all RAG routes, what each one owns, the factual source each uses, and the composer + disclaimer each uses. Read this first when adding or modifying any RAG route.

- `references/contract_rules.md`
  Use when adding or changing a request or response schema for any RAG route.

- `references/guardrail_rules.md`
  Use for unsupported prompts, refusal rules, cross-route safety, and the per-route safety pointer table.

- `references/knowledge_base_rules.md`
  Use when authoring or editing internal reference content that gets ingested.

- `references/prompt_eval_rules.md`
  Use when adding prompts, LLM calls, traces, or evaluation coverage.

## Working Style

- Keep `api/routes/{ingest,query,feedback}.py` thin.
- If request-envelope parsing or validation logic starts to make the route noisy, move that complexity into the action or orchestrator layer.
- Put business orchestration in `core/actions/` and `core/orchestrator/`.
- Keep deterministic computations (hashing, chunk math, RRF fusion) in their own modules under `core/ingestion/` or `core/retrieval/`.
- Put DB fetch helpers on the model class for that table, not in route or generic helper files.
- Keep prompt text out of routes, actions, and tool files — only `core/services/prompts.py` contains prompt strings.
- Keep response shaping product-controlled and explicit.
- Prefer narrow changes over RAG-platform building.

## Output Expectations

When using this skill, changes should produce:

- a narrow diff
- exact batch compliance
- explicit request and response contract compliance
- grounded answers (every claim traceable to a retrieved chunk)
- clear safety boundaries
- traceable request execution without speculative infrastructure
