# POST /v1/query

Ask a grounded question against your ingested knowledge base. The server retrieves relevant chunks, composes an answer citing them, and returns both. If no chunks are relevant enough to answer, the response explicitly says so instead of guessing.

This is the only query endpoint in v0. There is no streaming variant. Multi-turn conversation memory is supported as an **opt-in** feature — if you want it, pass a `conversation_id` and the server will thread prior turns into the LLM prompt. If you don't, omit it and every request is a one-turn conversation. See [Sessions and conversations](#sessions-and-conversations) below for the full model.

## Envelope conventions

- **Successful** responses wrap the payload in `{"data": ...}`.
- **Error** responses use a flat envelope: `{"message": "..."}`, with `errors[]` added for validation failures.
- Clients should dispatch on HTTP status; the success/error shapes are deliberately asymmetric.

## Request

```http
POST /v1/query HTTP/1.1
Content-Type: application/json
```

```json
{
  "question": "How do I configure the chunker?",
  "session_id": "sess_abc123",
  "conversation_id": "cnv_01HFX4G..."
}
```

### Request fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `question` | string | yes | 1–2000 characters, non-blank, trimmed. |
| `session_id` | string | **yes** | 1–64 characters, non-blank, trimmed. Caller-owned stable token — see [Sessions and conversations](#sessions-and-conversations). |
| `conversation_id` | string | no | ≤64 characters, trimmed. Omit to start a new conversation. Silently re-minted if the value doesn't belong to this `session_id`. |

Any other field returns `400` — the request body uses `extra="forbid"` validation.

### Not accepted (and why)

The following fields exist in other RAG APIs but are deliberately **not** part of the `/v1/query` contract:

| Field | Why not |
|---|---|
| `top_k` | Retrieval depth is a server-owned tuning knob. Operators set it via `configs/llm.py` / environment; clients asking for `top_k=50` could burn tokens. |
| `filters` | Retrieval is a black box in v0. Scoped retrieval (e.g. restricting to a subset of documents) can be added later as a purely additive field without breaking existing callers. |
| `history_turns` | Turn count is a server-owned budget, configured via `CONVERSATION_HISTORY_TURN_LIMIT` (env, default 10). Exposing it per request lets a caller burn arbitrary token budget on history. |
| `page.*` | Page context is a caller concern — prepend it into `question` if you need it. |

## Success response — 200 OK

```json
{
  "data": {
    "query_id": "qry_01HFX4G...",
    "session_id": "sess_abc123",
    "conversation_id": "cnv_01HFX4G...",
    "status": "answered",
    "answer": "The chunker uses a tiktoken-based tokenizer with a default target size of 500 tokens and 75 tokens of overlap between adjacent chunks. You can tune both via environment variables: `CHUNK_TOKENS` and `CHUNK_OVERLAP`.",
    "citations": [
      {
        "document_id": "doc_01HFY5K...",
        "chunk_id": "chk_01HFZ8M...",
        "chunk_order": 3,
        "source_url": "https://example.com/docs/chunking",
        "title": "Configuring the chunker",
        "text": "The chunker uses a tiktoken-based tokenizer with a default target size of 500 tokens...",
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

### Response fields (under `data`)

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `query_id` | string | **yes** | Prefixed random id (`qry_<random10>`). Pass this to [`POST /v1/feedback`](./feedback.md) to attach user feedback to this call. `null` when the request was refused by the safety gate — no query was persisted. |
| `session_id` | string | no | Echoed from the request unchanged. |
| `conversation_id` | string | no | Always set. Either the id you sent (if it belonged to this session) or a freshly minted `cnv_<uuid>`. Persist whatever you get back and echo it on your next request to continue the conversation. |
| `status` | string | no | One of `"answered"`, `"no_answer"`, `"refused"`, `"error"`. See [Status values](#status-values) below. |
| `answer` | string | **yes** | `null` when `status` is `no_answer`, `refused`, or `error`. Never an empty string. |
| `citations` | array | no | One entry per chunk used to ground the answer, in rank order. Empty `[]` when `answer` is `null`. |
| `confidence` | string | no | One of `"high"`, `"medium"`, `"low"`. Derived server-side from similarity scores. Always present. |
| `next_actions` | array of string | no | 0–3 suggested follow-up prompts, LLM-generated from the retrieved chunks. Each is a complete first-person question, ≤60 chars. Empty `[]` on no-answer responses. See [Suggested follow-ups](#suggested-follow-ups) below. |

### Status values

| Value | Meaning | `answer` | `query_id` | Suggested frontend rendering |
|---|---|---|---|---|
| `answered` | Retrieval found relevant context, LLM produced a grounded answer. | non-null | set | Show the answer and citations. |
| `no_answer` | Nothing relevant in the knowledge base, or context too thin to answer. | `null` | set | "I don't have enough information to answer that." |
| `refused` | The safety gate blocked the request (prompt injection or jailbreak detected). | generic message | `null` | Show the refusal message as-is. |
| `error` | Retrieval or LLM failed due to an infrastructure issue. | `null` | set | "Something went wrong, please try again." |

Clients should branch on `status`, not on `answer === null`, since `refused` carries a non-null `answer` (the generic refusal text).

### Citation object

| Field | Type | Nullable | Notes |
|---|---|---|---|
| `document_id` | string | no | Prefixed random id (`doc_<random10>`). Stable across re-ingestion if content hash is unchanged. |
| `chunk_id` | string | no | Prefixed random id (`chk_<random10>`). |
| `chunk_order` | integer | no | 0-based position of this chunk within the document. |
| `source_url` | string | no | The URL or `internal://<slug>` identifier passed at ingest time. |
| `title` | string | yes | Document title if known at ingest time, otherwise `null`. |
| `text` | string | no | The full chunk body used as grounding context. Callers render snippets by truncating client-side. |
| `ingested_at` | string (ISO 8601) | no | The `last_ingested_at` timestamp of the source document. A freshness signal — lets callers warn when citations are based on stale content. |

## No-answer response

When retrieval returns no chunks, or every retrieved chunk scores below the grounding threshold, the server refuses to guess. The HTTP status is still **`200 OK`** — the request was valid — but the payload carries an explicit null answer:

```json
{
  "data": {
    "query_id": "qry_01HG0...",
    "session_id": "sess_abc123",
    "conversation_id": "cnv_01HFX4G...",
    "status": "no_answer",
    "answer": null,
    "citations": [],
    "confidence": "low",
    "next_actions": []
  }
}
```

Clients should check `response.data.status === "no_answer"` and render a fallback (e.g. "I don't have enough context to answer that. Try rephrasing, or ingest more sources.") rather than treating this as an error. Attaching feedback to a no-answer query is valid and encouraged — `"helpful"` means "refusing was the right call", `"unhelpful"` means "you should have found something".

## Suggested follow-ups

Every successful response includes a `next_actions` array of 0–3 suggested follow-up prompts. They are generated by the same LLM call that composes the answer — no extra round trip, a few dozen extra output tokens — and are intended to be rendered as clickable chips underneath the answer in a chat UI. Clicking one simply posts it back as the next `/v1/query` call (echoing `session_id` and `conversation_id` to keep the thread).

**Format rules** (enforced via system prompt, not Pydantic):

- Complete first-person questions ("How do I tune the overlap?"), not fragments ("overlap tuning").
- ≤60 characters each. No duplicates. Must not repeat the question that was just asked.
- Must be answerable from the retrieved chunks — the LLM is instructed to ground them in the same context as the answer, not hallucinate broader capabilities.
- 0–3 items. The array may be empty if the context is too thin to suggest anything useful.

**When it's empty.** `next_actions` is `[]` whenever:
- `answer` is `null` (no-answer path — nothing to build follow-ups from).
- The retrieved context is so narrow that the LLM can't produce non-redundant suggestions.
- The composition call produces malformed output and the server falls back to empty.

Clients should treat `next_actions: []` as "don't render the chip row", not as an error.

**Not configurable per request.** There is no `next_actions_count` or `suggest_followups` field. The number of suggestions is server-owned, same rationale as `top_k` and `history_turns`: exposing it invites token-budget abuse.

**Persistence.** The returned list is stored on the `query_responses` row (as JSONB) so historical replays and evals can see what the caller was offered at the time. Feedback is still keyed on `query_id` — feedback applies to the answer, not to which chips were shown.

## Sessions and conversations

ContextIngest supports multi-turn conversations as an **opt-in** feature. All state decisions live on the server so callers don't have to rebuild a history layer from scratch.

### The two ids

- **`session_id`** — caller-owned, required on every request. The frontend generates it once per visitor (typically a UUID stored in `localStorage`) and echoes it back on every call. It is the unit of rate limiting and the access-control scope for conversations.
- **`conversation_id`** — server-visible, optional on request. A conversation lives under exactly one `session_id`. You cannot continue another session's conversation.

Think of it as two nested scopes: *session* is "one browser tab / one visitor", *conversation* is "one thread within that session". A single session can have many conversations; a single conversation belongs to exactly one session.

### Starting a new conversation

Omit `conversation_id` entirely. The server mints one and returns it on the response:

```json
// request
{"question": "How do I configure the chunker?", "session_id": "sess_abc123"}

// response.data
{"query_id": "qry_...", "session_id": "sess_abc123", "conversation_id": "cnv_new_..."}
```

### Continuing a conversation

Send the `conversation_id` you got back on the previous turn, along with the same `session_id`:

```json
{
  "question": "And how do I tune the overlap?",
  "session_id": "sess_abc123",
  "conversation_id": "cnv_new_..."
}
```

The server fetches the last N turns for this `(session_id, conversation_id)` pair, injects them into the LLM prompt as prior-turn context, and answers with the history in mind.

### Silent re-mint on stale ids

If you send a `conversation_id` that does not belong to your `session_id` — e.g. the operator wiped old data, or your localStorage is stale, or you're just guessing — the server does **not** return an error. It silently mints a new `conversation_id`, returns it in the response, and treats the call as the first turn of a new conversation. The client should always trust the `conversation_id` in the response, not the one it sent.

This is a deliberate UX choice: stranding users with a 404 on stale state is worse than losing their old thread.

### Turn limit is server-owned

The number of prior turns fed to the LLM is set by `CONVERSATION_HISTORY_TURN_LIMIT` (environment variable, default `10`). It is **not** a request field — exposing it per-request would let any caller burn arbitrary LLM tokens on history. Operators who want a different budget change the env var.

Turns are fetched newest-first via the `(session_id, conversation_id, created_at)` index, capped at the limit, then reversed to chronological order before being rendered into the prompt. Dangling requests (where the pipeline crashed before writing a response) are excluded — they never happened from the LLM's perspective.

### History influences generation, not retrieval (v0)

Retrieval runs on the raw `question` only. History is rendered into the LLM prompt as a transcript block next to the retrieved chunks. Known limitation: follow-ups with pronouns ("tell me more about *that*") retrieve worse than they should because the retriever sees the bare pronoun without context. A future batch may add a query-rewriting step that rewrites the question against history before retrieval.

### What if I never want conversations?

Never pass a `conversation_id`. Every request mints a fresh one, the history fetch returns zero prior turns, and the request behaves like the single-shot RAG call it always was. The only cost is one extra row in `query_requests.conversation_id`, which you can ignore.

## Error responses

All errors use the flat envelope from [`api/server/errorhandlers.py`](../../api/server/errorhandlers.py):

| Status | Body | When |
|---|---|---|
| `400` | `{"message": "Validation failed", "errors": [...]}` | Request body fails Pydantic validation — missing/blank `question` or `session_id`, unknown fields, lengths out of bounds. The `errors` array contains per-field detail. **Note:** an unknown `conversation_id` is NOT a 400 — it is silently re-minted. |
| `429` | `{"message": "Rate limit exceeded"}` | The caller's session tripped the rate limiter. (The real limiter lands in a later batch; until then `/v1/query` is effectively unlimited.) |
| `500` | `{"message": "Internal server error"}` | Any unhandled exception in the retrieval, LLM, or DB layer. Stack traces are logged server-side and never leaked to the response body. |

No `503` is used in v0 — transient LLM or database outages collapse to `500`.

## Worked example

### First turn (no conversation_id)

```bash
curl -sS -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I configure the chunker?",
    "session_id": "sess_abc123"
  }'
```

Successful response:

```json
{
  "data": {
    "query_id": "qry_01HFX4G...",
    "session_id": "sess_abc123",
    "conversation_id": "cnv_new_...",
    "status": "answered",
    "answer": "The chunker uses a tiktoken-based tokenizer ...",
    "citations": [ /* ... */ ],
    "confidence": "high"
  }
}
```

### Follow-up turn (echoing conversation_id)

```bash
curl -sS -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "And how do I tune the overlap?",
    "session_id": "sess_abc123",
    "conversation_id": "cnv_new_..."
  }'
```

The server fetches prior turns for this `(session_id, conversation_id)` pair and threads them into the LLM prompt.

### Validation failure (missing `session_id`)

```bash
curl -sS -X POST http://localhost:8000/v1/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How do I configure the chunker?"}'
```

```json
{
  "message": "Validation failed",
  "errors": [
    {"type": "missing", "loc": ["body", "session_id"], "msg": "Field required"}
  ]
}
```

## Related

- [`POST /v1/feedback`](./feedback.md) — record feedback on a query.
- [`POST /v1/ingest`](./ingest.md) — trigger content ingestion.
- [Architecture overview](../architecture/overview.md) — how a request flows end to end.
