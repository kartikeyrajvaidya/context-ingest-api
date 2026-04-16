# Batch 3a — Ingestion Pipeline ✅

> **Status:** ✅ shipped + acceptance pass 2026-04-15.
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Skills consulted:** `context-ingest-api-backend`, `context-ingest-rag-pipeline`

## 1. Goal

An operator can ingest real URLs and raw text files into ContextIngest from the CLI against a real OpenAI key. A second run against unchanged content is a no-op. A second run against changed content replaces the old chunks atomically.

Batch 3a ships ingestion only. Query, feedback, rate limiting, reembed, and public docs all belong to later sub-batches.

## 2. Scope

### In

- `core/actions/ingest_document.ingest_document` — the single reusable async action.
- Four pipeline stages under `core/ingestion/`: `fetcher`, `cleaner`, `chunker`, `pipeline`.
- `core/services/embeddings.py` — the only module that imports `openai` in 3a.
- `scripts/ingest_url.py` and `scripts/ingest_batch.py` — CLI wrappers.
- `Document.get_by_source_url` and `Chunk.delete_by_document_id` classmethods.
- `IngestResponseSchema.document_id` widened to `str | None` (already landed).
- Removal of `api/routes/ingest.py` and its router registration (already landed).
- CHANGELOG entry.

### Out (deferred)

| Item | Where |
|---|---|
| `POST /v1/query` + retrieval/orchestration | Batch 3b |
| `POST /v1/feedback` + `record_feedback` | Batch 3c |
| Real IP rate limiter | Batch 3d |
| `scripts/reembed_all.py` | Batch 3e |
| Public docs (`docs/api/{query,feedback}.md`, architecture, guides) | Batch 3f |
| `robots.txt` awareness in the fetcher | v0 non-goal |
| `POST /v1/ingest` / `POST /v1/refresh` HTTP route | Future batch (the action is reusable) |

## 3. Rules

1. **Layering.** Routes never import `core/services/` or `db/`. Actions never import `fastapi`. Services never know what a "document" or "chunk" is. `openai` is imported only from `core/services/`. Env vars only in `configs/`. Prompts only in `core/services/prompts.py`.
2. **Transaction boundary.** The action owns the transaction. Pipeline modules receive the session; they do not open one.
3. **Narrow diff.** No speculative helpers, no generic factories. Two concrete use cases trigger an abstraction; one does not.
4. **Contract enforcement.** `IngestRequestSchema` / `IngestResponseSchema` remain the public contract, enforced with `extra="forbid"`.
5. **Logging.** One meaningful success log per ingestion run. Never log raw HTML, raw extracted text, full chunk bodies, or embedding vectors. No `print` outside `scripts/`.
6. **No migrations.** The `documents` and `chunks` tables from Batch 2 are sufficient.
7. **Rerun-safety.** SHA-256 over cleaned text, not raw HTML. Unchanged content must not call the embeddings API.
8. **Embeddings.** One batched OpenAI call per document, with `OPENAI_TIMEOUT_SECONDS`. No retries in 3a — the CLI script exits non-zero and the operator re-runs; the rerun hash makes that free.

## 4. Implementation order

1. `core/services/embeddings.py`.
2. `core/ingestion/fetcher.py`.
3. `core/ingestion/cleaner.py`.
4. `core/ingestion/chunker.py`.
5. `core/ingestion/pipeline.py`.
6. `Document.get_by_source_url` + `Chunk.delete_by_document_id`.
7. `core/actions/ingest_document.py`.
8. `scripts/__init__.py`, `scripts/ingest_url.py`, `scripts/ingest_batch.py`.
9. `CHANGELOG.md` under `[Unreleased]`.
10. Manual acceptance pass (§10).

## 5. File-by-file

### 5.1 `core/services/embeddings.py`

The only module in 3a that imports `openai`. Wraps embedding batching and the per-request timeout. Knows nothing about documents, chunks, or URLs.

```python
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return a dense vector for each input string, preserving order.

    Raises whatever OpenAI raises on fatal errors (auth, rate limit,
    timeout, network); the action decides how to handle them.
    """
```

- Constructs `AsyncOpenAI(api_key=LLMConfig.OPENAI_API_KEY, timeout=LLMConfig.OPENAI_TIMEOUT_SECONDS)` inline. No shared client factory yet — 3b adds the second use case (`llm.py`) that triggers the extraction.
- Rejects empty input with `ValueError("embed_texts called with empty input")` — defensive, cheap.
- Splits into sub-batches of at most `OPENAI_EMBEDDING_BATCH_LIMIT = 2048` (module-level constant — OpenAI's hard cap). Per sub-batch: `await client.embeddings.create(model=LLMConfig.OPENAI_EMBEDDING_MODEL, input=sub_batch)`, then extend with `[item.embedding for item in response.data]`. Trusts OpenAI's ordering guarantee.
- Typical documents (≤100 chunks) execute the loop once. Sub-batching is insurance, not overhead.
- No logging (the action logs at the boundary).

### 5.2 `core/ingestion/fetcher.py`

```python
class FetchError(Exception):
    """Non-fatal fetch failure: HTTP error, timeout, DNS, TLS, or body too large."""


@dataclass(frozen=True)
class FetchedPage:
    url: str    # final URL after redirects
    html: str   # raw body, UTF-8 decoded


async def fetch_url(url: str) -> FetchedPage: ...
```

- One `httpx.AsyncClient` per call. Timeout: `Timeout(connect=5.0, read=20.0, write=5.0, pool=5.0)`. Not env-configurable in 3a — one caller, no second use case.
- `follow_redirects=True`, `max_redirects=5`.
- User-Agent: `ContextIngest/0.1 (+https://github.com/kartikeyrajvaidya/context-ingest-api)`.
- `response.raise_for_status()` + `TimeoutException` + `RequestError` → wrap as `FetchError(f"fetch {url}: {reason}")`.
- Body-size cap: `len(response.content) > 10_000_000` (10 MB) → `FetchError("response body too large")`.
- No logging. Errors carry enough context for the action's handler.
- Not in 3a: robots.txt, per-host throttling, caching, conditional GETs.

### 5.3 `core/ingestion/cleaner.py`

Pure sync. Handles HTML and raw text.

```python
class EmptyContentError(Exception):
    """Cleaner extracted nothing usable."""


@dataclass(frozen=True)
class CleanedContent:
    text: str
    title: str | None


def extract_content(html: str, url: str | None = None) -> CleanedContent: ...
def clean_raw_text(raw: str, is_markdown: bool = False) -> str: ...
```

- **HTML path:** `trafilatura.extract(html, url=url, include_comments=False, include_tables=True, favor_precision=True)` for body; `trafilatura.extract_metadata(html).title` for title (may be `None`). Empty → `EmptyContentError("no extractable content")`.
- **Text path:** `unicodedata.normalize("NFC", ...)`, replace smart quotes / em-dashes / ellipsis with ASCII, strip lingering HTML tags, collapse runs of spaces/tabs, collapse 3+ newlines to 2. When `is_markdown=True`, also strips fenced code blocks, ATX headings, bold/italic, link/image syntax, inline code, blockquote prefixes, list markers, and horizontal rules via a private `_strip_markdown` regex helper.
- Shared `_collapse_whitespace()` helper runs on both paths so they stay in sync.
- Empty post-normalization → `EmptyContentError`.

### 5.4 `core/ingestion/chunker.py`

Pure sync. Deterministic.

```python
def count_tokens(text: str) -> int: ...
def chunk_text(
    text: str,
    chunk_size: int = LLMConfig.CHUNK_TOKEN_SIZE,
    overlap: int = LLMConfig.CHUNK_TOKEN_OVERLAP,
    min_chunk_size: int = 50,
) -> list[str]:
    """Recursive-separator chunker using the cl100k_base tokenizer."""
```

**Algorithm — recursive separator hierarchy:**

```
1. _ENCODING = tiktoken.get_encoding("cl100k_base"), module-level.
2. Separators tried in order: ["\n\n", "\n", ". ", " "].
3. _recursive_split(text, chunk_size, separators):
     a. count_tokens(text) <= chunk_size → return [text.strip()].
     b. separators empty → _split_by_tokens(text, chunk_size).
     c. Split on separators[0]. Pack parts into `current` while
        count_tokens(current + sep + part) <= chunk_size.
        When it doesn't fit: flush `current`; if `part` alone
        exceeds chunk_size, recurse with remaining separators;
        otherwise start a new buffer with `part`.
     d. Flush final buffer.
4. _split_by_tokens — last-resort token-boundary split.
5. _apply_overlap — post-pass: for each chunk after the first,
   prepend the tail `overlap` tokens of the previous chunk.
6. Drop chunks with count_tokens(c) < min_chunk_size.
```

**Invariants:**
- `chunk_text("", ...) == []`, `chunk_text("   \n  ", ...) == []`.
- No chunk exceeds `chunk_size + overlap` tokens.
- All chunks have `count_tokens(c) >= min_chunk_size`.
- Deterministic: same `(text, chunk_size, overlap)` always produces the same list.

Two INFO log lines (explicit exception to the "no logging in pipeline modules" rule — load-bearing for operator trust): `"Chunked text into %d chunks"` per call, and `"Dropped %d chunks below %d-token minimum"` only when `dropped > 0`. `min_chunk_size=50` because fragments below 50 tokens are usually footer/nav boilerplate.

### 5.5 `core/ingestion/pipeline.py`

```python
@dataclass(frozen=True)
class PipelineInput:
    source_url: str      # action synthesizes text:// for text-only
    text: str            # already cleaned
    title: str | None


@dataclass(frozen=True)
class IngestResult:
    document_id: str
    status: Literal["ingested", "unchanged"]
    chunks: int


async def ingest(session: AsyncSession, pipeline_input: PipelineInput) -> IngestResult: ...
```

The pipeline returns a dataclass, not `IngestResponseSchema`, because `IngestResult` cannot represent `"failed"` — failure is signalled by an exception raised earlier (fetcher or cleaner). The action maps pipeline result or caught exception to the final schema. The pipeline's outcomes are "wrote" or "noop", not tri-state.

**Flow:**

```
1. content_hash = sha256(pipeline_input.text.encode("utf-8")).hexdigest()
2. existing = await Document.get_by_source_url(source_url)
3. if existing and existing.content_hash == content_hash:
       return IngestResult(existing.id, "unchanged", existing.chunk_count)
4. chunks_text = chunker.chunk_text(
       text, LLMConfig.CHUNK_TOKEN_SIZE, LLMConfig.CHUNK_TOKEN_OVERLAP,
   )
5. if not chunks_text: raise EmptyContentError("chunker produced zero chunks")
6. embeddings = await embeddings.embed_texts(chunks_text)
7. assert len(embeddings) == len(chunks_text)
8. If existing: Chunk.delete_by_document_id(existing.id);
   update existing's content_hash, title, status, chunk_count.
   Else: Document.create(...).
9. Insert new Chunk rows, one per (text, embedding) pair, with `ord` = index.
10. await session.flush()  (no commit — the action's context manager commits)
11. return IngestResult(document.id, "ingested", len(chunks_text))
```

- All DB work via model classmethods (`Document.create`, `Chunk.create`, `Document.get_by_source_url`, `Chunk.delete_by_document_id`). No raw SQL.
- Bulk chunk insert is `await Chunk.create(...)` in a loop. Typical documents have ≤30 chunks, so this is fine. Switch to `session.add_all(...)` only if profiling demands it.
- No try/except around the embedding call. Fatal OpenAI errors propagate; the context manager rolls back.
- `sha256` is stdlib.

### 5.6 `core/actions/ingest_document.py`

Single callable shared by both CLI scripts and any future refresh endpoint. Owns the transaction. Maps non-fatal failures to `status: "failed"`. Emits exactly one log line per run.

**Flow:**

```
1. If request.url is not None:
       try: page = await fetcher.fetch_url(str(request.url))
       except FetchError as e:
           logger.warning("Ingest failed (fetch): url=%s reason=%s", ...)
           return IngestResponseSchema(None, "failed", 0)
       try: cleaned = cleaner.extract_content(page.html, url=page.url)
       except EmptyContentError as e:
           logger.warning("Ingest failed (empty): url=%s reason=%s", ...)
           return IngestResponseSchema(None, "failed", 0)
       source_url = page.url
       text = cleaned.text
       title = request.title or cleaned.title

   Else (text-only):
       try: text = cleaner.clean_raw_text(request.text, is_markdown=False)
       except EmptyContentError as e:
           logger.warning("Ingest failed (empty text): reason=%s", ...)
           return IngestResponseSchema(None, "failed", 0)
       title = request.title
       source_url = f"text://{sha256(text.encode()).hexdigest()[:16]}"

2. async with commit_transaction_async() as session:
       try:
           result = await pipeline.ingest(
               session,
               PipelineInput(source_url, text, title),
           )
       except EmptyContentError as e:
           logger.warning("Ingest failed (empty after chunk): ...")
           return IngestResponseSchema(None, "failed", 0)

3. logger.info(
       "Ingested document id=%s source=%s status=%s chunks=%d",
       result.document_id, source_url, result.status, result.chunks,
   )
   return IngestResponseSchema(
       document_id=result.document_id,
       status=result.status,
       chunks=result.chunks,
   )
```

**Why `EmptyContentError` is caught in two places.** trafilatura may produce non-empty text that the chunker then drops (whitespace-only paragraphs). Either stage is a legitimate origin of "nothing to embed", and both must map to `status: "failed"`.

**Why the transaction wraps only the pipeline call.** Fetch and clean are network/CPU work that must not hold a DB session. The transaction stays short; the connection pool stays happy.

**Logging.** One INFO on success or unchanged; one WARNING on non-fatal failures (fetch/empty). Never log `text`, `html`, chunk text, or embeddings.

### 5.7 `db/models/documents.py` (modify)

```python
@classmethod
async def get_by_source_url(cls, source_url: str) -> "Document | None":
    return await cls.filter_first(cls.source_url == source_url)
```

### 5.8 `db/models/chunks.py` (modify)

```python
@classmethod
async def delete_by_document_id(cls, document_id: str) -> None:
    session = await db.get_session()
    await session.execute(delete(cls).where(cls.document_id == document_id))
```

The FK cascade would cover document deletion, but we update the document in place on rerun — so we need the explicit chunk-delete.

### 5.9 `scripts/__init__.py`

Empty file so `python -m scripts.ingest_url` works.

### 5.10 `scripts/ingest_url.py`

```
python -m scripts.ingest_url --url URL [--title TITLE]
python -m scripts.ingest_url --text-file PATH --source SOURCE [--title TITLE]
```

- Exactly one of `--url` or `--text-file` required.
- `--source` is required with `--text-file` (becomes the stable canonical `source_url`, e.g. `internal://faq-setup`) and forbidden with `--url`.
- `argparse` (stdlib). `dotenv.load_dotenv()` at the top of `main()`. `asyncio.run(_run_async(args))`.
- Inside `_run_async`: build `IngestRequestSchema`, `await db.connect()`, call `ingest_document(req)`, `await db.disconnect()`.
- Prints one line: `<document_id|-> <status> chunks=<N> <source_url>`.
- Exit codes: 0 on `ingested`/`unchanged`, 1 on `failed`, 2 on argparse errors, 3 on uncaught exception.
- For `--text-file`: reads as UTF-8. `.md`/`.markdown` → `cleaner.clean_raw_text(raw, is_markdown=True)` before building the schema (keeps the frozen `IngestRequestSchema.text` contract clean: "already plain text"). `.txt` or other → raw bytes through; the action's `clean_raw_text(is_markdown=False)` call normalizes whitespace.
- Must not: reach into `core/ingestion/` or `db/` directly, wrap the action in retries, log at INFO level.

### 5.11 `scripts/ingest_batch.py`

```
python -m scripts.ingest_batch --file urls.txt [--stop-on-error]
```

- Reads `--file` as UTF-8. Blank lines and lines starting with `#` skipped.
- Each non-comment line is a URL.
- Default: continue on `failed`. `--stop-on-error`: exit 1 on first `failed`.
- Final summary: `ingested=N unchanged=M failed=K`.
- One shared DB connection for the whole loop. Serial only — parallelism is a knob worth adding only once a real need appears (and the OpenAI rate-limit math for parallel calls is nontrivial).

## 6. Error taxonomy

| Origin | Exception | Outcome |
|---|---|---|
| `fetcher.fetch_url` — HTTP 4xx/5xx, timeout, DNS, TLS, body too large | `FetchError` | action catches, WARNING, `IngestResponseSchema(None, "failed", 0)` |
| `cleaner.extract_content` — empty body | `EmptyContentError` | action catches, WARNING, same |
| `chunker.chunk_text` → `[]` (raised by pipeline) | `EmptyContentError` | action catches, WARNING, same |
| `pydantic.ValidationError` on `IngestRequestSchema` | raised at argparse layer | script stderr, exit 2 |
| `openai.RateLimitError` / `APIError` / `APIConnectionError` | propagates | transaction rollback, script exit 3 |
| `sqlalchemy.exc.*` | propagates | transaction rollback, script exit 3 |
| any other Exception | propagates | transaction rollback, script exit 3 |

Only three things become `status: "failed"`: fetch failure, empty cleaning, empty chunking. Everything else is a bug or infrastructure problem and exits non-zero with a traceback.

## 7. Logging catalog

| Emitter | Level | Message |
|---|---|---|
| `ingest_document` | INFO | `Ingested document id=%s source=%s status=%s chunks=%d` |
| `ingest_document` | WARNING | `Ingest failed (fetch): url=%s reason=%s` |
| `ingest_document` | WARNING | `Ingest failed (empty): url=%s reason=%s` |
| `ingest_document` | WARNING | `Ingest failed (empty text): reason=%s` |
| `ingest_document` | WARNING | `Ingest failed (empty after chunk): source=%s reason=%s` |
| `chunker` | INFO | `Chunked text into %d chunks` |
| `chunker` | INFO | `Dropped %d chunks below %d-token minimum` (only when > 0) |

No logs from fetcher, cleaner, pipeline, or embeddings. No logs from scripts (stdout only).

## 8. DB / model surface

No schema change, no migration, no index change. Model additions:

| Model | Change |
|---|---|
| `Document` | `@classmethod async def get_by_source_url(cls, source_url: str) -> Document \| None` |
| `Chunk` | `@classmethod async def delete_by_document_id(cls, document_id: str) -> None` |

## 9. Config surface

No new env vars. 3a uses only what `LLMConfig` already exposes:

| Env var | Default | Used by |
|---|---|---|
| `OPENAI_API_KEY` | `""` | `embeddings.py` |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | `embeddings.py` |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | matches `chunks.embedding` column width |
| `OPENAI_TIMEOUT_SECONDS` | `20` | `embeddings.py` |
| `CHUNK_TOKEN_SIZE` | `500` | `chunker.py` via `pipeline.py` |
| `CHUNK_TOKEN_OVERLAP` | `75` | same |

Fetcher timeouts are not env-configurable — one caller, no second use case.

**Dependencies.** None new: `openai`, `httpx`, `trafilatura`, `tiktoken`, `pgvector`, `SQLAlchemy`, `asyncpg`, `python-dotenv` are all already in `requirements.txt`.

## 10. Acceptance test

Manual pass. Preconditions: `.env` has a real `OPENAI_API_KEY`; `docker compose up --build -d` is healthy; `documents` and `chunks` empty.

**T1. Fresh ingest from URL.** `python -m scripts.ingest_url --url https://martinfowler.com/articles/lmql.html`. Expected: `doc_XXXXXXXXXX ingested chunks=N <url>`, `N > 0`. DB: one `documents` row, `N` `chunks` rows with non-null `embedding`, contiguous `ord` 0..N-1.

**T2. Rerun same URL.** Expected: `doc_XXXXXXXXXX unchanged chunks=N <url>` with the same `doc_id` and `N`. No new OpenAI call. DB row counts unchanged.

**T3. Ingest from raw text file.** Create `/tmp/faq.md`, run `python -m scripts.ingest_url --text-file /tmp/faq.md --source internal://faq-setup --title "Setup FAQ"`. Expected: `doc_XXX ingested chunks=1 internal://faq-setup`. DB row with `source_url='internal://faq-setup'`, `title='Setup FAQ'`.

**T4. Text file without `--source`.** Expected: `doc_XXX ingested chunks=1 text://<16 hex>`. DB row with `source_url` matching `text://[0-9a-f]{16}`.

**T5. Modified content triggers re-embedding.** Append to `/tmp/faq.md`, re-run T3. Expected: same `doc_id`, new `M ≥ 1`. Old chunks are gone (count equals new `M`).

**T6. Bad URL → failed.** `--url https://definitely-not-a-real-host-xyz.invalid`. Expected stdout `- failed chunks=0 ...`, exit 1, no new DB rows.

**T7. Empty content URL → failed.** A JavaScript-rendered SPA landing page trafilatura can't extract. Expected: `- failed chunks=0 ...`.

**T8. Bulk from file.** `/tmp/urls.txt` with a comment line, a blank line, and two URLs (one already ingested in T1). Expected: one summary line per URL, then `ingested=1 unchanged=1 failed=0`.

**T9. Ingest HTTP route is gone.** `curl -X POST http://localhost:8080/v1/ingest` → 404.

**T10. `/v1/query` and `/v1/feedback` stubs still 501.** Regression check.

**T11. Schema rejects unknown fields.** `IngestRequestSchema(url='...', foo='bar')` → `ValidationError`.

**T12. Schema rejects neither-url-nor-text.** `IngestRequestSchema()` → `ValidationError`.

**T13. Ruff + pre-commit pass.** All green. (Especially: no unused imports after removing `api/routes/ingest.py`.)

## 11. Rollout / rollback

Commit one logical group per step (pipeline modules / action / scripts). Every change is additive except the `api/routes/ingest.py` deletion and the `api/server/run_api.py` edit, both revertable from git. The schema change (`document_id: str | None`) is backwards-compatible.

## 12. Deviations from this plan

*(Fill in as deviations occur during implementation.)*

None yet.
