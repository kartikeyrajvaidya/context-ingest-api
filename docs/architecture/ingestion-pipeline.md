# Ingestion Pipeline

How content goes from a URL to searchable chunks with embeddings.

## The five stages

```
URL or local file
  -> Fetch    (httpx / file read)
  -> Clean    (trafilatura for HTML, custom for markdown)
  -> Chunk    (tiktoken-based, ~500 tokens, 75 overlap)
  -> Embed    (OpenAI text-embedding-3-small, batched)
  -> Persist  (document + chunks in one transaction)
```

### 1. Fetch

`core/ingestion/fetcher.py` — HTTP GET via `httpx` with timeouts. For manifest entries with a `file` key, reads from disk instead.

### 2. Clean

`core/ingestion/cleaner.py` — `trafilatura` strips nav, ads, and boilerplate from HTML. Markdown files get a lighter pass (strip front matter, normalize whitespace). Output is plain text.

### 3. Chunk

`core/ingestion/chunker.py` — splits text into chunks of ~`CHUNK_TOKEN_SIZE` tokens (default 500) with `CHUNK_TOKEN_OVERLAP` overlap (default 75). Uses `tiktoken` for accurate token counting. Avoids splitting mid-paragraph when possible.

### 4. Embed

`core/services/embeddings.py` — calls OpenAI's embeddings API. Automatically splits large batches into sub-batches to stay under API limits. One embedding per chunk, 1536 dimensions.

### 5. Persist

`core/ingestion/pipeline.py` — writes the document row and all chunk rows in a single transaction. If the document already exists, old chunks are deleted and new ones inserted atomically.

## Rerun safety

Every document's cleaned text is SHA-256 hashed. On re-ingest:

- **Hash matches stored hash** -> skip. Status: `unchanged`. Zero API calls, zero DB writes.
- **Hash differs** -> delete old chunks, re-chunk, re-embed, persist. Status: `ingested`.
- **New URL** -> full pipeline. Status: `ingested`.

This makes it safe to run `POST /v1/ingest` or `scripts/ingest_all.py` on every deploy.

## Entry points

| Entry point | When to use |
|---|---|
| `POST /v1/ingest` | Trigger from CI/CD or monitoring. Reads `data/sources.json`. |
| `scripts/ingest_all.py` | Same as above, from the CLI inside the container. |
| `scripts/ingest_one.py` | Ad-hoc testing. `--url` or `--file`, one item at a time. |

## Error handling

If a single manifest entry fails, the error is logged and the pipeline continues to the next entry. After all entries, if any failed, the action raises `IngestManifestError` — the HTTP route returns 500, the CLI script exits with code 1.

## Related

- [Retrieval](./retrieval.md) — what happens after ingestion
- [Tuning guide](../guides/tuning-retrieval.md) — chunk size and overlap knobs
- [Schema](./schema.md) — `documents` and `chunks` tables
