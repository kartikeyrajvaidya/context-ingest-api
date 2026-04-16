# Database Schema

All state lives in one PostgreSQL 17 database with pgvector. Five tables, no external stores.

## Tables

### documents

The unit of ingestion. One row per source URL.

| Column | Type | Notes |
|---|---|---|
| id | text PK | `doc_<random10>` |
| source_url | text NOT NULL UNIQUE | The URL or `knowledge://` identifier |
| title | text | Optional, from manifest |
| content_hash | text NOT NULL | SHA-256 of cleaned text — rerun gate |
| last_ingested_at | timestamptz | Updated on each successful ingest |
| created_at | timestamptz | First ingest |

### chunks

Pieces of a document, each with an embedding.

| Column | Type | Notes |
|---|---|---|
| id | text PK | `chk_<random10>` |
| document_id | text FK -> documents | CASCADE delete |
| chunk_order | int | 0-based position in document |
| chunk_text | text NOT NULL | The readable text |
| embedding | vector(1536) | OpenAI `text-embedding-3-small` |
| tsv | tsvector | Auto-generated for full-text search |
| created_at | timestamptz | |

**Indexes:** HNSW on `embedding` (vector cosine), GIN on `tsv`, b-tree on `document_id`.

### query_requests

One row per incoming query. Written *before* retrieval starts (first write of the two-write durable flow).

| Column | Type | Notes |
|---|---|---|
| id | text PK | `qry_<random10>` |
| session_id | text NOT NULL | Caller-owned visitor token |
| conversation_id | text NOT NULL | Server-minted or echoed |
| question | text NOT NULL | The user's question |
| created_at | timestamptz | |

### query_responses

One row per completed answer. Written *after* the LLM call (second write).

| Column | Type | Notes |
|---|---|---|
| id | text PK | `qrs_<random10>` |
| query_id | text FK -> query_requests | CASCADE delete |
| status | text NOT NULL | `answered`, `no_answer`, `no_context`, `retrieval_failed`, `llm_failed` |
| response_payload | jsonb NOT NULL | `{answer, citations, confidence, retrieved_chunk_ids, next_actions}` |
| created_at | timestamptz | |

**Why two tables?** If the LLM call crashes, `query_requests` has the record but `query_responses` doesn't. The query was attempted but not answered — no orphan answer rows, no ambiguity.

**Why JSONB?** The five response fields (`answer`, `citations`, `confidence`, `retrieved_chunk_ids`, `next_actions`) are always read and written together, never queried individually. One JSONB column avoids a migration for every response shape change.

### feedback

One row per query. Replace semantics via upsert.

| Column | Type | Notes |
|---|---|---|
| id | text PK | `fdb_<random10>` — preserved across upserts |
| query_id | text FK UNIQUE | One feedback per query |
| rating | text NOT NULL | Free-form, 1-32 chars |
| reason | text | Optional |
| created_at | timestamptz | Preserved across upserts |
| updated_at | timestamptz | Advanced on each upsert |

## FK topology

```
documents  <--  chunks
query_requests  <--  query_responses
query_requests  <--  feedback
```

All FKs use `ON DELETE CASCADE`. To purge old data: `DELETE FROM query_requests WHERE created_at < ...` — responses and feedback follow.

## Migrations

Raw SQL lives in `db/migrations/sql/` (`0001.sql`, `0002.sql`). Alembic wrappers in `db/migrations/versions/` execute the same SQL. Docker Compose runs the raw SQL files as Postgres init scripts on first boot.
