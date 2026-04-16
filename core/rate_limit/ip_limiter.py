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
            "detected. Effective ceiling is %d x RATE_LIMIT_IP_PER_MINUTE. "
            "See docs/guides/self-hosting.md Rate limiting.",
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
