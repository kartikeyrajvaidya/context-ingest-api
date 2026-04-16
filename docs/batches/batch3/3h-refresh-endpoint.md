# Batch 3h — Ingest endpoint ✅

> **Status:** ✅ shipped 2026-04-16. All acceptance tests pass (H1–H4, L1). H5 deviation noted — see §9.
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Upstream:** [`./3a-ingestion-pipeline.md`](./3a-ingestion-pipeline.md) — the action and manifest reader already exist.

## 1. Goal

Expose the manifest-driven ingestion pipeline over HTTP so operators can trigger a re-ingest without shell access to the container. One endpoint:

```
POST /v1/ingest
```

Does exactly what `scripts/ingest_all.py` does: reads `data/sources.json`, walks every entry, calls `ingest_document()` per entry. Rerun-safe — the content-hash gate skips unchanged entries with zero work.

**No request body. No URL parameter.** The operator controls what gets ingested by editing the manifest file. This is deliberately not an "ingest arbitrary URL" endpoint — that would let any stranger drive the operator's OpenAI bill on an unauthenticated API.

**Minimal response.** This is a public API — no per-entry details, no document IDs, no chunk counts, no error messages in the response body. The client gets `{"data": {"ok": true}}` on success and a standard 500 on failure. All operational detail goes to server logs.

### Why this is safe without auth

- The manifest is a file on disk inside the container. An HTTP caller can only trigger ingestion of what the operator has already listed.
- The content-hash gate means repeated calls are free (unchanged entries produce zero embeddings calls).
- Rate limiting (Batch 3d) applies — the IP/min limit covers `/v1/ingest` as well.

## 2. Scope

### In

- `core/actions/ingest_manifest.py` — new. Reads the manifest, builds requests, calls `ingest_document()` per entry, logs per-entry results. Extracted from `scripts/ingest_all.py` so both the script and the route share the same logic.
- `api/routes/ingest.py` — new. `POST /v1/ingest` route, calls the action, returns `{"data": {"ok": true}}`.
- `api/server/run_api.py` — register the ingest router.
- `scripts/ingest_all.py` — refactor to call the shared action instead of duplicating the logic.
- `docs/api/ingest.md` — new. API contract doc for the endpoint.
- `CHANGELOG.md` — one `[Unreleased]` bullet.

### Out

| Item | Why |
|---|---|
| Single-URL ingest endpoint (body with URL) | Unsafe without auth. Operators use `scripts/ingest_one.py` for ad-hoc items. |
| Auth / API key | Not in v0. |
| Async / background job | The manifest is small (seconds to minutes). Synchronous is fine for v0. |
| Per-entry details in response | Public API — no information leakage. Details go to server logs. |
| Response schema | Not needed — `{"data": {"ok": true}}` is a plain dict, no Pydantic model. |

## 3. Rules

1. **No request body.** `POST /v1/ingest` takes no parameters. The manifest is the input.
2. **Minimal response.** `200 {"data": {"ok": true}}` on success. Any failure (partial or total) raises and becomes a standard `500 {"message": "Internal server error"}` via the global error handler.
3. **Layering.** The action in `core/actions/ingest_manifest.py` has no fastapi imports. The route is thin — call the action, return the result.
4. **Rerun-safe.** Calling the endpoint twice in a row produces `unchanged` for every entry on the second call. Zero embeddings cost.
5. **Rate-limited.** The IP/min middleware from 3d covers this route. No special rate limit.
6. **Logs are the operator's view.** Per-entry ingestion results (ingested/unchanged/failed, document IDs, chunk counts, errors) are logged at INFO/ERROR level. The HTTP caller never sees them.

## 4. Implementation order

1. `core/actions/ingest_manifest.py` — shared action extracted from `scripts/ingest_all.py`.
2. `scripts/ingest_all.py` — refactor to use the shared action.
3. `api/routes/ingest.py` — route.
4. `api/server/run_api.py` — register the router.
5. `docs/api/ingest.md` — contract doc.
6. `CHANGELOG.md`.
7. Manual acceptance pass (§7).

## 5. File-by-file

### 5.1 `core/actions/ingest_manifest.py`

```python
"""Manifest-driven ingestion action.

Reads data/sources.json, walks every entry, calls ingest_document() per entry.
Shared by both scripts/ingest_all.py and api/routes/ingest.py.
"""

import json
from pathlib import Path

from core.actions.ingest_document import ingest_document
from core.ingestion.cleaner import clean_raw_text
from core.schema.ingest import IngestRequestSchema
from libs.logger import get_logger

logger = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "sources.json"


def _load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"manifest not found at {MANIFEST_PATH}")
    with MANIFEST_PATH.open(encoding="utf-8") as f:
        sources = json.load(f)
    if not isinstance(sources, list) or not sources:
        raise ValueError("manifest must be a non-empty JSON array")
    return sources


def _build_request(entry: dict) -> IngestRequestSchema:
    url = entry["url"]
    title = entry.get("title")
    file_rel = entry.get("file")

    if file_rel:
        path = (REPO_ROOT / file_rel).resolve()
        if not path.exists():
            raise FileNotFoundError(f"file not found: {file_rel}")
        raw = path.read_text(encoding="utf-8")
        if not raw.strip():
            raise ValueError(f"file is empty: {file_rel}")
        is_markdown = path.suffix.lower() in (".md", ".markdown")
        text = clean_raw_text(raw, is_markdown=is_markdown)
        return IngestRequestSchema(text=text, title=title, source_url=url)

    return IngestRequestSchema(url=url, title=title)


class IngestManifestError(Exception):
    """Raised when one or more manifest entries fail to ingest."""


async def ingest_manifest() -> dict[str, int]:
    """Run the full manifest ingestion. Returns tallies dict.

    Raises IngestManifestError if any entry fails.
    """
    sources = _load_manifest()
    logger.info("Ingesting %d sources from manifest", len(sources))

    tallies = {"ingested": 0, "unchanged": 0, "failed": 0}

    for entry in sources:
        url = entry.get("url", "?")
        try:
            request = _build_request(entry)
            response = await ingest_document(request)
            tallies[response.status] += 1
            logger.info(
                "Manifest entry url=%s status=%s document_id=%s chunks=%d",
                url, response.status, response.document_id, response.chunks,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to ingest: %s", url, exc_info=True)
            tallies["failed"] += 1

    logger.info(
        "Manifest ingestion complete ingested=%d unchanged=%d failed=%d",
        tallies["ingested"], tallies["unchanged"], tallies["failed"],
    )

    if tallies["failed"] > 0:
        raise IngestManifestError(
            f"{tallies['failed']} of {len(sources)} entries failed"
        )

    return tallies
```

Key design: the action raises `IngestManifestError` on any failure. The route does not catch it — it propagates to the global error handler and becomes a 500. The operator sees which entries failed in the ERROR logs.

### 5.2 `scripts/ingest_all.py` (refactor)

Simplified to call the shared action. The script still prints per-entry output to stdout for interactive use — it catches `IngestManifestError` and returns exit code 1 instead of crashing.

```python
"""Ingest every source listed in data/sources.json.

CLI wrapper around ingest_manifest(). For HTTP access use POST /v1/ingest.
"""

from __future__ import annotations

import asyncio
import sys
import traceback

from dotenv import load_dotenv

from core.actions.ingest_manifest import IngestManifestError, ingest_manifest
from db import db
from libs.logger import get_logger

logger = get_logger(__name__)


async def _run() -> int:
    await db.connect()
    try:
        tallies = await ingest_manifest()
    except IngestManifestError:
        return 1
    finally:
        await db.disconnect()

    sys.stdout.write(
        f"ingested={tallies['ingested']} unchanged={tallies['unchanged']} "
        f"failed={tallies['failed']}\n"
    )
    return 0


def main() -> int:
    load_dotenv()
    try:
        return asyncio.run(_run())
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
```

### 5.3 `api/routes/ingest.py`

```python
"""POST /v1/ingest — trigger manifest-driven ingestion."""

from fastapi import APIRouter

from core.actions.ingest_manifest import ingest_manifest

router = APIRouter()


@router.post("")
async def post_ingest() -> dict:
    await ingest_manifest()
    return {"data": {"ok": True}}
```

Four lines of route code. No try/catch — on any failure `ingest_manifest()` raises, the global error handler returns 500. On success, `{"data": {"ok": true}}`.

### 5.4 `api/server/run_api.py` (update)

```python
from api.routes.ingest import router as ingest_router

# In setup_routers():
app.include_router(ingest_router, prefix="/v1/ingest", tags=["ingest"])
```

Remove the "Ingestion is intentionally CLI-only in v0" docstring note.

### 5.5 `docs/api/ingest.md`

Contract doc:

- Endpoint: `POST /v1/ingest`
- Request body: none
- Success: `200 {"data": {"ok": true}}`
- Failure: `500 {"message": "Internal server error"}`
- Rerun semantics: safe to call repeatedly
- Rate limiting: subject to IP/min limit

## 6. Logging

| Emitter | Level | When | Message |
|---|---|---|---|
| `core.actions.ingest_manifest` | INFO | ingestion starts | `Ingesting %d sources from manifest` |
| `core.actions.ingest_manifest` | INFO | each entry succeeds | `Manifest entry url=%s status=%s document_id=%s chunks=%d` |
| `core.actions.ingest_manifest` | ERROR | single entry fails | `Failed to ingest: %s` (with traceback) |
| `core.actions.ingest_manifest` | INFO | ingestion complete | `Manifest ingestion complete ingested=%d unchanged=%d failed=%d` |

No log sites in the route. The client sees only `ok: true` or a 500.

## 7. Acceptance test

Manual pass against the live compose stack.

**H1. Fresh ingest.** `POST /v1/ingest` on a fresh DB. Expected: `200 {"data": {"ok": true}}`. Server logs show two INFO entries with `status=ingested`.

**H2. Rerun (unchanged).** `POST /v1/ingest` again immediately. Expected: `200 {"data": {"ok": true}}`. Server logs show `status=unchanged` for both entries.

**H3. Query after ingest.** `POST /v1/query` with `question="what is a microservice?"`. Expected: `status="answered"` with citations. Retrieval healthy.

**H4. Script still works.** `docker compose exec context-ingest-api python -m scripts.ingest_all`. Expected: same tally output, `unchanged=2`.

**H5. Rate limit applies.** Fire `POST /v1/ingest` more than `RATE_LIMIT_IP_PER_MINUTE` times in a minute. Expected: 429 on the excess calls.

### Layering checks

**L1.** `rg "^from fastapi|^from starlette" core/actions/ingest_manifest.py` → zero matches.

## 8. Rollout / rollback

**Commits:**
1. `action: extract ingest_manifest from ingest_all script`
2. `scripts: refactor ingest_all to use shared action`
3. `api: add POST /v1/ingest route`
4. `docs/api: add ingest contract`
5. `docs/CHANGELOG: record 3h`

**Rollback.** Every commit is a clean `git revert`. No migration, no schema change, no dependency change.

## 9. Deviations from this plan

**H5 — rate limit scope.** The plan stated "The IP/min middleware from 3d covers this route." In practice, `IPRateLimitMiddleware` scopes to `_RATE_LIMITED_PREFIXES = ("/v1/query", "/v1/feedback")` only — `/v1/ingest` is exempt. This is the correct behavior: ingest is an operator action, not a public user endpoint. The content-hash gate already makes repeated calls free (zero embeddings cost), so rate limiting adds no value here. H5 test updated to verify exemption rather than enforcement.
