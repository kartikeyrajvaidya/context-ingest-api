# Tuning Retrieval

When answers aren't good enough, here's what to adjust.

## Symptoms and fixes

| Symptom | Likely cause | Knob to turn |
|---|---|---|
| Answers are shallow or miss details | Not enough context reaching the LLM | Increase `RETRIEVAL_TOP_K` or `RETRIEVAL_VECTOR_CANDIDATES` |
| Wrong chunks cited | Chunks too large, mixing topics | Decrease `CHUNK_TOKEN_SIZE` |
| Answers cut off mid-thought | Chunks split at bad boundaries | Increase `CHUNK_TOKEN_OVERLAP` |
| "I don't have enough information" on valid questions | Retrieval missing the right chunks | Increase candidate counts, check if content is ingested |
| Slow responses | Too many candidates or too large context | Decrease candidate counts or `RETRIEVAL_TOP_K` |

## Knob reference

All set via environment variables in `.env` or `docker-compose.yaml`.

| Env var | Default | What it does |
|---|---|---|
| `CHUNK_TOKEN_SIZE` | 500 | Target tokens per chunk. Smaller = more precise retrieval, larger = more context per chunk. |
| `CHUNK_TOKEN_OVERLAP` | 75 | Overlap between adjacent chunks. Higher = better continuity at chunk boundaries. |
| `RETRIEVAL_VECTOR_CANDIDATES` | 20 | How many chunks vector search returns before fusion. |
| `RETRIEVAL_FULLTEXT_CANDIDATES` | 20 | How many chunks full-text search returns before fusion. |
| `RETRIEVAL_TOP_K` | 5 | Final number of chunks sent to the LLM. |
| `CONVERSATION_HISTORY_TURN_LIMIT` | 10 | How many prior turns are included in multi-turn conversations. |
| `OPENAI_ANSWER_MODEL` | gpt-5.4-mini | The LLM used for answer generation. |
| `OPENAI_TIMEOUT_SECONDS` | 20 | LLM call timeout. |

## After changing chunk settings

If you change `CHUNK_TOKEN_SIZE` or `CHUNK_TOKEN_OVERLAP`, you need to **re-ingest** your content for the new settings to take effect. Existing chunks in the database were split with the old settings.

```bash
# Delete existing data and re-ingest
docker compose down -v
docker compose up --build -d
docker compose exec context-ingest-api python -m scripts.ingest_all
```

## After changing the embedding model

If you change `OPENAI_EMBEDDING_MODEL`, run the reembed script instead of re-ingesting:

```bash
docker compose exec context-ingest-api python -m scripts.reembed_all
```

This updates embeddings in place without re-fetching or re-chunking.

## The feedback loop

The `POST /v1/feedback` endpoint records thumbs up/down against each query. Use this data to guide tuning decisions — it's the ground truth for whether your retrieval is working.

```sql
-- See feedback distribution
SELECT rating, COUNT(*) FROM feedback GROUP BY rating;

-- Find unhelpful answers to investigate
SELECT qr.question, qresp.response_payload->>'answer' as answer, f.reason
FROM feedback f
JOIN query_requests qr ON f.query_id = qr.id
JOIN query_responses qresp ON qresp.query_id = qr.id
WHERE f.rating = 'unhelpful'
ORDER BY f.updated_at DESC LIMIT 10;
```

## Related

- [Retrieval architecture](../architecture/retrieval.md) — how hybrid search and RRF work
- [Ingestion guide](./ingestion.md) — re-ingesting after config changes
