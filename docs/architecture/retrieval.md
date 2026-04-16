# Hybrid Retrieval

How ContextIngest finds relevant chunks and composes grounded answers.

## The flow

1. **Embed the question** — same model as ingestion (`text-embedding-3-small`).
2. **Vector search** — pgvector HNSW cosine similarity, top `RETRIEVAL_VECTOR_CANDIDATES` (default 20).
3. **Full-text search** — Postgres `tsvector` with `plainto_tsquery`, top `RETRIEVAL_FULLTEXT_CANDIDATES` (default 20).
4. **Fuse with RRF** — Reciprocal Rank Fusion merges both lists into one ranked result.
5. **Take top K** — `RETRIEVAL_TOP_K` (default 5) chunks go into the LLM context.
6. **Compose answer** — single LLM call with structured output (`LLMAnswer` schema).
7. **Persist** — write the response row with answer, citations, confidence, and suggested follow-ups.

## Why hybrid?

Vector search is great at semantic similarity but misses exact keyword matches. Full-text search catches exact terms but misses paraphrases. Combining them covers both cases.

## Reciprocal Rank Fusion (RRF)

```
score(chunk) = 1/(k + rank_vector) + 1/(k + rank_fts)
```

- `k = 60` (the TREC default, configurable via source)
- Chunks appearing in only one list get `0` for the missing term
- The `FULL OUTER JOIN` ensures nothing is dropped

RRF works on ranks, not scores, so it sidesteps the problem that vector cosine similarity and `ts_rank` are on completely different scales.

## Grounding refusal

If retrieved chunks score too low or retrieval returns nothing, the LLM is instructed to return `status: "no_answer"` instead of guessing. The client sees `answer: null` with `status: "no_answer"`. This is a 200 response — the request was valid, there just wasn't enough context.

## Multi-turn conversations

When a `conversation_id` is provided, the server fetches the last N turns (default `CONVERSATION_HISTORY_TURN_LIMIT=10`) and injects them into the LLM prompt as prior context. Retrieval still runs on the raw question only — history informs the answer, not the search.

Known limitation: follow-ups with pronouns ("tell me more about *that*") retrieve worse because the retriever sees the bare pronoun. A query-rewriting step may be added later.

## Structured output

The LLM returns a `LLMAnswer` with:
- `status` — `answered` or `no_answer`
- `answer` — the grounded response (null on no_answer)
- `citations` — which chunks were used
- `confidence` — `high`, `medium`, or `low`
- `next_actions` — 0-3 suggested follow-up questions, grounded in the same context

Single LLM call, no retrieve-then-critique chain.

## Safety gate

Before retrieval, every question passes through a two-layer safety gate (when `SAFETY_ENABLED=true`):

1. **Regex heuristics** — 12 patterns catching common prompt injection and jailbreak phrases.
2. **LLM classifier** — cheap model (`SAFETY_LLM_MODEL`, default `gpt-4o-mini`) classifies as `safe`, `prompt_injection`, or `jailbreak`.

Blocked requests get `status: "refused"` with a generic message. Fail-closed: classifier errors block the request.

## Knob reference

| Knob | Env var | Default | Effect |
|---|---|---|---|
| Vector candidates | `RETRIEVAL_VECTOR_CANDIDATES` | 20 | More = better recall, slower |
| FTS candidates | `RETRIEVAL_FULLTEXT_CANDIDATES` | 20 | More = better recall, slower |
| Final top-K | `RETRIEVAL_TOP_K` | 5 | How many chunks the LLM sees |
| Chunk size | `CHUNK_TOKEN_SIZE` | 500 | Larger = more context per chunk |
| Chunk overlap | `CHUNK_TOKEN_OVERLAP` | 75 | More = better continuity |
| History turns | `CONVERSATION_HISTORY_TURN_LIMIT` | 10 | Multi-turn memory depth |

See [Tuning guide](../guides/tuning-retrieval.md) for when to change these.

## Related

- [Ingestion pipeline](./ingestion-pipeline.md) — how chunks get created
- [Schema](./schema.md) — `chunks` table and indexes
- [Query API contract](../api/query.md) — what the client sees
