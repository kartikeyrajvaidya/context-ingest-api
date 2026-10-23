"""Rate limiting configuration for ContextIngest API."""

import os


def _bool(raw: str, default: bool) -> bool:
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class RateLimitConfig:
    IP_PER_MINUTE = int(os.getenv("RATE_LIMIT_IP_PER_MINUTE", "5"))
    SESSION_PER_HOUR = int(os.getenv("RATE_LIMIT_SESSION_PER_HOUR", "15"))
    CONVERSATION_MAX_TURNS = int(os.getenv("RATE_LIMIT_CONVERSATION_MAX_TURNS", "10"))
    # Off: the per-IP key is the socket peer address. On: read CF-Connecting-IP
    # or X-Forwarded-For. Turn on only when every request arrives through a
    # proxy that sets those headers; otherwise clients can spoof them.
    TRUST_FORWARDED_HEADERS = _bool(os.getenv("TRUST_FORWARDED_HEADERS", ""), False)
