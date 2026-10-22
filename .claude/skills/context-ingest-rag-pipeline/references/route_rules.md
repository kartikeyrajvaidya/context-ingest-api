# RAG Route Rules

This file is the index of every public RAG route. Read it first when adding a new route, modifying an existing one, or wiring a new behavior into an existing one.

For per-route safety rules, see `guardrail_rules.md`.

## Concepts

The query side of the pipeline uses a three-stage flow:

```
embed question  →  hybrid retrieve  →  compose answer
```

- The **embedding stage** turns the question into a vector using `core/services/embeddings.py`.
- The **retrieval stage** runs vector kNN and full-text search in parallel, then fuses with Reciprocal Rank Fusion in `core/retrieval/hybrid.py`.
- The **compose stage** takes the top-K chunks, builds a prompt, calls the LLM, attaches citations, and returns an answer.

The ingestion side has its own four-stage flow described in `../../../docs/architecture/ingestion-pipeline.md` (fetch → clean → chunk → embed+persist).

The flow is the contract between layers. New capabilities are added by extending one stage explicitly, not by piling logic into another.

## Active routes

| Route | Method | Path | Action | Factual source | LLM function | Composer | Rule file |
|---|---|---|---|---|---|---|---|
| Query | POST | `/v1/query` | `query_document` | retrieved `chunks` (hybrid RRF) | `generate_answer` | `build_answered_response` | [contract_rules.md](./contract_rules.md), [guardrail_rules.md](./guardrail_rules.md) |
| Feedback | POST | `/v1/feedback` | `record_feedback` | n/a (writes only) | n/a | n/a | [contract_rules.md](./contract_rules.md) |

## Ingestion (no HTTP route in v0)

Ingestion has **no public HTTP route** in v0. It is driven from `scripts/ingest_url.py` and `scripts/ingest_batch.py`, both of which call `core/actions/ingest_document.ingest_document` directly. The rationale and the future "manifest-triggered refresh endpoint" design are recorded in `../../../docs/scaffolding-plan.md`.

Implementation rules still apply to the action and the pipeline modules even though there is no route wrapping them:

- The action owns the transaction.
- Pipeline modules (`core/ingestion/`) are pure-ish stages that take typed inputs and return typed outputs.
- One success log per ingestion run, emitted by the action — not by the scripts or by pipeline modules.
- Non-fatal failures (`FetchError`, `EmptyContentError`) are mapped to `status: "failed"` in the response schema. Everything else propagates.

Do not scaffold a `/v1/ingest` or `/v1/refresh` route in the current batch. The first such route lands only in the batch that explicitly activates the manifest-driven refresh feature.

## Factual source rule

The query route has exactly one primary factual source: the retrieved chunks for that question. The composer must:

- ground every claim in the answer in at least one retrieved chunk
- attach a citation for every chunk used
- not invent URLs, document titles, or chunk content

If retrieval returns nothing, the composer returns a low-confidence "not enough information" answer without calling the LLM. This is the single most important safety rule on the query path — break it and the bot starts hallucinating.

## System prompt rule

Each route that calls the LLM has its own system prompt. System prompts live in `core/services/prompts.py` only — never in routes, actions, or pipeline modules.

| Route | System prompt builder |
|---|---|
| `/v1/query` | `build_query_answer_system_prompt` |

The user prompt builder for retrieval answers includes the retrieved chunks as bracketed context with stable IDs, so the LLM can cite them by ID.

## Composer rule

The query route has its own composer in `core/orchestrator/answer_composer.py`. The composer:

- builds the user prompt from retrieved chunks
- calls the LLM via `core/services/llm.py`
- parses the response
- attaches citations from the retrieved chunks
- decides confidence based on retrieval signal strength

Do not branch the composer on additional intents in the current batch. If a future batch adds a second answer shape, write a second composer function. Conditional logic inside one composer becomes unmaintainable as routes accumulate.

## Persistence

All operations persist through the same flow:

- ingest (CLI-driven): writes to `documents` and `chunks` in one transaction
- query: writes to `queries` (request, answer, retrieved chunk IDs, latency) after composing
- feedback: writes to `feedback` (query_id, rating, reason)

Do not add per-route persistence wrappers. The shared persistence is intentional and decoupled from route logic.

## Rate limiting

Rate limiting is route-agnostic and runs before the route handler:

- Per-IP-per-minute (in-memory) in `IPRateLimitMiddleware`

See `configs/rate_limit.py` for the env-var knobs and `core/rate_limit/` for the implementation. Do not add per-route rate limits in the current batch.

## Adding a new route — checklist

Before opening a code change for a new route:

1. Confirm the new route's batch is the active batch in `phase_rules.md`. If not, stop.
2. Add a row to the table at the top of this file.
3. Update `contract_rules.md` with the new request/response shape.
4. Update `guardrail_rules.md` if the new route has any safety implications.
5. Update the SKILL.md reference map if a new rule file is needed.
6. Then proceed through the implementation steps in the batch's plan.

This sequence keeps the rule surface in sync with the code surface. Skipping it leads to drift, and drift in a RAG pipeline is what produces wrong answers.
