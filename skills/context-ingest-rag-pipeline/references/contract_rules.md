# RAG Contract Rules

These rules govern the request and response contracts for the public RAG endpoints and the shape of the internal ingestion action. They apply on top of the general API rules in `../../context-ingest-api-backend/references/api_rules.md`.

## Endpoints

| Method | Path           | Purpose                                       |
|--------|----------------|-----------------------------------------------|
| POST   | `/v1/query`    | Hybrid retrieval + LLM answer with citations   |
| POST   | `/v1/feedback` | Record thumbs up/down against a prior query    |

Both use the wrapped envelope:

```json
{ "data": { ... } }
```

Auth: none in the current batch.

## Ingestion (CLI-only in v0)

Ingestion in v0 has **no HTTP route**. It is driven entirely from `scripts/ingest_url.py` and `scripts/ingest_batch.py`, which call `core/actions/ingest_document.ingest_document` directly. A future batch may add a manifest-triggered `POST /v1/refresh` endpoint (see `../../../docs/scaffolding-plan.md` → "Future: manifest-driven refresh API") that reuses the same action without any refactor.

The `IngestRequestSchema` and `IngestResponseSchema` in `core/schema/ingest.py` are the action's typed input and output. They are not an HTTP contract in v0, but they are the contract that the future refresh loop will produce rows from, so the same rules apply:

### Action input (`IngestRequestSchema`)

```python
{
  "url": "https://example.com/post" | None,
  "text": "optional raw text" | None,
  "title": "optional title" | None,
}
```

- Either `url` or `text` is required. Both is allowed only if `text` represents the same content as `url` (the `url` becomes the canonical source identifier and `text` is used in place of fetching).
- `url`, when present, must be a valid http(s) URL.
- `title` is optional. If absent, the ingestion pipeline derives it from the fetched or supplied content.
- The schema rejects unknown fields (`extra="forbid"`).
- Empty / whitespace-only `text` is rejected by the schema's validator.

### Action output (`IngestResponseSchema`)

```python
{
  "document_id": "doc_abc123" | None,
  "status": "ingested" | "unchanged" | "failed",
  "chunks": 17,
}
```

- `document_id` is required on `ingested` and `unchanged`; it is `None` on `failed` because no row was written.
- `status: ingested` means new content was written or replaced.
- `status: unchanged` means the content hash matched the stored hash and the pipeline was a no-op (no embedding call, no DB write beyond the rerun lookup).
- `status: failed` is used only for non-fatal, contract-documented failures — specifically `FetchError` (HTTP/network error fetching a URL) and `EmptyContentError` (cleaner extracted nothing usable). Fatal errors (OpenAI outage, DB outage) propagate as exceptions from the action.
- `chunks` is the count of chunks now associated with the document. For `unchanged`, it is the existing count. For `failed`, it is `0`.

## `/v1/query`

### Request

```json
{
  "data": {
    "question": "What does the post say about X?",
    "top_k": 5,
    "filters": {
      "document_ids": ["doc_abc123"]
    }
  }
}
```

### Request rules

- `question` is required and must be non-empty plain text.
- `top_k` is optional; if omitted, use the configured default. Cap at the configured maximum.
- `filters` is optional. The only filter supported in the current batch is `document_ids`.
- Reject unknown top-level request fields.
- Reject unknown `filters` fields.

### Response

```json
{
  "data": {
    "query_id": "qry_xyz789",
    "answer": "The post explains that X works by ...",
    "citations": [
      {
        "document_id": "doc_abc123",
        "url": "https://example.com/post",
        "title": "My Post",
        "chunk_ord": 4
      }
    ],
    "confidence": "low | medium | high"
  }
}
```

### Response rules

- `query_id` is required on every response — it is the handle used by `/v1/feedback`.
- `answer` is required and is the user-facing string. May contain markdown.
- `citations` is a list of objects, one per retrieved chunk used to ground the answer. Empty list is allowed only when `confidence` is `low`.
- `confidence` is required. Use `low` when retrieval returned nothing or everything was below the relevance threshold; `medium` when retrieval was usable but partial; `high` when the answer is strongly grounded in the retrieved chunks.
- Do not return raw embeddings, raw chunk text bodies, or internal scoring values in the public response.
- Do not return classifier labels or prompt names.

## `/v1/feedback`

### Request

```json
{
  "data": {
    "query_id": "qry_xyz789",
    "rating": "up | down",
    "reason": "optional free-text reason"
  }
}
```

### Request rules

- `query_id` is required and must reference an existing query.
- `rating` is required; only `up` or `down` are accepted.
- `reason` is optional and capped at a configured length.
- Reject unknown top-level fields.

### Response

`204 No Content`. No body.

## Error rules

- Use shared exception handling.
- Validation errors should remain field-specific.
- Do not emit per-route ad hoc error JSON.
- Error responses use the shared envelope `{"message": "..."}`.
- Do not grow large route-local validation helpers when the same complexity can live in the action layer more cleanly.
