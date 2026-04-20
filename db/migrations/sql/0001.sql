-- Batch 2c — Documents and chunks.
--
-- Enables pgvector and creates the ingest half of the schema: `documents`
-- (one row per logical source) and `chunks` (one row per embedded chunk).
-- Split from 0002 so a fork that only wants the ingest pipeline can stop
-- here and skip the query/response/feedback tables.
--
-- Index choices:
--   * HNSW with vector_cosine_ops on chunks.embedding — matches the default
--     OpenAI embedding model (text-embedding-3-small) which is not normalized
--     for inner-product.
--   * GIN on the generated tsvector column `chunks.tsv` so the hybrid
--     retrieval path can full-text search without a second index build.
--   * unique (document_id, chunk_order) to catch double-insert on retry.

create extension if not exists vector;

create table if not exists documents (
    id text primary key,
    source_url text not null unique,
    source_type text not null,
    title text,
    content_hash text,
    chunk_count integer not null default 0,
    is_active boolean not null default true,
    last_ingested_at timestamp with time zone default now(),
    created_at timestamp with time zone default now()
);


create table if not exists chunks (
    id text primary key,
    document_id text not null references documents(id) on delete cascade,
    chunk_order integer not null,
    chunk_text text not null,
    embedding vector(1536) not null,
    tsv tsvector generated always as (to_tsvector('english', chunk_text)) stored,
    created_at timestamp with time zone default now(),
    unique (document_id, chunk_order)
);

create index if not exists idx_chunks_document_id
    on chunks(document_id);

create index if not exists idx_chunks_embedding
    on chunks using hnsw (embedding vector_cosine_ops);

create index if not exists idx_chunks_tsv
    on chunks using gin(tsv);

