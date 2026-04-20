-- Batch 2c — Queries and feedback.
--
-- The query path is split into two tables:
--   * `query_requests` — written BEFORE the retrieval + LLM pipeline runs.
--     The PK is the public `query_id` returned to callers and referenced by
--     `feedback.query_id`.
--   * `query_responses` — written AFTER the pipeline finishes (success or
--     failure). 1:1 with query_requests via `request_id`. A query_requests
--     row with no matching query_responses row is a dangling / crashed
--     request and is excluded from conversation history fetches.
--
-- session_id is caller-owned and required on every request.
-- conversation_id is server-minted if the caller omits it or supplies one
-- that doesn't belong to their session_id.
--
-- feedback is keyed on query_requests.id (not query_responses) because
-- feedback is "how was my question handled" — it survives even if the
-- response row is later rewritten.
--
-- response_payload is a single JSONB column holding the full response body
-- (answer, citations, confidence, retrieved_chunk_ids, next_actions).
-- Schema changes to the response shape are code-only — no migration needed.
-- status stays as a top-level column for filtering in analytics queries.

create table if not exists query_requests (
    id text primary key,
    question text not null,
    session_id text not null,
    conversation_id text not null,
    created_at timestamp with time zone default now()
);

create index if not exists idx_query_requests_conversation_id
    on query_requests(conversation_id);

create index if not exists idx_query_requests_session_conversation_created
    on query_requests(session_id, conversation_id, created_at desc);

create table if not exists query_responses (
    id text primary key,
    request_id text not null unique references query_requests(id) on delete cascade,
    session_id text not null,
    conversation_id text not null,
    status text not null,
    response_payload jsonb not null,
    created_at timestamp with time zone default now()
);

create table if not exists feedback (
    id text primary key,
    query_id text not null unique references query_requests(id) on delete cascade,
    rating text not null,
    reason text,
    created_at timestamp with time zone not null default now(),
    updated_at timestamp with time zone not null default now()
);

