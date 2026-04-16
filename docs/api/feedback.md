# POST /v1/feedback

Record user feedback against a previous query. Feedback is the only post-hoc signal you have for whether the RAG loop is working, and it drives every meaningful improvement to retrieval, prompting, and ingestion quality.

## Replace semantics — read this first

**One feedback row per `query_id`.** A POST against a `query_id` that already has feedback **overwrites** the existing row. Implementation is an atomic Postgres upsert (`INSERT ... ON CONFLICT (query_id) DO UPDATE`), so concurrent POSTs for the same query are safe — the last write wins.

Practical consequences:

- If you need an audit trail of every rating a user ever gave, keep it in your frontend. ContextIngest stores only the latest.
- There is no "append feedback" variant. A second POST is a replacement, not an addition.
- Because v0 ships with no authentication, any caller with a `query_id` can overwrite any previous feedback for it. This is intentional for a single-tenant primitive; if you need per-user feedback, run ContextIngest behind an authenticated frontend and scope `query_id`s per user there.

## Pick a rating vocabulary and stick with it

`rating` is **free-form text**, 1–32 characters. ContextIngest does not validate the *values* — only length and non-blank. That's deliberate, so you can use whatever rating scheme fits your product:

- Thumbs: `"helpful"`, `"unhelpful"`
- Stars: `"1"`, `"2"`, `"3"`, `"4"`, `"5"`
- Thermometer: `"good"`, `"ok"`, `"bad"`
- Emoji: `"👍"`, `"👎"`, `"🤔"`

**Inconsistency is the price of flexibility.** Mixed vocabularies in the `feedback` table make analysis harder later. Decide up front which scheme you're using, put it in your client code, and keep it consistent across all callers. The API will not rescue you from a deployment that sends `"helpful"` from one frontend and `"thumbs_up"` from another.

## Request

```http
POST /v1/feedback HTTP/1.1
Content-Type: application/json
```

```json
{
  "query_id": "qry_01HFX4G...",
  "rating": "helpful",
  "reason": "exactly what I needed"
}
```

### Request fields

| Field | Type | Required | Constraints |
|---|---|---|---|
| `query_id` | string | yes | Non-blank, trimmed. Must reference an existing row in the `queries` table — a `query_id` returned by an earlier `POST /v1/query` call. |
| `rating` | string | yes | 1–32 characters, non-blank, trimmed. Free-form — see [Pick a rating vocabulary](#pick-a-rating-vocabulary-and-stick-with-it) above. |
| `reason` | string | no | ≤1000 characters, trimmed. An empty-after-trim value is treated as `null`. |

Any other field returns `400` — the request body uses `extra="forbid"` validation.

## Feedback on no-answer queries

If the original `POST /v1/query` returned `"answer": null`, you can still submit feedback on that `query_id`. In fact, it's the most useful signal you can collect:

- `rating: "helpful"` on a null answer means "refusing to guess was the right call — I didn't have this info either."
- `rating: "unhelpful"` on a null answer means "you should have found something — there are sources that cover this."

Both signals are critical for tuning the grounding threshold. The endpoint does not special-case no-answer queries; feedback is feedback.

## Success response — 204 No Content

```http
HTTP/1.1 204 No Content
```

Empty body. There is no `feedback_id` returned — v0 has no endpoint that reads feedback back, so the row id is write-only server state. (If a future version adds a "retract my feedback" flow, the response shape can grow a `feedback_id` field additively.)

## Error responses

| Status | Body | When |
|---|---|---|
| `400` | `{"message": "Validation failed", "errors": [...]}` | Request body fails Pydantic validation — missing `query_id` or `rating`, blank after trim, `rating` over 32 characters, unknown fields, etc. The `errors` array contains per-field detail. |
| `404` | `{"message": "query not found"}` | The supplied `query_id` does not reference any row in the `queries` table. Returned when the FK insert fails. |
| `429` | `{"message": "Rate limit exceeded"}` | The caller's IP tripped the rate limiter. (Feedback runs through the same IP-based limiter as `/v1/query`, tuned tighter in a later batch.) |
| `500` | `{"message": "Internal server error"}` | Any unhandled exception. Stack traces are logged server-side and never leaked to the response body. |

## Worked examples

### Record positive feedback

```bash
curl -sS -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "qry_01HFX4G...",
    "rating": "helpful",
    "reason": "answered the question directly and cited the right section"
  }'
```

`HTTP/1.1 204 No Content`.

### Record negative feedback without a reason

```bash
curl -sS -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "qry_01HFX4G...",
    "rating": "unhelpful"
  }'
```

`HTTP/1.1 204 No Content`.

### Overwrite existing feedback

Same `query_id`, different rating:

```bash
# First call
curl -sS -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "qry_01HFX4G...", "rating": "helpful"}'
# → 204

# Second call — replaces the first
curl -sS -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "qry_01HFX4G...", "rating": "unhelpful", "reason": "on re-reading, the answer is wrong"}'
# → 204
```

After both calls, the `feedback` table contains exactly **one** row for `qry_01HFX4G...`, with `rating = "unhelpful"` and the later `reason`.

### Unknown query_id

```bash
curl -sS -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"query_id": "qry_doesnotexist", "rating": "helpful"}'
```

```json
{"message": "query not found"}
```

## Related

- [`POST /v1/query`](./query.md) — produces the `query_id` you attach feedback to.
- [`POST /v1/ingest`](./ingest.md) — trigger content ingestion.
- [Architecture overview](../architecture/overview.md) — how the system works.
