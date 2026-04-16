# Batch 3c — Feedback ✅

> **Status:** ✅ shipped + acceptance pass 2026-04-15 (F1–F11 all green).
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Upstream contracts:** [`../batch2/2b-contracts-and-schemas.md`](../batch2/2b-contracts-and-schemas.md), [`../../api/feedback.md`](../../api/feedback.md), [`../batch2/2c-migrations-and-tables.md`](../batch2/2c-migrations-and-tables.md)
> **Skills consulted:** `context-ingest-api-backend`, `context-ingest-rag-pipeline`

## 1. Goal

`POST /v1/feedback` with a `query_id` returned from an earlier `POST /v1/query`. Attach a `rating` (operator-chosen vocabulary) and an optional free-form `reason`. Row persists in `feedback` with atomic replace semantics: a second POST for the same `query_id` overwrites in place — same PK, same `created_at`, advanced `updated_at`, new `rating`/`reason`. Unknown `query_id` → `404 {"message": "query not found"}`. Validation errors → `400` with per-field `errors` array.

Batch 3c ships feedback only. Rate limiting is 3d; reembed is 3e; public docs are 3f.

## 2. Scope

### In

- `POST /v1/feedback` — replaces the 501 stub in `api/routes/feedback.py`.
- `core/actions/record_feedback.record_feedback(request)` — owns the single transaction boundary.
- `core/actions/record_feedback.QueryNotFoundError` — plain domain exception; route maps it to HTTP 404.
- CHANGELOG entry.

**Nothing else.** No new services (feedback is one-table, one-row — `Feedback.upsert_by_query_id` already shipped in 2c), no new schemas (`FeedbackRequestSchema` is frozen in 2b), no migrations (feedback table + `created_at`/`updated_at` + `UNIQUE(query_id)` already shipped in 2c's `0002.sql`).

### Out (deferred)

| Item | Where |
|---|---|
| Real IP rate limiter | Batch 3d |
| `scripts/reembed_all.py` | Batch 3e |
| Public docs polish | Batch 3f |
| `GET /v1/feedback/{query_id}` | Non-goal for v0 — feedback is write-only server state |
| Per-user scoping | Non-goal for v0 (no auth) — frontends scope `query_id`s per user |
| CHECK constraint on `rating` vocabulary | Non-goal — operators pick the vocabulary; length + non-blank only |
| Feedback-specific rate limiter | The app-wide 3d middleware is sufficient |

## 3. Rules

1. **Layering.** The action never imports `fastapi`. 404 is a plain-Python `QueryNotFoundError` caught at the route and mapped to `HTTPException(404, detail="query not found")`.
2. **Transaction boundary.** One `commit_transaction_async()` block around the upsert. The existence check (`QueryRequest.get_by_id`) runs outside the transaction — a read-only lookup doesn't need commit semantics. If the row vanishes between check and write, the FK catches it and SQLAlchemy raises `IntegrityError` → 500 via the global handler. Race-narrow and acceptable for v0.
3. **Contract-first.** `FeedbackRequestSchema` is the only public input shape. Success is `204 No Content` — no body, no envelope. The `{"data": ...}` wrap is a query-path convention and does not apply here.
4. **Atomic replace semantics.** `INSERT ... ON CONFLICT (query_id) DO UPDATE`. Never a `SELECT` → `UPDATE` pair. Concurrent POSTs are safe and last-write-wins without application locking. `id` and `created_at` are preserved by omitting them from the `DO UPDATE SET`; only `rating`, `reason`, and `updated_at` are overwritten.
5. **Narrow diff.** Action file + route file = entire change. No service module, no schema module, no helper extraction.
6. **Logging.** One INFO line per successful write: `query_id`, `rating`, `has_reason` boolean. Never log `reason` text — it's free-form user input and potential PII. No log on the 404 path (the access log already carries the status).
7. **No migrations.** 2c shipped the entire feedback schema.
8. **No retries.** Clients retry. `IntegrityError` from a race becomes a 500.

## 4. Implementation order

1. `core/actions/record_feedback.py` — existence check + transaction + upsert.
2. Rewrite `api/routes/feedback.py` — replaces 501 stub, wires the action, maps `QueryNotFoundError` to 404.
3. `CHANGELOG.md` under `[Unreleased]`.
4. Manual acceptance pass (§9).

## 5. File-by-file

### 5.1 `core/actions/record_feedback.py`

```python
"""Record feedback for a prior query with replace semantics."""

from core.schema.feedback import FeedbackRequestSchema
from db.models.feedback import Feedback
from db.models.query_requests import QueryRequest
from db.session import commit_transaction_async
from libs.logger import get_logger

logger = get_logger(__name__)


class QueryNotFoundError(Exception):
    """Raised when a feedback POST references an unknown `query_id`."""


async def record_feedback(request: FeedbackRequestSchema) -> None:
    existing = await QueryRequest.get_by_id(request.query_id)
    if existing is None:
        raise QueryNotFoundError(request.query_id)

    async with commit_transaction_async():
        await Feedback.upsert_by_query_id(
            query_id=request.query_id,
            rating=request.rating,
            reason=request.reason,
        )

    logger.info(
        "Recorded feedback query_id=%s rating=%s has_reason=%s",
        request.query_id,
        request.rating,
        request.reason is not None,
    )
```

- Existence check is outside the transaction — read-only lookup doesn't need commit semantics.
- `QueryNotFoundError` carries the bad `query_id` as its only arg.
- Nothing in this module imports `fastapi`.
- `request.reason` arrives already trimmed-to-None by the schema validator. No re-trimming.

### 5.2 `api/routes/feedback.py` (rewrite)

```python
from fastapi import APIRouter, HTTPException, Response

from core.actions.record_feedback import QueryNotFoundError, record_feedback
from core.schema.feedback import FeedbackRequestSchema

router = APIRouter()


@router.post("", status_code=204)
async def post_feedback(request: FeedbackRequestSchema) -> Response:
    try:
        await record_feedback(request)
    except QueryNotFoundError as exc:
        raise HTTPException(status_code=404, detail="query not found") from exc
    return Response(status_code=204)
```

- Router is already registered in `api/server/run_api.py` from 2a.
- `status_code=204` on the decorator + explicit `Response(status_code=204)` — the explicit form is self-documenting.
- `from exc` preserves the cause chain for debug.
- `extra="forbid"` on `FeedbackRequestSchema` handles unknown-field rejection via the existing `RequestValidationError` handler.
- No response envelope — `204` means no body.

## 6. Contract recap

From `docs/api/feedback.md` (frozen in 2b; unchanged in 3c):

| Field | Type | Required | Constraints |
|---|---|---|---|
| `query_id` | string | yes | Non-blank, trimmed. Must reference an existing row in `query_requests`. |
| `rating` | string | yes | 1–32 chars, non-blank, trimmed. Free-form vocabulary. |
| `reason` | string | no | ≤1000 chars, trimmed. Empty-after-trim → `null`. |

Any other field → 400 (`extra="forbid"`).

| Status | Body | When |
|---|---|---|
| `204` | (empty) | Feedback recorded (first insert or replace). |
| `400` | `{"message": "Validation failed", "errors": [...]}` | Body fails validation. |
| `404` | `{"message": "query not found"}` | `query_id` unknown. |
| `429` | `{"message": "Rate limit exceeded"}` | IP rate limiter tripped (lands in 3d). |
| `500` | `{"message": "Internal server error"}` | Any unhandled exception. |

## 7. Logging plan

One added log point: `core.actions.record_feedback - INFO - Recorded feedback query_id=%s rating=%s has_reason=%s` on successful write.

Validation failures flow through the existing global handler. Query-not-found and 5xx flow through the existing HTTP exception handler / access log. No WARNING on 404 — that would double-log a normal client error.

Never logged: `reason` text (PII surface), the bad `query_id` on 404 (already in the access log + request body), the new PK (internal state).

## 8. DB / config / deps

**DB.** No schema changes. `feedback` shipped in 2c's `0002.sql` with `id`, `query_id` (`UNIQUE`, FK `ON DELETE CASCADE`), `rating`, `reason`, `created_at`, `updated_at`, and b-tree indexes on both timestamps. Write pattern (built by `Feedback.upsert_by_query_id` via `sqlalchemy.dialects.postgresql.insert(...).on_conflict_do_update(...)`):

```sql
INSERT INTO feedback (id, query_id, rating, reason, created_at, updated_at)
VALUES ($1, $2, $3, $4, now(), now())
ON CONFLICT (query_id) DO UPDATE SET
    rating     = EXCLUDED.rating,
    reason     = EXCLUDED.reason,
    updated_at = now();
```

Only `rating`, `reason`, `updated_at` appear in `DO UPDATE SET`. `id` and `created_at` are preserved.

**Config.** No new env vars. `DB_STATEMENT_TIMEOUT` applies as usual.

**Dependencies.** None new.

## 9. Acceptance test

Manual pass. Preconditions: compose stack healthy, valid `OPENAI_API_KEY` (for F10), one ingested document, one `query_requests` row to use as `$QID` (get via `POST /v1/query` or `SELECT id FROM query_requests ORDER BY created_at DESC LIMIT 1`).

**F1. Happy path — first insert.**
```bash
curl -sS -o /dev/null -w "http=%{http_code}\n" -X POST http://localhost:8080/v1/feedback \
  -H 'content-type: application/json' \
  -d "{\"query_id\":\"$QID\",\"rating\":\"helpful\",\"reason\":\"  answered with the right citations  \"}"
```
Expected: `http=204`. DB: new `feedback` row with `rating='helpful'`, `reason='answered with the right citations'` (trimmed), `created_at = updated_at`, fresh `fbk_<random10>` PK.

**F2. Replace semantics — PK and `created_at` preserved.** Capture `created_at` after F1, then POST again with different `rating`/`reason`. DB invariants: `COUNT(*)=1`, same `id`, same `created_at`, `updated_at > created_at`, new `rating`/`reason` visible.

**F3. No reason.** `{"query_id":"$QID","rating":"ok"}` → `204`, `reason IS NULL`.

**F4. Unknown `query_id` → 404** with body `{"message":"query not found"}`.

**F5. Missing `rating` → 400** with `type=missing` on `loc=["body","rating"]`.

**F6. Blank `rating` → 400** with `type=value_error`, `msg="Value error, must not be blank"`.

**F7. `rating` > 32 chars → 400** with `type=string_too_long`, `ctx.max_length=32`.

**F8. Unknown field → 400** with `type=extra_forbidden`.

**F9. `reason` empty-after-trim → stored as `NULL`** (the `_reason_trimmed_or_none` validator handles this).

**F10. Feedback on a no-answer query.** Run `POST /v1/query` with an off-topic question to force `status='no_answer'`, then `POST /v1/feedback` against that `query_id`. Expected: `204`, row persisted. This is the most valuable feedback signal — distinguishing "refusing was right" from "you should have found something".

**F11. Layering check.** `rg "^from fastapi|^import fastapi" core/actions/record_feedback.py` → zero matches.

## 10. Rollout / rollback

**Commits:**
1. `actions: add record_feedback action + QueryNotFoundError`
2. `routes: wire POST /v1/feedback to the action (replaces 501 stub)`
3. `docs/CHANGELOG: record 3c`

**Rollback.** Everything additive except the route rewrite. Revert restores the 501 stub; DB stays clean. No migration, no env vars, no new deps. `docker compose up -d --force-recreate --no-deps context-ingest-api` suffices.

## 11. Deviations from this plan

*(Fill in as deviations occur during implementation.)*

None.
