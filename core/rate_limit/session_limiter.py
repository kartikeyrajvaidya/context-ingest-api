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
