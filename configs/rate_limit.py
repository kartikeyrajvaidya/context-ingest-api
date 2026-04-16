"""Rate limiting configuration for ContextIngest API."""

import os


class RateLimitConfig:
    IP_PER_MINUTE = int(os.getenv("RATE_LIMIT_IP_PER_MINUTE", "5"))
    SESSION_PER_HOUR = int(os.getenv("RATE_LIMIT_SESSION_PER_HOUR", "15"))
    CONVERSATION_MAX_TURNS = int(
        os.getenv("RATE_LIMIT_CONVERSATION_MAX_TURNS", "10")
    )
