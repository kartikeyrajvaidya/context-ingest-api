# Batch 2b — API contracts and schemas (contract-first) ✅

**Goal:** Decide and write down the exact contract for `POST /v1/query`, `POST /v1/feedback`, and the internal `ingest_document` action, then translate those contracts into Pydantic v2 classes in `core/schema/`. No routes, migrations, or models change in this batch — only contract docs and schema bodies.

**Why this exists as its own batch:** The RAG-pipeline skill's phase rules require a contract-first workflow: `docs/api → schema → action → route`. Doing this as a discrete batch forces contract decisions to be made *on the record* instead of emerging implicitly when the routes are wired up in 3b/3c.

## Status of this batch

- ✅ **`/v1/query` contract frozen** (see below). `core/schema/query.py` + internal `core/schema/retrieval_result.py` updated to match.
- ✅ **`/v1/feedback` contract frozen** (see below). `core/schema/feedback.py` updated to match. Replace semantics — one row per `query_id`, enforced by `UNIQUE (query_id)` in 2c + atomic upsert in the action.
- ✅ **`docs/api/query.md` and `docs/api/feedback.md` shipped** and linked from `README.md`. README curl examples updated to match the frozen contracts (flat request body, `chunk_order`/`source_url`/`text`/`ingested_at` in citations, free-form `rating`). Batch 2b is closed.
- ♻️ **2026-04-14 re-freeze — conversation support added to `/v1/query`.** `session_id` (required) and `conversation_id` (optional) added to request; `session_id` and `conversation_id` added to response (always present). No other fields change. Session is caller-owned and scopes conversations; unknown `conversation_id` under a given `session_id` silently re-mints. Turn limit is server-owned via `CONVERSATION_HISTORY_TURN_LIMIT` env (default 10) and is **not** exposed in the request. 2c adds session/conversation columns to the request table and splits queries into `query_requests` + `query_responses` tables.
- ♻️ **2026-04-14 re-freeze — `next_actions` added to `/v1/query` response.** Additive: a new `next_actions: list[str]` field on the response envelope, 0–3 LLM-generated follow-up prompts grounded in the retrieved chunks. Generated in the same LLM call that composes the answer; empty on no-answer. Not request-configurable. Persisted on `query_responses.next_actions` as JSONB. Single-list design (no 2+1 split, no cross-status rules) since ContextIngest is single-intent.

---

## `POST /v1/query` — frozen contract

### Design decisions (all resolved)

| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Success envelope | `{"data": ...}` wrapping on success; flat `{"message": ...}` on error. | Matches `/health`; asymmetric success/error makes clients dispatch on HTTP status; `data` wrapper leaves room to add response-level metadata later without breaking consumers. |
| 2 | `top_k` in request | **Dropped.** Server-owned via `configs/llm.py`. | Keeps contract minimal; prevents clients from burning tokens via `top_k=50`. Operators tune via env. |
| 3 | `filters.document_ids` | **Dropped in v0.** | Retrieval stays a black box. Additive to re-add later if operators ask; harder to remove. |
| 4 | `session_id` / `conversation_id` | **Added on 2026-04-14 re-freeze.** See "Conversation support" section below for the full design. `page.*` is still not added — page context remains a caller concern. |
| 5 | Confidence | 3-level label `high \| medium \| low`. | Label is easier to act on than a raw float; numeric can be added later as an additional field. |
| 6 | Citation snippet (`text`) | **Included.** Full chunk body returned. | Callers without DB access need something to render. Truncation is caller-side. |
| 7 | Citation field names | `chunk_order` (not `chunk_ord`), `source_url` (not `url`). | Match DB column names to reduce mapping glue. |
| 8 | Citation `ingested_at` | **Added.** | Freshness signal, already in `documents.last_ingested_at`. Any RAG caller wants to know when the cited content was last refreshed. |
| 9 | Citation authority (`type`, `label`) | **Not added.** | Authority tags only make sense inside a single domain. ContextIngest is domain-agnostic. |
| 10 | Latency / retrieved count in response | **Not surfaced.** Written to `queries` table only. | Clients don't need it; leaking timing is avoidable. |
| 11 | Nullable `answer` | **Included.** `answer: str \| None` when no grounded context. | Single most important RAG guardrail — honest "I don't know" beats hallucination. Citations are `[]` and confidence is `"low"` in the no-answer case. No separate `status` enum — nullable carries the same signal with one less field. |

### Request

```http
POST /v1/query HTTP/1.1
Content-Type: application/json
```

```json
{
  "question": "How do I configure chunking?",
  "session_id": "sess_abc123",
  "conversation_id": "cnv_01HFX4G..."
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `question` | string | yes | 1–2000 chars, non-blank |
| `session_id` | string | **yes** | 1–64 chars, non-blank. Caller-owned. See Conversation support below. |
| `conversation_id` | string | no | ≤64 chars. Omit to start a new conversation; silently re-minted if the value doesn't belong to `session_id`. |

`extra="forbid"` — any unknown field returns `400`.

### Response — 200 OK

```json
{
  "data": {
    "query_id": "qry_01HFX...",
    "session_id": "sess_abc123",
    "conversation_id": "cnv_01HFX4G...",
    "answer": "The chunker uses a tiktoken-based tokenizer with a default target size of 500 tokens...",
    "citations": [
      {
        "document_id": "doc_01HFY...",
        "chunk_id": "chk_01HFZ...",
        "chunk_order": 3,
        "source_url": "https://example.com/docs/chunking",
        "title": "Configuring the chunker",
        "text": "The chunker uses a tiktoken-based tokenizer...",
        "ingested_at": "2026-03-15T10:22:00Z"
      }
    ],
    "confidence": "high",
    "next_actions": [
      "How do I tune the chunk overlap?",
      "What embedding model is used?",
      "Can I swap in a different LLM?"
    ]
  }
}
```

**`data` fields:**

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `query_id` | string | no | `qry_<random10>`. Pass to `/v1/feedback`. Stable identity of the question, not the answer. |
| `session_id` | string | no | Echoed from the request unchanged. |
| `conversation_id` | string | no | Always set. Either the one supplied by the caller (if it belonged to this session) or a freshly minted `cnv_<random10>`. Callers persist this and echo it on the next turn. |
| `answer` | string | **yes** | `null` when no grounded context. Never an empty string. |
| `citations` | array | no | Empty `[]` when `answer` is `null`. Otherwise one entry per chunk used, in rank order. |
| `confidence` | string | no | `"high" \| "medium" \| "low"`. Always present. `"low"` when `answer` is `null`. |
| `next_actions` | array of string | no | 0–3 suggested follow-up prompts, LLM-generated in the same call as `answer`. Complete first-person questions, ≤60 chars each. Empty `[]` on no-answer responses. Server-owned — no request field controls count. |

**Citation fields:**

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `document_id` | string | no | `doc_<ulid>`. |
| `chunk_id` | string | no | `chk_<ulid>`. |
| `chunk_order` | integer | no | 0-based position within document. |
| `source_url` | string | no | URL or `internal://slug` passed at ingest time. |
| `title` | string | yes | Document title if known. |
| `text` | string | no | Full chunk body. |
| `ingested_at` | string (ISO 8601) | no | `documents.last_ingested_at`. |

### Response — errors

Uses the existing flat envelope in `api/server/errorhandlers.py`:

| Status | Shape | When |
|---|---|---|
| 400 | `{"message": "Validation failed", "errors": [...]}` | Request fails Pydantic validation — missing/blank `question` or `session_id`, length out of bounds, unknown fields. |
| 429 | `{"message": "Rate limit exceeded"}` | Per-session rate limit tripped (real limiter in 3d). |
| 500 | `{"message": "Internal server error"}` | Any unhandled exception. No stack traces in body. |

No `503` in v0 — LLM/DB outages collapse to `500`.

### No-answer example

```json
{
  "data": {
    "query_id": "qry_01HG0...",
    "session_id": "sess_abc123",
    "conversation_id": "cnv_01HFX4G...",
    "answer": null,
    "citations": [],
    "confidence": "low",
    "next_actions": []
  }
}
```

### Suggested follow-ups (`next_actions`, added 2026-04-14)

**Why it exists.** RAG chatbots without follow-up chips leave the user guessing what to ask next; measurably worse engagement in every UI I've shipped. Suggested prompts are the single highest-leverage addition to a grounded answer after citations themselves. ContextIngest uses a simple single-list version (0–3 prompts, all grounded in the retrieved chunks) because we are single-intent and capability-agnostic — a "discovery" slot would only make sense if the operator knew what other domains the system covered.

**Shape.** `next_actions: list[str]`, 0–3 items, always present on the response (may be `[]`).

**Generation.** Produced by the same OpenAI call that writes the answer. The system prompt in Batch 3b instructs the model to emit, alongside the answer, up to 3 follow-up questions that (a) are directly answerable from the retrieved chunks, (b) are complete first-person user questions ≤60 chars each, (c) do not repeat the question just asked, and (d) are distinct from each other. No second round-trip; cost is a few dozen extra output tokens.

**Empty list cases.** `[]` when `answer` is `null`, when the retrieved context is too narrow to suggest anything non-redundant, or when the LLM produces malformed output and the server falls back to empty rather than failing the request.

**Not request-configurable.** No `next_actions_count`, no `suggest_followups` toggle. Same rationale as `top_k` and `history_turns`: exposing server-owned budgets per-request invites token abuse. Operators who want a different behavior per deployment change the system prompt in 3b.

**Persistence.** Stored on `query_responses.next_actions` as `jsonb not null default '[]'` (see 2c). This lets operators run historical replays and measure click-through without re-running the LLM.

**Feedback is still keyed on `query_id`**, not on which chip the user clicked. Click-through can be measured by correlating a new `query_request.question` to the `next_actions` list of the prior turn in the same conversation, but that is an operator-side analytics concern, not a contract one.

### Conversation support (added 2026-04-14)

**Why it exists.** v0 originally shipped stateless per-request and pushed conversation memory entirely onto the caller. Feedback from early design review: the "bring your own history layer" stance is unfriendly for the dominant use case (drop-in chatbot on a content site) and forces every operator to re-invent the same session + turn-history glue. Supporting conversations server-side as an **opt-in** feature gives both crowds what they want: callers who never pass a `conversation_id` still get one-turn behavior; callers who persist it get multi-turn memory for free.

**Session is the caller identity.** `session_id` is a caller-supplied string (the frontend generates it — typically a UUID in `localStorage` — and echoes it on every request). It is:
- The rate-limit key (per-session in 3d, replacing the interim per-IP limiter).
- The access-control scope for conversations: you cannot continue a conversation that does not belong to your session.

There is no server-side mint of `session_id` in v0 — if the caller omits it, the request is rejected with `400`. Rationale: any frontend complex enough to want multi-turn memory already needs a stable caller token for analytics and feedback grouping; making that token explicit in the contract is cheaper than minting it server-side and having two ids to reconcile.

**Conversation is scoped under session.** `conversation_id` is optional on the request. The server resolves it like this:
1. If omitted → mint a new `cnv_<random10>`, return it on the response.
2. If supplied → check that a row exists in `query_requests` with this `(session_id, conversation_id)` pair. If yes, use it. If no → mint a new one silently (no 404). The response always carries whatever id was actually used.

**Silent re-mint, not 404.** A stale `conversation_id` in the client's localStorage (e.g. after the operator wipes old data) would otherwise strand the user with a hard error. Silent re-mint is friendlier; the client just sees "new conversation started", which is correct.

**Turn limit is server-owned.** `CONVERSATION_HISTORY_TURN_LIMIT` (env, default `10`) controls how many prior turns are fetched and injected into the LLM prompt. It is **not** a request field. Rationale: exposing it per-request lets a caller burn arbitrary token budget on history. Operators who want a different limit per deployment set the env var; operators who want per-caller limits add auth.

**History fetch.** Retrieved server-side per request via `LEFT JOIN query_requests → query_responses ON request_id`, filtered by `(session_id, conversation_id)`, ordered `created_at DESC`, limited to the env value, then reversed to chronological. Dangling requests (no response row yet — crash or in-flight) are excluded by the inner join.

**What history does to the pipeline — v0.** History is injected into the LLM **generation** prompt as a compact transcript block. Retrieval runs on the raw `question` only. Known limitation: follow-ups with pronouns ("tell me more about that") retrieve worse than they should. A future batch may add a query-rewriting step before retrieval.

**Feedback is still keyed on `query_id`**, not on conversation. A user's rating is about a specific turn, not the thread.

---

## `POST /v1/feedback` — frozen contract

### Design decisions (all resolved)

| # | Decision | Resolution | Rationale |
|---|---|---|---|
| 1 | Rating domain | **Free-form text**, `str` with `min_length=1, max_length=32`, trimmed, non-blank. | ContextIngest is a domain-agnostic primitive — an enum locks every operator into one vocabulary. Free text lets callers use thumbs, stars, labels, emojis, numbers, anything. Cost is inconsistency, which is documented as the operator's responsibility. |
| 2 | Response shape | **`204 No Content`** on success. | Fire-and-forget write; v0 has no endpoint that reads feedback back, so returning `feedback_id` would be dead code. Additive upgrade to `200` with body is purely additive if a future "delete my feedback" flow needs it. |
| 3 | `reason` field | **Optional, ≤1000 chars**, free-form, trimmed. | Required fields at feedback time kill response rates. Structure (`tags[]`, categories) is over-engineered for v0 — operators who want structure can categorize the free text post-hoc. |
| 4 | Feedback on no-answer queries (`answer: null`) | **Allowed, no special casing.** | "Refusing was correct" and "you should have found something" are both critical eval signals. Don't fragment the contract. |
| 5 | Duplicate feedback per `query_id` | **Replace.** One row per `query_id`, enforced by `UNIQUE (query_id)` at the DB level, implemented as an atomic upsert in the action. | Operator-chosen semantics: latest feedback wins. Known trade-off: with no auth in v0, a later stranger's feedback can overwrite an earlier one. Acceptable for a single-tenant primitive behind an operator's own frontend. |
| 6 | Unknown `query_id` | **`404`** `{"message": "query not found"}`. | FK insert fails → action catches → 404. Silent-accept is bad for debuggability. |
| 7 | `query_id` format / length | Trimmed, non-blank. No prefix check in the schema (action validates shape of `qry_<ulid>` when looking it up). | Schema stays decoupled from id_prefix convention; action layer owns existence check. |

### Request

```http
POST /v1/feedback HTTP/1.1
Content-Type: application/json
```

```json
{
  "query_id": "qry_01HFX...",
  "rating": "helpful",
  "reason": "exactly what I needed"
}
```

| Field | Type | Required | Constraints |
|---|---|---|---|
| `query_id` | string | yes | Non-blank, trimmed. Must reference an existing row in `queries`. |
| `rating` | string | yes | 1–32 chars, non-blank, trimmed. Free-form — operator picks the vocabulary. |
| `reason` | string | no | ≤1000 chars, trimmed. Empty-after-trim becomes `null`. |

`extra="forbid"`.

### Replace semantics — how it works

A POST against a `query_id` that already has a feedback row **replaces** the existing row. The implementation is an atomic upsert:

```sql
INSERT INTO feedback (id, query_id, rating, reason, updated_at)
VALUES ($1, $2, $3, $4, now())
ON CONFLICT (query_id) DO UPDATE SET
    rating     = EXCLUDED.rating,
    reason     = EXCLUDED.reason,
    updated_at = now();
```

**Observable behavior:**
- After any successful POST, the `feedback` table contains exactly one row for that `query_id`.
- `rating` and `reason` reflect the most recent POST.
- `updated_at` reflects the most recent POST.
- The `feedback.id` (`fbk_<ulid>`) is **stable across updates** — it's generated on the first insert and preserved by the upsert. Since v0 returns `204` and never exposes `feedback_id`, no client can observe this.

**Why upsert instead of literal delete + insert:** a two-statement `DELETE; INSERT` is racy — two concurrent POSTs can both pass the DELETE and one will crash on the UNIQUE constraint. Upsert is one atomic statement and needs no retry logic.

### Response — 204 No Content

Empty body on success. No response schema.

### Response — errors

Uses the existing flat envelope in `api/server/errorhandlers.py`:

| Status | Body | When |
|---|---|---|
| `400` | `{"message": "Validation failed", "errors": [...]}` | Request fails Pydantic validation (blank `rating`, >32-char `rating`, missing `query_id`, unknown fields, etc.). |
| `404` | `{"message": "query not found"}` | `query_id` doesn't reference an existing row in `queries`. |
| `429` | `{"message": "Rate limit exceeded"}` | IP rate limit tripped. |
| `500` | `{"message": "Internal server error"}` | Unhandled exception. |

### Documentation callout (for `docs/api/feedback.md`)

> **Pick a rating vocabulary and stick with it.** ContextIngest does not validate rating *values* — only length and non-blank. That's deliberate, so you can use thumbs, stars, labels, or anything else. But inconsistency hurts eval: decide up front whether you're sending `"helpful"`/`"unhelpful"`, `"1"`–`"5"`, `"👍"`/`"👎"`, etc., and keep client code in sync. Mixed vocabularies in the `feedback` table make analysis harder later.

> **Feedback is replace-on-conflict.** Submitting feedback for a `query_id` that already has feedback **overwrites** the existing row. One `query_id` has at most one feedback row at any time. If you want history, your frontend is the place to keep it — ContextIngest stores only the latest.

---

## Internal `ingest_document` action — confirmed unchanged

Not an HTTP contract. Lives in `core/schema/ingest.py`, documented in `docs/guides/ingestion.md` (Batch 3f).

```python
IngestRequestSchema(url=..., text=..., title=...)     # exactly one of url/text
IngestResponseSchema(document_id=..., status="ingested"|"unchanged"|"failed", chunks=N)
```

No changes proposed in this batch.

---

## Acceptance

- ✅ `core/schema/query.py` matches the frozen contract (`extra="forbid"`, nullable `answer`, `chunk_order` + `source_url` + `text` + `ingested_at` in citation).
- ✅ `core/schema/retrieval_result.py` field names aligned with `CitationSchema`.
- ✅ `core/schema/feedback.py` matches the frozen contract (free-form `rating`, 1–32 chars, non-blank trimmed, optional `reason`).
- ✅ `docs/api/query.md` created from the frozen section above.
- ✅ `docs/api/feedback.md` created from the frozen section above (including the replace-semantics callout).
- ✅ Both docs linked from `README.md`; README curl examples updated to match the frozen contracts.
- ✅ Routes still return 501 — no route logic changes in 2b.
- ✅ Ruff, pre-commit, CI stay green.

## Carry-over into Batch 2c

The feedback replace semantics add two requirements to the migration work in 2c:

1. **`feedback.query_id` gets a `UNIQUE` constraint** (in addition to the FK with cascade). Without the constraint, the `ON CONFLICT (query_id)` clause has no conflict target to hook into.
2. **`feedback.created_at` is renamed to `feedback.updated_at`** to reflect its true meaning — the timestamp of the *latest* feedback event for that `query_id`, not the first. A future batch can add a separate `created_at` if audit history is needed; v0 doesn't.
