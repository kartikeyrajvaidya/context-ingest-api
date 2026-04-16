# RAG Pipeline Phase Rules

Source of truth: `../../../docs/scaffolding-plan.md`

The plan document is canonical. If this file and the plan disagree, the plan wins. Update the plan first, then update this file.

## Hard boundaries

- Do not implement streaming responses, conversation memory, or persistent chat state in the current batch. These are explicit non-goals in `scaffolding-plan.md`.
- Do not add a generic `context` or generic `metadata` request field. Add fields explicitly to the contract when needed.
- Do not expose internal classifier labels, raw embeddings, or raw scoring objects in the public response.
- Do not add a multi-tenancy column to any RAG table. The current batch is single-tenant.
- Do not add reranker, cross-encoder, or MMR retrieval in the current batch — hybrid RRF is the only retrieval strategy until a future batch explicitly adds another.
- Do not add new ingestion source types beyond URL and raw text in the current batch. PDF, Notion, GitHub, and other sources are deferred.
- Do not let any answer be ungrounded. If retrieval fails, return a low-confidence "not enough information" answer. Do not call the LLM without grounding context.

## Retrieval boundary

- The retrieval pipeline is intent-agnostic and shared across the query route.
- Vector kNN runs against `chunks.embedding` using pgvector HNSW.
- Full-text search runs against `chunks.tsv` using Postgres `tsvector` GIN.
- Fusion is Reciprocal Rank Fusion (RRF) — no weighted sum, no learned weights.
- Retrieval failures must degrade gracefully. A pgvector error or a full-text error must not block the request — fall back to the side that succeeded, and if both fail, return a low-confidence answer.

## Ingestion boundary

- Ingestion in v0 has no HTTP route. It is driven from CLI scripts that call `core/actions/ingest_document.ingest_document` directly. A future batch may add a manifest-triggered `POST /v1/refresh` endpoint; until that batch is active, do not scaffold a public ingest HTTP route.
- Ingestion is synchronous. No background queue.
- The pipeline is rerun-safe via SHA-256 content hashing — unchanged content is a no-op (no embedding call, no DB write beyond the rerun lookup).
- The pipeline is one transaction per document. A failed ingestion leaves the database untouched.
- Chunking is token-aware via `tiktoken`, with size and overlap configured via env vars. Chunks should not cross paragraph boundaries when avoidable.
- Embeddings are batched into one OpenAI call per document where possible.
- `robots.txt` is not consulted in v0. Operators ingest content they already own, and adding a per-request robots fetch plus cache is deferred until the feature is actually needed.

## Support-table rule

The RAG side owns these tables: `documents`, `chunks`, `queries`, `feedback`.

- Do not add new RAG tables in the current batch unless the active batch is explicitly a schema-change batch.
- Do not extend the existing tables with speculative columns. Add a column when a feature actually needs it.

## Implementation order

When implementing a RAG batch, follow this order to keep the surface area small:

1. Update the contract in `contract_rules.md` and `docs/api/`.
2. Update or create the Pydantic schema in `core/schema/`.
3. Write the action in `core/actions/`.
4. Write the pipeline modules it calls (`core/ingestion/`, `core/retrieval/`, `core/orchestrator/`).
5. Write the route in `api/routes/`.
6. Register the route in `api/server/run_api.py`.
7. Add or update the docs in `docs/api/` and `docs/architecture/`.
8. Manually verify the contract end to end with curl.

Do not start at step 5 just because routes feel like the obvious place to start. The contract comes first, the action comes second, the route is the last thing you write.
