# Ingestion Guide

How to add content to your ContextIngest instance.

## The manifest

`data/sources.json` is the source of truth. Each entry has a `url` and optionally a `title` and `file`:

```json
[
  {
    "url": "https://example.com/blog/my-post",
    "title": "My Post"
  },
  {
    "url": "knowledge://internal-faq",
    "title": "Internal FAQ",
    "file": "data/content/faq.md"
  }
]
```

- **URL entries** are fetched over HTTP and cleaned with trafilatura.
- **File entries** (with a `file` key) are read from disk relative to the repo root. Use a `knowledge://` URL as a stable identifier.

## Running ingestion

**Over HTTP:**

```bash
curl -X POST http://localhost:8050/v1/ingest
```

Returns `{"data": {"ok": true}}` on success, 500 on failure. Details are in server logs.

**From the CLI (inside the container):**

```bash
docker compose exec context-ingest-api python -m scripts.ingest_all
```

Prints a tally: `ingested=N unchanged=N failed=N`.

**Ad-hoc single item (testing only):**

```bash
docker compose exec context-ingest-api python -m scripts.ingest_one --url "https://example.com/page"
docker compose exec context-ingest-api python -m scripts.ingest_one --file data/content/note.md
```

## Rerun safety

Content is SHA-256 hashed. Re-running ingestion on unchanged content is free — no OpenAI API calls, no database writes. Safe to run on every deploy.

## Adding your own content

1. Add entries to `data/sources.json`.
2. For local files, place them under `data/content/` (or anywhere in the repo).
3. Run ingestion.
4. Verify with a query.

## Useful inspection queries

Connect to the database (`docker compose exec postgres psql -U postgres context_ingest`) and run:

```sql
-- Documents by source
SELECT source_url, title, last_ingested_at FROM documents ORDER BY last_ingested_at DESC;

-- Chunks per document
SELECT d.title, COUNT(*) as chunks FROM chunks c JOIN documents d ON c.document_id = d.id GROUP BY d.title;

-- Total chunks
SELECT COUNT(*) FROM chunks;
```

## Re-embedding

After changing the embedding model, run the reembed script to update all chunk embeddings without re-fetching or re-chunking:

```bash
docker compose exec context-ingest-api python -m scripts.reembed_all
```

Use `--dry-run` to preview. Use `--batch-size N` to control memory.

## Related

- [Ingestion pipeline architecture](../architecture/ingestion-pipeline.md) — how the five stages work
- [Tuning guide](./tuning-retrieval.md) — chunk size and overlap knobs
- [Ingest API contract](../api/ingest.md) — HTTP endpoint spec
