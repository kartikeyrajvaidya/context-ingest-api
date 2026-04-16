# Batch 3e — Reembed ⏳

> **Status:** ⏳ next up after 3d.
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Upstream contracts:** [`./3a-ingestion-pipeline.md`](./3a-ingestion-pipeline.md) §"embed_texts + sub-batching", [`../batch2/2c-migrations-and-tables.md`](../batch2/2c-migrations-and-tables.md) §"chunks"
> **Skills consulted:** `context-ingest-api-backend`, `context-ingest-rag-pipeline`

## 1. Goal

When an operator changes `OPENAI_EMBEDDING_MODEL` (same-dimension upgrade) existing chunks stay on the old vector space and hybrid search quality degrades silently. `scripts/reembed_all.py` walks every chunk, regenerates its embedding with the *current* model, and writes the new vector in place via a bulk UPDATE. One-shot operator CLI — never re-fetches source documents, never re-chunks, never changes chunk text.

3e ships the reembed script only. Public docs that reference it land in 3f.

## 2. Scope

### In

- `scripts/reembed_all.py` — one-shot CLI. Walks every row in `chunks`, re-embeds, bulk-writes vectors. Supports `--batch-size` and `--dry-run`.
- `Chunk.iter_for_reembed(batch_size)` — keyset-paginated async generator over `chunks`.
- `Chunk.update_embeddings_bulk(updates)` — single bulk `UPDATE ... FROM (VALUES ...)` per batch.
- `Chunk.count_all()` — used once for the `done/total` progress ratio (add only if missing).
- CHANGELOG entry.

### Out (deferred)

| Item | Why |
|---|---|
| `POST /v1/reembed` or any HTTP trigger | Non-goal. Reembed is operator-only; an HTTP trigger needs auth, which is a v0 non-goal. |
| `--model` flag | Non-goal. Script always reads the current env; operators who want to switch models change the env then run. A flag would tempt backdoor config overrides. |
| Cross-dimension reembed (1536 → 3072) | Non-goal. `chunks.embedding` is typed `Vector(1536)`; a dim change is a migration, not a script. See E3. |
| Re-chunking | Non-goal. Re-chunking means re-running the full ingestion pipeline — operators rerun `scripts/ingest_all.py` (which reads `data/sources.json`). |
| Idempotent skip via `embedding_model_version` column | Post-v0. A second run is already correct (same model → same bytes). Only interesting at 100k+ chunks. |
| Parallelism / resume-cursor | Post-v0. `embed_texts` is already batched; keyset ordering makes resume deterministic without a manual cursor. |
| pytest integration tests | Out of scope. v0 uses manual acceptance passes. |

## 3. Rules

1. **Layering.** `scripts/` imports from `db/` and `core/`, never from `api/`. No `fastapi` anywhere in `scripts/`.
2. **Idempotent by construction.** A second run against chunks already at the current model writes the same bytes back — wasteful but correct. No skip-logic in v0.
3. **One transaction per batch, not one giant transaction.** A crash mid-run leaves completed batches committed; the next run picks up from the beginning and redoes work idempotently.
4. **Streaming reads.** `iter_for_reembed` is an async generator yielding lists of ≤`batch_size` rows. Never loads the full `chunks` table into memory.
5. **Keyset pagination, not OFFSET.** `WHERE id > :last_id ORDER BY id ASC`. At 100k chunks, `OFFSET 90000` scans 90050 rows per call; keyset scans exactly `batch_size`.
6. **Bulk writes.** `UPDATE ... FROM (VALUES ...)` in one round trip per batch. Never a per-row loop.
7. **Narrow model surface.** Two (or three) classmethods on `Chunk`, nothing else. No maintenance service, no shared mixin.
8. **Env, not flags, for the model.** `OPENAI_EMBEDDING_MODEL` comes from `LLMConfig` — same as the ingestion pipeline. The final summary prints which model was used.
9. **`print()` for the human summary, `logger` for per-batch progress.** Same split as the 3a ingestion scripts.

## 4. Implementation order

1. `Chunk.iter_for_reembed` + `Chunk.update_embeddings_bulk` (+ `count_all` if missing) on `db/models/chunks.py`.
2. `scripts/reembed_all.py` wiring the read → embed → bulk write.
3. CHANGELOG under `[Unreleased]`.
4. Manual acceptance pass (§9).

## 5. File-by-file

### 5.1 `db/models/chunks.py` — new classmethods

```python
@classmethod
async def iter_for_reembed(cls, batch_size: int) -> AsyncIterator[list["Chunk"]]:
    last_id: str | None = None
    while True:
        stmt = (
            select(cls.id, cls.chunk_text)
            .order_by(cls.id.asc())
            .limit(batch_size)
        )
        if last_id is not None:
            stmt = stmt.where(cls.id > last_id)
        result = await db_session.execute(stmt)
        rows = result.all()
        if not rows:
            return
        yield [cls(id=row.id, chunk_text=row.chunk_text) for row in rows]
        last_id = rows[-1].id


@classmethod
async def update_embeddings_bulk(
    cls, updates: list[tuple[str, list[float]]]
) -> int:
    if not updates:
        return 0
    values_clause = ", ".join(
        f"(:id_{i}, :emb_{i}::vector)" for i in range(len(updates))
    )
    params: dict[str, object] = {}
    for i, (chunk_id, emb) in enumerate(updates):
        params[f"id_{i}"] = chunk_id
        params[f"emb_{i}"] = str(emb)  # pgvector accepts its text repr
    stmt = text(
        f"""
        UPDATE chunks AS c
        SET embedding = v.embedding
        FROM (VALUES {values_clause}) AS v(id, embedding)
        WHERE c.id = v.id
        """
    )
    result = await db_session.execute(stmt, params)
    return result.rowcount or 0


@classmethod
async def count_all(cls) -> int:
    result = await db_session.execute(select(func.count()).select_from(cls))
    return int(result.scalar_one())
```

- Reads only `id` and `chunk_text` — `tsv` is DB-generated, `embedding` is about to be overwritten.
- Raw `text()` for the bulk UPDATE — the ORM equivalent triggers change-tracking we don't want on thousands of rows.
- Parameters are numbered placeholders; zero SQL injection surface.
- pgvector parses `str(list_of_floats)` as its text form with an explicit `::vector` cast.

### 5.2 `scripts/reembed_all.py`

```python
async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    total = await Chunk.count_all()
    done = 0
    started = time.monotonic()
    model = LLMConfig.OPENAI_EMBEDDING_MODEL

    async for batch in Chunk.iter_for_reembed(batch_size=args.batch_size):
        texts = [c.chunk_text for c in batch]
        new_embeddings = await embed_texts(texts)
        if not args.dry_run:
            async with commit_transaction_async():
                await Chunk.update_embeddings_bulk(
                    [(c.id, emb) for c, emb in zip(batch, new_embeddings)]
                )
        done += len(batch)
        elapsed = time.monotonic() - started
        logger.info(
            "reembedded chunks=%d/%d elapsed_s=%.1f model=%s dry_run=%s",
            done, total, elapsed, model, args.dry_run,
        )

    elapsed = time.monotonic() - started
    summary = f"reembedded {done} chunks in {elapsed:.1f}s using {model}"
    if args.dry_run:
        summary += " (dry run — no writes)"
    print(summary)


if __name__ == "__main__":
    asyncio.run(main())
```

- `--batch-size` default `50` — 50 × ~500 tokens = ~25k tokens per call, below OpenAI's sub-batching cap.
- `--dry-run` still embeds (real timing + real API errors surface) but skips the write.
- One `commit_transaction_async()` block per batch; crash recovery is re-doing committed batches idempotently.
- `print()` to stdout for the final summary; `logger.info` for per-batch progress. Same split as `scripts/ingest_all.py`.
- No row locking. Concurrent ingestion + reembed is unsupported — documented as operator guidance in 3f.

## 6. Logging plan

Per-batch: `scripts.reembed_all - INFO - reembedded chunks=<done>/<total> elapsed_s=<s> model=<model> dry_run=<bool>`.
Final summary: `print()` to stdout, not logged.

Never logged: individual chunk ids, embedding vectors, OpenAI request/response bodies.

## 7. DB / config / deps

**DB.** No schema changes. The script only issues `UPDATE chunks SET embedding = ...`. HNSW index updates are more expensive than b-tree but acceptable for a one-shot maintenance op. `VACUUM ANALYZE chunks;` after a large run is a good operator habit — documented in 3f.

**Config.** No new env vars. Reads `OPENAI_EMBEDDING_MODEL`, `OPENAI_API_KEY`, `DB_*` (all unchanged).

**Dependencies.** None new.

## 8. Contract impact

None. Not part of any HTTP contract.

## 9. Acceptance test

Manual pass against the live compose stack. Preconditions: `docker compose up --build -d` healthy, valid `OPENAI_API_KEY`, at least one ingested document. Baseline snapshot:

```bash
docker compose exec -T postgres psql -U postgres -d context_ingest -c \
  "SELECT id, left(embedding::text, 40) FROM chunks ORDER BY id LIMIT 3;"
docker compose exec -T postgres psql -U postgres -d context_ingest -tAc \
  "SELECT COUNT(*) FROM chunks;"
```

**E1. Dry-run pass.**
```bash
docker compose exec -T context-ingest-api python -m scripts.reembed_all --dry-run
```
Expected: final `reembedded <N> chunks in <X>s using text-embedding-3-small (dry run — no writes)`. Snapshot rows identical to baseline. Log lines show `dry_run=True`.

**E2. Live pass.**
```bash
docker compose exec -T context-ingest-api python -m scripts.reembed_all --batch-size 10
```
Expected: stdout prints `reembedded N chunks in X.Xs using text-embedding-3-small`. Sample embeddings may differ microscopically (OpenAI is not bit-exact) but dimension unchanged. `COUNT(*)` equals baseline. A follow-up `POST /v1/query` for a known-good question returns sensible results.

**E3. Cross-dimension model change.** Out of scope — `Vector(1536)` rejects a 3072-dim write. Pending until a column-widening migration story is scoped.

**E4. Progress logs.** During E2, `docker compose logs -f context-ingest-api` shows one `reembedded chunks=X/Y ...` INFO line per batch, `done` monotonically increasing.

**E5. Crash recovery.** Run against ≥100 chunks with `--batch-size 5`. Ctrl-C mid-run. Re-run; completes without error. `done` equals full chunk count. Partially-updated chunks get overwritten again (idempotent).

**E6. Layering check.** `rg "^from fastapi|^import fastapi" scripts/` → zero matches.

**E7. Script imports.** `rg -n "^from api|^import api" scripts/reembed_all.py` → zero matches.

**E8. One round trip per batch.** Temporarily enable `log_statement = 'all'` on Postgres; confirm one `UPDATE chunks AS c ... FROM (VALUES ...)` per batch, not N per-row updates.

**E9. Entry point.** `python -m scripts.reembed_all --help` prints argparse help listing `--batch-size` and `--dry-run`.

## 10. Rollout / rollback

**Commits:**
1. `models: add Chunk.iter_for_reembed + Chunk.update_embeddings_bulk`
2. `scripts: add reembed_all.py`
3. `docs/CHANGELOG: record 3e`

**Rollback.** All additive. Reverting removes the script and classmethods; nothing in the running API depends on either. `docker compose up -d --force-recreate --no-deps context-ingest-api` suffices.

## 11. Deviations from this plan

*(Fill in as deviations occur during implementation.)*

None.
