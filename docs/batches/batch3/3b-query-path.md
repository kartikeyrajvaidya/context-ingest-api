# Batch 3b — Query path (retrieval + answer composition) ✅

> **Status:** ✅ shipped + acceptance pass 2026-04-15.
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Upstream contracts:** [`../batch2/2b-contracts-and-schemas.md`](../batch2/2b-contracts-and-schemas.md), [`../../api/query.md`](../../api/query.md), [`../batch2/2c-migrations-and-tables.md`](../batch2/2c-migrations-and-tables.md)
> **Skills consulted:** `context-ingest-api-backend`, `context-ingest-rag-pipeline`

## 1. Goal

`POST /v1/query` returns a grounded, cited answer with a confidence label and up-to-three suggested follow-ups. Multi-turn conversations work by echoing the returned `conversation_id`. Every request round-trips through the two-write flow: a `query_requests` row is written **before** retrieval, a `query_responses` row is written **after** the LLM call, and a crash between the two leaves a durable "we were asked this" record that the history fetcher skips over.

Batch 3b ships the query path only. Feedback is 3c; rate limiting is 3d; re-embedding is 3e; public docs are 3f.

## 2. Scope

### In

- `POST /v1/query` — replaces the 501 stub in `api/routes/query.py`.
- `core/actions/query_document.query_document(request)` — owns the two transaction boundaries.
- `core/services/retrieval.py` — embeds the question, calls `Chunk.hybrid_search`, maps rows to `RetrievedChunk`.
- `core/services/llm.py` — single `generate_answer(...)` call via OpenAI structured output.
- `core/services/prompts.py` — system/user prompt builders, chunk renderer, token-budget trimmer.
- `core/services/openai_client.py` — shared `AsyncOpenAI` factory. Extracted now because 3b is the second concrete use case (the phase rule's extraction trigger).
- `core/schema/llm_answer.py` — internal structured-output schema.
- `core/services/embeddings.py` — swap inline client for the new factory.
- CHANGELOG entry.

### Out (deferred)

| Item | Where |
|---|---|
| `POST /v1/feedback`, `record_feedback` action | Batch 3c |
| Real IP rate limiter | Batch 3d |
| `scripts/reembed_all.py` | Batch 3e |
| Public docs / architecture refresh | Batch 3f |
| Query rewriting against history before retrieval | Post-v0 |
| Decomposition / sub-query fan-out | Post-v0 |
| Streaming response variant | Non-goal for v0 |
| Numeric grounding score threshold | The LLM's `answer: null` is the guardrail |
| `core/retrieval/` subpackage | Dropped — `Chunk.hybrid_search` already owns the SQL |
| `core/orchestrator/answer_composer.py` | Dropped — one response shape, mapping is inline |

## 3. Rules

1. **Layering.** Routes never import `core/services/` or `db/`. Actions never import `fastapi`. Services import models only via narrow classmethods (`Chunk.hybrid_search`, `QueryRequest.generate_conversation_id`, etc.). `openai` is imported only from `core/services/`. Env vars only in `configs/`. Prompt text only in `core/services/prompts.py`.
2. **Two-write transaction boundary.** The action runs two separate `commit_transaction_async()` blocks — one around the `query_requests` insert, one around the `query_responses` insert. Retrieval and the LLM call happen between the two, with no session held open. A crash mid-pipeline leaves a dangling request row that `fetch_recent_completed_turns` filters out.
3. **Contract-first.** The frozen `QueryRequestSchema` / `QueryResponseSchema` in `core/schema/query.py` are the only public shapes. The LLM's structured output is an internal type (`LLMAnswer`) that never escapes `core/services/`.
4. **Grounding guardrail.** No answer without citations. Zero chunks → short-circuit to no-answer without calling the LLM. `LLMAnswer.answer=null` is honored verbatim. No text-level heuristics.
5. **Narrow diff.** One new abstraction in this batch (`openai_client.py`), and only because Batch 3a pinned the extraction to "second concrete use case".
6. **Logging.** Four INFO lines per request, warnings on the two catchable failure modes. Never log `question`, `answer`, `chunk_text`, conversation history, or embedding vectors. The DB is the audit log.
7. **Prompts are server-owned.** `top_k`, `history_turns`, `next_actions_count` are server-side knobs per the 2b contract. Request-field versions are a contract violation.
8. **No retries.** Parse failures fall back to no-answer. Timeouts propagate and become 500 — the operator can replay.
9. **No migrations.** 2c shipped the entire query path schema.

## 4. Implementation order

1. `core/schema/llm_answer.py`.
2. `core/services/openai_client.py`; migrate `embeddings.py` off its inline client.
3. `core/services/prompts.py`.
4. `core/services/llm.py`.
5. `core/services/retrieval.py`.
6. `core/actions/query_document.py`.
7. Rewrite `api/routes/query.py`.
8. `CHANGELOG.md` under `[Unreleased]`.
9. Manual acceptance pass (§11).

## 5. File-by-file

### 5.1 `core/schema/llm_answer.py`

The Pydantic model `client.responses.parse(...)` returns. Internal to `core/services/` — the action maps it to `QueryResponseSchema` before returning. Split from the public schema so the LLM can only decide `answer`, `confidence`, `next_actions`; `query_id`, `session_id`, `conversation_id`, and `citations` are assembled server-side from known state.

```python
"""Internal structured-output schema for answer composition."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LLMAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str | None = Field(
        description=(
            "Final grounded answer in the user's language. MUST be null when "
            "the retrieved chunks do not contain enough information to answer. "
            "Never an empty string — use null for no-answer."
        ),
    )
    confidence: Literal["high", "medium", "low"]
    next_actions: list[str] = Field(
        default_factory=list,
        max_length=3,
        description=(
            "0–3 suggested follow-up questions grounded in the retrieved chunks. "
            "Empty when answer is null or the context is too thin."
        ),
    )
```

### 5.2 `core/services/openai_client.py`

Memoized `AsyncOpenAI` factory — the single place the codebase constructs an OpenAI client. Batch 3a deferred this; 3b is the second use case that triggers the extraction.

```python
"""Shared async OpenAI client factory."""

from openai import AsyncOpenAI

from configs.llm import LLMConfig

_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is not None:
        return _client
    if not LLMConfig.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    _client = AsyncOpenAI(
        api_key=LLMConfig.OPENAI_API_KEY,
        timeout=LLMConfig.OPENAI_TIMEOUT_SECONDS,
    )
    return _client
```

Raises on missing `OPENAI_API_KEY` on first call, not at import, so lint-only CI runs without a key still work.

**Migration of `embeddings.py`.** Replace `AsyncOpenAI(api_key=..., timeout=...)` with `client = get_openai_client()`. Everything else (sub-batching, ordering guarantee, empty-input guard) unchanged.

### 5.3 `core/services/prompts.py`

The only module in 3b that hardcodes prompt text. Public surface:

```python
def build_answer_system_prompt() -> str: ...
def build_answer_user_prompt(
    question: str,
    conversation_turns: list[dict],
    retrieved_chunks: list[RetrievedChunk],
) -> str: ...
```

**System prompt (verbatim — this is the load-bearing artifact):**

```
You are the answer-generation layer for ContextIngest — a grounded,
citation-first question-answering service.

IDENTITY CONSTRAINT: You have no domain knowledge of your own. Your only
information source is the <retrieved_context> section in the user prompt.
If the retrieved context does not contain the answer, you genuinely do
not know it.

## Role
You answer one question per call, using ONLY the retrieved source
material. You cite your sources naturally in prose ("According to
<title>, ..."). You never invent facts, URLs, titles, or numbers.

## The answer field
- Write 2–4 short paragraphs or bullets grounded in the retrieved chunks.
- Lead with the direct answer; follow with supporting detail.
- Use the chunks' own words where precision matters, paraphrase otherwise.
- Set answer=null if and only if the retrieved context does not contain
  the information needed to answer the question. Never write an empty
  string. Never hedge with "I don't have enough information" as the
  answer text — use null instead.

## The confidence field
- "high": the retrieved chunks directly and unambiguously answer.
- "medium": the chunks cover the topic but require synthesis or partial
  inference.
- "low": the chunks are tangentially related, or you are setting
  answer=null.

## The next_actions field
- 0–3 follow-up questions the user could ask next.
- Each is a complete first-person question (≤60 chars).
- Each must be answerable from the SAME retrieved chunks.
- Do not repeat the question just asked.
- Empty list when answer=null or the context is too narrow.

## Conversation history
- You may receive up to N prior turns from the same conversation.
- Use them only to resolve references ("that", "it", "the second one").
- Do not treat prior assistant claims as ground truth — the retrieved
  context is the only authority.

## Safety
- No personalized legal, medical, financial, or tax advice unless the
  retrieved context explicitly provides it.
- No speculation about topics the chunks do not cover.
- No mention of internal field names, table names, or implementation
  details.

Return only the structured output matching the schema.
```

**User prompt shape:**

```
<request_context>
conversation_turns: {N}
current_date: {YYYY-MM-DD}
</request_context>

<conversation_context>
{rendered history or "none"}
</conversation_context>

<retrieved_context>
{rendered chunks}
</retrieved_context>

<user_question>
{question}
</user_question>
```

**Private helpers:**
- `_build_conversation_context(turns)` — renders `<turn_1>…<turn_N>` blocks with `user_question`, `assistant_answer`, `assistant_status`. Returns `"none"` on empty.
- `_format_retrieved_context(chunks)` — renders `<source_i>` blocks with `title`, `url`, and chunk text.
- `_fit_chunks_to_budget(chunks, encoding)` — drops lowest-scored chunks until the formatted context fits `_CONTEXT_TOKEN_BUDGET = 50_000` tokens. Emits one WARNING per drop.
- `_PROMPT_ENCODING = tiktoken.get_encoding("cl100k_base")` — module-level, reused.

Budget is a module-level constant, not env-configurable — one consumer, no second use case.

### 5.4 `core/services/llm.py`

```python
"""Answer-composition LLM service."""

from configs.llm import LLMConfig
from core.schema.llm_answer import LLMAnswer
from core.schema.retrieval_result import RetrievedChunk
from core.services.openai_client import get_openai_client
from core.services.prompts import (
    build_answer_system_prompt,
    build_answer_user_prompt,
)


class LLMParseError(Exception):
    """Non-fatal LLM failure: structured output did not parse."""


async def generate_answer(
    question: str,
    conversation_turns: list[dict],
    retrieved_chunks: list[RetrievedChunk],
) -> LLMAnswer:
    client = get_openai_client()
    response = await client.responses.parse(
        model=LLMConfig.OPENAI_ANSWER_MODEL,
        input=[
            {"role": "system", "content": build_answer_system_prompt()},
            {
                "role": "user",
                "content": build_answer_user_prompt(
                    question=question,
                    conversation_turns=conversation_turns,
                    retrieved_chunks=retrieved_chunks,
                ),
            },
        ],
        text_format=LLMAnswer,
    )
    if response.output_parsed is None:
        raise LLMParseError("LLM answer response did not include parsed output")
    return response.output_parsed
```

No retries. Timeouts propagate; the action catches `LLMParseError` only and maps it to no-answer.

### 5.5 `core/services/retrieval.py`

```python
"""Hybrid retrieval service — thin wrapper over Chunk.hybrid_search."""

from configs.llm import LLMConfig
from core.schema.retrieval_result import RetrievedChunk
from core.services.embeddings import embed_texts
from db.models.chunks import Chunk
from libs.logger import get_logger

logger = get_logger(__name__)


async def retrieve_relevant_chunks(question: str) -> list[RetrievedChunk]:
    [query_embedding] = await embed_texts([question])
    rows = await Chunk.hybrid_search(
        query_embedding=query_embedding,
        question=question,
        vector_candidates=LLMConfig.RETRIEVAL_VECTOR_CANDIDATES,
        fulltext_candidates=LLMConfig.RETRIEVAL_FULLTEXT_CANDIDATES,
        top_k=LLMConfig.RETRIEVAL_TOP_K,
    )
    results = [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            chunk_order=row.chunk_order,
            text=row.chunk_text,
            source_url=row.source_url,
            title=row.document_title,
            ingested_at=row.last_ingested_at,
            score=float(row.rrf_score),
        )
        for row in rows
    ]
    logger.info(
        "Retrieved %d chunks for question top_score=%.4f",
        len(results),
        results[0].score if results else 0.0,
    )
    return results
```

Reuses `embed_texts` with a single-item list. No retries; DB/embedding failures propagate to the action.

### 5.6 `core/actions/query_document.py`

Owns both transaction boundaries and maps retrieval/LLM outcomes to `QueryResponseSchema`.

**Flow:**

```
1. conversation_id = await _resolve_conversation_id(request)
   - None → QueryRequest.generate_conversation_id()
   - belongs to this session → keep it
   - otherwise → silent re-mint

2. Write #1 — insert query_request:
   async with commit_transaction_async():
       query_request = await QueryRequest.create(
           QueryRequest(
               id=None,
               question=request.question,
               session_id=request.session_id,
               conversation_id=conversation_id,
           )
       )

3. logger.info("Stored query request_id=... session_id=... conversation_id=...")

4. turns = await QueryResponse.fetch_recent_completed_turns(
       session_id=..., conversation_id=...,
       limit=LLMConfig.CONVERSATION_HISTORY_TURN_LIMIT,
   )

5. try:
       chunks = await retrieve_relevant_chunks(request.question)
       retrieval_ok = True
   except Exception:
       logger.warning("Retrieval failed...", exc_info=True)
       chunks, retrieval_ok = [], False

6. if not chunks:
       status = "no_context" if retrieval_ok else "retrieval_failed"
       answer, confidence, next_actions, citations = None, "low", [], []
       → step 9

7. try:
       llm_answer = await generate_answer(request.question, turns, chunks)
   except LLMParseError:
       logger.warning("LLM parse failed...")
       status = "llm_failed"
       answer, confidence, next_actions, citations = None, "low", [], []
       → step 9

8. Happy path:
       status = "no_answer" if llm_answer.answer is None else "answered"
       answer = llm_answer.answer
       confidence = llm_answer.confidence
       next_actions = llm_answer.next_actions if answer else []
       citations = [CitationSchema(...) for c in chunks] if answer else []

9. Write #2 — insert query_response:
   async with commit_transaction_async():
       query_response = await QueryResponse.create(
           QueryResponse(
               id=None,
               request_id=query_request.id,
               session_id=..., conversation_id=...,
               status=status, answer=answer,
               citations=[c.model_dump(mode="json") for c in citations],
               confidence=confidence,
               retrieved_chunk_ids=[c.chunk_id for c in chunks],
               next_actions=list(next_actions),
           )
       )

10. logger.info("Completed query request_id=... response_id=... status=... "
                "confidence=... citations=... next_actions=... history_turns=...")

11. return QueryResponseSchema(...)
```

`_resolve_conversation_id` is a private helper in the same module, reading existing classmethods without opening a transaction.

**Why two transactions.** A single wrapping transaction rolls back the `query_requests` insert on LLM failure, defeating the 2c two-write audit trail. `commit_transaction_async` commits on `__aexit__`, so two separate `async with` blocks are required.

**Why retrieval failure is caught but LLM timeout is not.** Retrieval has a meaningful degraded mode (no-answer). LLM timeout is almost always a real outage; swallowing it would hide problems. `LLMParseError` is the narrow "model responded but output is unparseable" case — safe to treat as no-answer.

### 5.7 `api/routes/query.py` (rewrite)

```python
"""POST /v1/query — grounded, citation-first question answering."""

from fastapi import APIRouter

from core.actions.query_document import query_document
from core.schema.query import QueryRequestSchema, QueryResponseSchema

router = APIRouter()


@router.post("", response_model=dict[str, QueryResponseSchema])
async def post_query(request: QueryRequestSchema) -> dict:
    response = await query_document(request)
    return {"data": response.model_dump(mode="json")}
```

The request body is flat per the 2b contract — the route binds `QueryRequestSchema` directly and does not go through `validate_data_payload`. FastAPI handles 400-on-ValidationError; the existing error handler flattens it to `{"message": ..., "errors": [...]}`. Unhandled exceptions become 500. The action never raises for domain outcomes — no-answer is a successful response with `answer=null`.

### 5.8 `core/services/embeddings.py` (modify)

Two-line change: drop the inline `AsyncOpenAI(...)`, add `client = get_openai_client()`. Sub-batching, 2048-item cap, and ordering guarantees are unchanged.

## 6. Error taxonomy

| Origin | Outcome | HTTP |
|---|---|---|
| `QueryRequestSchema` validation (missing `session_id`, blank `question`, unknown field) | existing handler 400 envelope | 400 |
| `retrieve_relevant_chunks` raises | WARNING, `status='retrieval_failed'`, `answer=null` — persisted | 200 |
| `retrieve_relevant_chunks` returns `[]` | `status='no_context'`, same shape | 200 |
| `generate_answer` → `LLMParseError` | WARNING, `status='llm_failed'`, same shape | 200 |
| `generate_answer` → `openai.APIError` / `APITimeoutError` / `APIConnectionError` | propagates; second write never runs; dangling request row remains | 500 |
| `LLMAnswer(answer=None)` | `status='no_answer'` | 200 |
| `LLMAnswer(answer="...")` | `status='answered'`, citations populated | 200 |
| any other Exception in the action | existing 500 handler | 500 |
| Rate limiter middleware | existing 429 handler | 429 |

**`query_responses.status` values** (internal enum, not in the public contract): `answered`, `no_answer`, `no_context`, `retrieval_failed`, `llm_failed`. The client only sees `answer: str | None`. `no_answer` (LLM had chunks and refused) and `no_context` (zero chunks) surface identically but eval runs care about the difference.

## 7. Logging catalog

| Emitter | Level | Message |
|---|---|---|
| `query_document` | INFO | `Stored query request_id=... session_id=... conversation_id=...` |
| `retrieval` | INFO | `Retrieved %d chunks for question top_score=%.4f` |
| `query_document` | WARNING | `Retrieval failed for request_id=..., falling back to no-answer` (+ `exc_info`) |
| `query_document` | WARNING | `LLM parse failed for request_id=..., falling back to no-answer` |
| `prompts` | WARNING | `Dropped chunk %s (score=%.4f) to fit prompt token budget` |
| `query_document` | INFO | `Completed query request_id=... response_id=... status=... confidence=... citations=... next_actions=... history_turns=...` |

Never logged: `question`, `answer`, `chunk_text`, conversation history, embedding vectors, OpenAI request/response bodies.

## 8. DB / model surface

No schema change, no migration, no index change. All helpers used by 3b (`generate_conversation_id`, `conversation_belongs_to_session`, `count_session_requests_since`, `fetch_recent_completed_turns`, `Chunk.hybrid_search`) shipped in 2c.

## 9. Config surface

No new env vars. 3b uses what `LLMConfig` already exposes from 3a:

| Env var | Default | Used by |
|---|---|---|
| `OPENAI_API_KEY` | `""` | `openai_client.py` |
| `OPENAI_ANSWER_MODEL` | `gpt-5.4-mini` | `llm.py` |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | `embeddings.py` (unchanged from 3a) |
| `OPENAI_TIMEOUT_SECONDS` | `20` | `openai_client.py` |
| `RETRIEVAL_VECTOR_CANDIDATES` | `20` | `retrieval.py` |
| `RETRIEVAL_FULLTEXT_CANDIDATES` | `20` | `retrieval.py` |
| `RETRIEVAL_TOP_K` | `5` | `retrieval.py` |
| `CONVERSATION_HISTORY_TURN_LIMIT` | `10` | `query_document.py` |

`_CONTEXT_TOKEN_BUDGET = 50_000` is a module-level constant in `prompts.py`, not an env knob.

## 10. Dependencies

None new — `openai==1.107.1`, `tiktoken==0.12.0`, `pgvector==0.4.2`, `SQLAlchemy==2.0.43`, `asyncpg==0.30.0` are all already in `requirements.txt`.

## 11. Acceptance test

Manual pass against the live compose stack. API on `:8080`, Postgres on `:5432`. Preconditions: valid `OPENAI_API_KEY`, `gpt-5.4-mini` reachable, at least three documents ingested via `python -m scripts.ingest_url` (the T1/T3/T8 fixtures from 3a).

**Q1. Happy path.**
```bash
curl -sS -X POST http://localhost:8080/v1/query \
  -H 'content-type: application/json' \
  -d '{"question":"How do I run migrations?","session_id":"sess_test_1"}' | jq
```
Expected: 200, body `{"data": {...}}`. `query_id` matches `qry_[a-z0-9]{10}`, `conversation_id` matches `cnv_[a-z0-9]{10}`, non-empty answer mentioning migrations, ≥1 citation with `chunk_order`/`source_url`/`text`/`ingested_at`, `confidence ∈ {high, medium, low}`, `next_actions` is 0–3 strings each ≤60 chars. DB: one row in `query_requests`, one matching row in `query_responses` with `status='answered'`.

**Q2. Multi-turn history.** Re-send under the same `conversation_id` with a pronoun-referencing follow-up; expect the response to resolve the pronoun and the log line to include `history_turns=1`. DB: two rows per table under the same `conversation_id`.

**Q3. Stale `conversation_id` — silent re-mint.** Send `conversation_id=cnv_doesnotexis`; expect 200 and a fresh `conversation_id`, not the one sent. `history_turns=0`.

**Q4. Missing `session_id` → 400** with field-level error.

**Q5. Blank `question` → 400** with field-level error.

**Q6. Unknown top-level field → 400.** `extra="forbid"` rejects e.g. `"top_k": 50`.

**Q7. No-context path.** Ask a question the KB cannot answer (e.g. about Neptune's moons against a KB of Martin Fowler articles); expect 200 with `answer=null`, `citations=[]`, `confidence="low"`, `next_actions=[]`. DB row has `status='no_context'` (or `'no_answer'` if retrieval returned weak rows and the LLM refused).

**Q8. Response envelope shape.** `jq 'keys'` returns exactly `["data"]`.

**Q9. Feedback 501 untouched.** `POST /v1/feedback` still 501 — verifies 3b didn't cross into 3c.

**Q10. Dangling-request invariant.** Set `OPENAI_ANSWER_MODEL=definitely-not-a-model`, restart, send Q1. Expect 500. DB: `query_requests` row exists; no `query_responses` row. A subsequent good request must not see the broken turn in history. Restore the model and restart.

**Q11. Citations survive re-ingestion.** Re-ingest one URL with changed content; the old `query_responses` row's citations are unchanged (snapshotted at answer time); new queries use the new document state.

**Q12. Ruff + pre-commit pass.** No unused imports in `embeddings.py` after removing `AsyncOpenAI`; no circular import between `openai_client.py` and `embeddings.py`.

**Q13. `OPENAI_API_KEY` is only imported from services.** `rg "OPENAI_API_KEY" --glob '!configs/**' --glob '!docs/**' -l` → only `core/services/openai_client.py`.

**Q14. No fastapi in actions/services.** `rg "^from fastapi|^import fastapi" core/ -l` → zero matches.

## 12. Rollout / rollback

**Commits:**
1. `schema: add LLMAnswer structured-output model`
2. `services: extract openai_client, migrate embeddings`
3. `services: add prompts + llm (answer composition)`
4. `services: add retrieval service`
5. `actions: add query_document action`
6. `routes: wire POST /v1/query to the action`
7. `docs/CHANGELOG: record 3b`

**Rollback.** Everything additive except the `embeddings.py` swap (trivially revertable) and the route rewrite (revert restores the 501 stub). DB schema untouched. `docker compose up --build -d context-ingest-api` picks up the new code; Postgres stays warm.

## 13. Deviations from this plan

*(Fill in as deviations occur during implementation.)*

None yet.
