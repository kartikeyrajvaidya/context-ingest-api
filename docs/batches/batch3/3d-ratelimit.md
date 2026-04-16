# Batch 3d — Rate limiting ✅

> **Status:** ✅ shipped + acceptance pass 2026-04-15.
> **Anchor:** [`../../scaffolding-plan.md`](../../scaffolding-plan.md) §Batches
> **Upstream contracts:** [`../batch2/2b-contracts-and-schemas.md`](../batch2/2b-contracts-and-schemas.md) §"429 responses"
> **Skills consulted:** `context-ingest-api-backend`

## 1. Goal

Stop a single misconfigured client — or an attacker — from draining the operator's OpenAI budget. Three layers, stacked cheapest-first so abuse is rejected as early as possible:

| Layer | Scope | Default | Env var | Store |
|---|---|---|---|---|
| 1. Per-IP / minute | `/v1/query` and `/v1/feedback` | `5` | `RATE_LIMIT_IP_PER_MINUTE` | in-memory |
| 2. Per-session / hour | `/v1/query` only | `15` | `RATE_LIMIT_SESSION_PER_HOUR` | Postgres (`query_requests`) |
| 3. Per-conversation total turns | `/v1/query` only | `10` | `RATE_LIMIT_CONVERSATION_MAX_TURNS` | Postgres (`query_requests`) |

**All three thresholds are environment variables.** Every operator tunes via `.env`; no code changes.

Layer 1 bails in middleware before any route runs. Layers 2 and 3 run at the top of `POST /v1/query` before the action is called — they read the `query_requests` table and raise `HTTPException(429)` if the caller is over budget.

### Known limitation: layer 1 is single-worker only

The IP counter lives in a per-process Python dict. Correct only with `--workers=1` (the default). Under `-w N` the effective ceiling becomes `N × RATE_LIMIT_IP_PER_MINUTE`. Layers 2 and 3 are unaffected because Postgres is the shared store. On startup, if `WEB_CONCURRENCY > 1` is detected, the limiter emits one WARNING log line. Self-hosters needing correct IP limiting under multi-worker should put an upstream limiter in front (nginx `limit_req`, Cloudflare, Traefik), or scale horizontally with more single-worker containers.

## 2. Scope

### In

- `core/rate_limit/__init__.py` — package marker.
- `core/rate_limit/ip_limiter.py` — sliding-window IP limiter + `get_client_ip`. Module-level dict + `threading.Lock` + periodic prune.
- `core/rate_limit/session_limiter.py` — `check_session_rate_limit(session_id)` and `check_conversation_turn_limit(conversation_id)`, both returning `str | None`.
- Rewrite `api/server/middleware.py::IPRateLimitMiddleware.dispatch` to call the real limiter and scope it to `/v1/query` and `/v1/feedback` prefixes.
- Update `api/routes/query.py` to call the session and conversation checks before `query_document(...)` and raise `HTTPException(429, detail=<message>)` on trip.
- Extend `configs/rate_limit.py` with `SESSION_PER_HOUR` and `CONVERSATION_MAX_TURNS`.
- Extend `.env.example` with the two new env vars.
- Add `QueryRequest.count_conversation_turns(conversation_id)` classmethod in `db/models/query_requests.py`.
- `WEB_CONCURRENCY > 1` startup warning in `core/rate_limit/ip_limiter.py`.
- CHANGELOG entry under `[Unreleased]`.

### Out (deferred)

| Item | Where |
|---|---|
| `scripts/reembed_all.py` | Batch 3e |
| Public docs (`docs/guides/self-hosting.md` §Rate limiting, 429 rows in `docs/api/*.md`) | Batch 3f |
| Redis-backed distributed counter | Post-v0 |
| `Retry-After` beyond `60`, rate-limit response headers on 2xx | Post-v0 |
| Per-feedback session/conversation limits | Non-goal (feedback doesn't touch the LLM) |
| Pytest integration tests | Out of scope (manual acceptance like 3a/3b/3c) |

## 3. Rules

1. **Layering.** `core/rate_limit/` has no `fastapi`/`starlette` imports except for the `Request` type used by `get_client_ip`. The middleware owns the HTTP shim for layer 1. The route owns the HTTP shim for layers 2 and 3 — the action stays untouched.
2. **Every threshold is env-driven.** No magic numbers in `core/rate_limit/` or route code. All values flow through `configs/rate_limit.py`.
3. **Check before insert.** Layers 2 and 3 run before `query_document` is called, so the in-flight request doesn't count against its own budget.
4. **Never touch the LLM on a 429.** Layer 1 returns before `call_next`. Layers 2 and 3 raise before the action runs.
5. **Log tripped requests only.** In-budget requests produce no log; every over-budget request emits one WARNING line naming the layer.
6. **No new dependencies.** Stdlib + SQLAlchemy (already in the stack).
7. **Single-worker only for layer 1, loud about it.** Startup WARNING on `WEB_CONCURRENCY > 1`.

## 4. Implementation order

1. Extend `configs/rate_limit.py` and `.env.example`.
2. Add `QueryRequest.count_conversation_turns` classmethod.
3. Write `core/rate_limit/ip_limiter.py` (+ `__init__.py`).
4. Write `core/rate_limit/session_limiter.py`.
5. Rewrite `api/server/middleware.py::IPRateLimitMiddleware.dispatch`.
6. Update `api/routes/query.py` to call the two checks.
7. Update `CHANGELOG.md`.
8. Manual acceptance pass (§7).

## 5. File-by-file

### 5.1 `configs/rate_limit.py`

```python
"""Rate limiting configuration for ContextIngest API."""

import os


class RateLimitConfig:
    IP_PER_MINUTE = int(os.getenv("RATE_LIMIT_IP_PER_MINUTE", "5"))
    SESSION_PER_HOUR = int(os.getenv("RATE_LIMIT_SESSION_PER_HOUR", "15"))
    CONVERSATION_MAX_TURNS = int(
        os.getenv("RATE_LIMIT_CONVERSATION_MAX_TURNS", "10")
    )
```

`int()` with no fallback — a malformed env value raises at boot, which is the correct fail-fast behavior.

### 5.2 `.env.example` (extend)

```bash
# Rate limiting — all three layers are env-tunable.
# Layer 1: per-IP per minute (middleware, in-memory).
RATE_LIMIT_IP_PER_MINUTE=5
# Layer 2: per-session per hour (route, Postgres).
RATE_LIMIT_SESSION_PER_HOUR=15
# Layer 3: per-conversation total turns (route, Postgres).
RATE_LIMIT_CONVERSATION_MAX_TURNS=10
```

### 5.3 `db/models/query_requests.py` — new classmethod

Sibling of the existing `count_session_requests_since`. Uses the `idx_query_requests_conversation_id` index from 2c.

```python
@classmethod
async def count_conversation_turns(cls, conversation_id: str) -> int:
    db_session = await db.get_session()
    stmt = select(func.count(cls.id)).filter(
        cls.conversation_id == conversation_id,
    )
    result = await db_session.execute(stmt)
    return result.scalar_one()
```

### 5.4 `core/rate_limit/ip_limiter.py`

Sliding 60-second window keyed on client IP. Module-level dict protected by a `threading.Lock`. Periodic prune every 5 minutes drops IPs whose most recent request is older than the window.

```python
"""In-memory per-IP rate limiter."""

from __future__ import annotations

import os
import time
from threading import Lock

from fastapi import Request

from configs.rate_limit import RateLimitConfig
from libs.logger import get_logger

logger = get_logger(__name__)

_WINDOW_SECONDS = 60
_PRUNE_INTERVAL_SECONDS = 300

_ip_timestamps: dict[str, list[float]] = {}
_lock = Lock()
_last_prune: float = 0.0


def _warn_if_multi_worker() -> None:
    raw = os.getenv("WEB_CONCURRENCY")
    try:
        workers = int(raw) if raw else 1
    except ValueError:
        return
    if workers > 1:
        logger.warning(
            "IP rate limiter is in-memory per process: WEB_CONCURRENCY=%d "
            "detected. Effective ceiling is %d × RATE_LIMIT_IP_PER_MINUTE. "
            "See docs/guides/self-hosting.md §Rate limiting.",
            workers, workers,
        )


_warn_if_multi_worker()


def get_client_ip(request: Request) -> str:
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip:
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def _prune_expired() -> None:
    global _last_prune
    now = time.monotonic()
    if now - _last_prune < _PRUNE_INTERVAL_SECONDS:
        return
    cutoff = now - _WINDOW_SECONDS
    expired = [
        ip for ip, stamps in _ip_timestamps.items()
        if not stamps or stamps[-1] < cutoff
    ]
    for ip in expired:
        del _ip_timestamps[ip]
    _last_prune = now


def is_ip_rate_limited(request: Request) -> bool:
    ip = get_client_ip(request)
    limit = RateLimitConfig.IP_PER_MINUTE
    now = time.monotonic()
    cutoff = now - _WINDOW_SECONDS

    with _lock:
        _prune_expired()
        timestamps = _ip_timestamps.get(ip)
        if timestamps is None:
            _ip_timestamps[ip] = [now]
            return False
        timestamps[:] = [t for t in timestamps if t > cutoff]
        if len(timestamps) >= limit:
            logger.warning(
                "IP rate limit exceeded ip=%s count=%d",
                ip, len(timestamps),
            )
            return True
        timestamps.append(now)
        return False
```

### 5.5 `core/rate_limit/session_limiter.py`

Two async functions, both returning `str | None` — `None` means in-budget, a string is the user-visible 429 message.

```python
"""Postgres-backed session and conversation rate limiter."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from configs.rate_limit import RateLimitConfig
from db.models.query_requests import QueryRequest
from libs.logger import get_logger

logger = get_logger(__name__)


async def check_session_rate_limit(session_id: str) -> str | None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    count = await QueryRequest.count_session_requests_since(session_id, since)
    if count >= RateLimitConfig.SESSION_PER_HOUR:
        logger.warning(
            "Session rate limit exceeded session_id=%s count=%d limit=%d",
            session_id, count, RateLimitConfig.SESSION_PER_HOUR,
        )
        return (
            f"Rate limit exceeded: maximum {RateLimitConfig.SESSION_PER_HOUR} "
            f"requests per hour per session. Please try again later."
        )
    return None


async def check_conversation_turn_limit(conversation_id: str | None) -> str | None:
    if not conversation_id:
        return None
    count = await QueryRequest.count_conversation_turns(conversation_id)
    if count >= RateLimitConfig.CONVERSATION_MAX_TURNS:
        logger.warning(
            "Conversation turn limit exceeded conversation_id=%s count=%d limit=%d",
            conversation_id, count, RateLimitConfig.CONVERSATION_MAX_TURNS,
        )
        return (
            f"This conversation has reached its limit of "
            f"{RateLimitConfig.CONVERSATION_MAX_TURNS} turns. "
            f"Please start a new conversation."
        )
    return None
```

### 5.6 `api/server/middleware.py` (rewrite)

Scoped to `/v1/query` and `/v1/feedback`. `/health` is intentionally exempt so operator monitoring doesn't trip the limiter.

```python
"""Request middleware for ContextIngest API."""

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from core.rate_limit.ip_limiter import is_ip_rate_limited

_RATE_LIMITED_PREFIXES = ("/v1/query", "/v1/feedback")


class IPRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(path.startswith(p) for p in _RATE_LIMITED_PREFIXES):
            if is_ip_rate_limited(request):
                return JSONResponse(
                    status_code=429,
                    content={"message": "Too many requests. Please try again later."},
                    headers={"Retry-After": "60"},
                )
        return await call_next(request)
```

Registration in `api/server/run_api.py` is unchanged from 2a.

### 5.7 `api/routes/query.py` (update)

Call the two checks before invoking the action. On trip, raise `HTTPException(429, detail=message)`.

```python
from fastapi import APIRouter, HTTPException

from core.actions.query_document import query_document
from core.rate_limit.session_limiter import (
    check_conversation_turn_limit,
    check_session_rate_limit,
)
from core.schema.query import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/v1/query", response_model=QueryResponse)
async def post_query(payload: QueryRequest) -> QueryResponse:
    session_error = await check_session_rate_limit(payload.session_id)
    if session_error:
        raise HTTPException(status_code=429, detail=session_error)

    conversation_error = await check_conversation_turn_limit(payload.conversation_id)
    if conversation_error:
        raise HTTPException(status_code=429, detail=conversation_error)

    return await query_document(payload)
```

`core/actions/query_document.py` is untouched.

## 6. Contract impact

`docs/api/query.md` and `docs/api/feedback.md` already list 429 as a possible response — 3d makes it real. Three distinct bodies depending on which layer tripped:

| Layer | Source | Body |
|---|---|---|
| 1 | middleware | `{"message": "Too many requests. Please try again later."}` + `Retry-After: 60` |
| 2 | route (query only) | `{"detail": "Rate limit exceeded: maximum 15 requests per hour per session. Please try again later."}` |
| 3 | route (query only) | `{"detail": "This conversation has reached its limit of 10 turns. Please start a new conversation."}` |

The `message` vs `detail` key split is an artifact of where the response is built (middleware `JSONResponse` vs FastAPI `HTTPException`). Batch 3f updates the public docs to show all three.

## 7. Acceptance test

Manual pass against the live compose stack (`docker compose up --build -d`; API on `:8050`, Postgres on `:5433`). No pytest.

**Defaults for this run:** `RATE_LIMIT_IP_PER_MINUTE=5`, `RATE_LIMIT_SESSION_PER_HOUR=15`, `RATE_LIMIT_CONVERSATION_MAX_TURNS=10`. For layer 2 and 3 tests, temporarily raise `RATE_LIMIT_IP_PER_MINUTE=1000` so layer 1 doesn't mask the lower layers.

### Layer 1 — IP / minute

**R1. Budget is 5/min on `/v1/query`.** Fire 7 requests; expect 5 × 200 then 2 × 429 with body `{"message":"Too many requests. Please try again later."}` and header `Retry-After: 60`.

**R2. `/health` is exempt.** After exhausting layer 1 with R1, `GET /health` still returns 200.

**R3. Per-IP isolation.** Exhaust under `X-Forwarded-For: 10.0.0.1`; a request under `X-Forwarded-For: 10.0.0.2` is 200.

**R4. Cloudflare header wins.** With both `CF-Connecting-IP: 1.1.1.1` and `X-Forwarded-For: 2.2.2.2`, the counter keys on `1.1.1.1`.

**R5. Env override.** Set `RATE_LIMIT_IP_PER_MINUTE=2`, recreate, repeat R1 — expect 2 × 200 then 429. Restore to 5.

**R6. Multi-worker startup warning.** `docker compose exec -T -e WEB_CONCURRENCY=4 context-ingest-api python -c "import core.rate_limit.ip_limiter"` — expect one WARNING line naming `WEB_CONCURRENCY=4`.

### Layer 2 — session / hour

Precondition: `RATE_LIMIT_SESSION_PER_HOUR=3`, `RATE_LIMIT_IP_PER_MINUTE=1000`, recreate.

**S1. Session budget.** Fire 5 `/v1/query` calls under `session_id=sess_s1`; expect 3 × 200 then 2 × 429 with body `{"detail":"Rate limit exceeded: maximum 3 requests per hour per session. Please try again later."}`.

**S2. Per-session isolation.** After S1, a request under a fresh `session_id=sess_s2` returns 200.

**S3. Log line.** Tail `docker compose logs -f` during S1 — expect one `WARNING - Session rate limit exceeded session_id=sess_s1 count=3 limit=3` per tripped request. Restore to 15.

### Layer 3 — conversation / turns

Precondition: `RATE_LIMIT_CONVERSATION_MAX_TURNS=3`, `RATE_LIMIT_IP_PER_MINUTE=1000`, `RATE_LIMIT_SESSION_PER_HOUR=1000`, recreate.

**C1. Conversation budget.** Turn 1 with no `conversation_id` mints one; capture it. Fire turns 2, 3, 4 with that `conversation_id`. Expect 200, 200, 429 with body `{"detail":"This conversation has reached its limit of 3 turns. Please start a new conversation."}`.

**C2. New conversation is never tripped by layer 3.** A request with no `conversation_id` always passes layer 3 (first-turn short-circuit).

**C3. Log line.** During C1, expect one `WARNING - Conversation turn limit exceeded conversation_id=<id> count=3 limit=3` on the fourth turn. Restore to 10.

### Layering check

**L1.** `rg "^from fastapi|^from starlette" core/rate_limit/` — allowed: one match for `from fastapi import Request` in `ip_limiter.py`. No other matches.

**L2.** `rg "RateLimitConfig" core/actions/` — zero matches. Action layer stays untouched.

## 8. Rollout / rollback

**Commits:**
1. `rate_limit: add ip limiter + session/conversation limiter`
2. `middleware: wire ip limiter for /v1/query and /v1/feedback`
3. `api: session and conversation checks in /v1/query route`
4. `docs/CHANGELOG: record 3d`

**Rollback.** `git revert` per commit. No schema change, no dependency change. Restart with `docker compose up -d --force-recreate --no-deps context-ingest-api`.

## 9. Deviations from this plan

*(Fill in as deviations occur during implementation.)*

None yet — this document is the canonical plan as of 2026-04-15.
