"""Common runtime configuration for ContextIngest API."""

import os


class CommonConfig:
    """Process-wide settings that are not specific to a subsystem."""

    APP_NAME = os.getenv("APP_NAME", "ContextIngest API")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "dev")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ALLOWED_ORIGINS",
            "http://localhost:8000,http://127.0.0.1:8000",
        ).split(",")
        if origin.strip()
    ]

    @classmethod
    def is_development_environment(cls) -> bool:
        return cls.ENVIRONMENT == "dev"
