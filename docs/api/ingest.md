# POST /v1/ingest

Trigger a full manifest-driven ingestion. The server reads `data/sources.json`, walks every entry, fetches/cleans/chunks/embeds each source, and persists the results. Rerun-safe — unchanged entries are skipped at zero cost via content-hash comparison.

## Envelope conventions

- **Successful** responses wrap the payload in `{"data": ...}`.
- **Error** responses use a flat envelope: `{"message": "..."}`.
- Clients should dispatch on HTTP status; the success/error shapes are deliberately asymmetric.

## Request

```http
POST /v1/ingest HTTP/1.1
```

**No request body. No URL parameters.** The operator controls what gets ingested by editing the manifest file (`data/sources.json`) inside the container. This is deliberately not an "ingest arbitrary URL" endpoint — that would let any caller drive the operator's OpenAI bill on an unauthenticated API.

## Success response — 200 OK

```json
{
  "data": {
    "ok": true
  }
}
```

That's it. Per-entry results (which sources were ingested, unchanged, or failed, document IDs, chunk counts) are logged server-side at INFO level. The HTTP caller never sees them.

## Error response — 500

```json
{
  "message": "Internal server error"
}
```

Returned when one or more manifest entries fail to ingest. The action processes all entries before raising — partial failures still ingest the successful entries. Stack traces and per-entry errors are logged server-side.

## Rerun semantics

Safe to call repeatedly. Each source's content is SHA-256 hashed at ingest time. If the hash matches the stored hash, the entry is skipped with status `unchanged` — no embeddings API call, no database write.

## Rate limiting

This endpoint is **not** rate-limited by the IP/min middleware (which scopes to `/v1/query` and `/v1/feedback` only). The content-hash gate makes repeated calls free, so rate limiting adds no value here.

## Why this is safe without auth

- The manifest is a file on disk inside the container. An HTTP caller can only trigger ingestion of what the operator has already listed.
- The content-hash gate means repeated calls are free (unchanged entries produce zero embeddings calls).
- There is no request body — the caller cannot inject URLs, text, or any other input.

## Related

- [`POST /v1/query`](./query.md) — query the ingested knowledge base.
- [`POST /v1/feedback`](./feedback.md) — record feedback on a query.
- [ARCHITECTURE.md](../../ARCHITECTURE.md) — system design and data flow.
