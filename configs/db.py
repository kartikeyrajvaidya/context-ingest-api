"""Database configuration for ContextIngest API."""

import os


class DBConfig:
    """Postgres connection and engine knobs."""

    DB_CONNECTION_URI = os.environ.get(
        "DB_CONNECTION_URI",
        "postgresql://postgres:password@localhost:5432/context_ingest",
    )
    DB_CONNECTION_URI_ASYNCPG = os.environ.get(
        "DB_CONNECTION_URI_ASYNCPG",
        "postgresql+asyncpg://postgres:password@localhost:5432/context_ingest",
    )
    SCHEMA_NAME = os.environ.get("SCHEMA_NAME", "public")
    DB_STATEMENT_TIMEOUT = os.environ.get("DB_STATEMENT_TIMEOUT", "5000")
    DB_APPLICATION_NAME = os.environ.get("DB_APPLICATION_NAME", "context-ingest-api")
    DB_ECHO = os.environ.get("SQLALCHEMY_ECHO", "F") == "T"
    DB_ECHO_POOL = os.environ.get("SQLALCHEMY_ECHO_POOL", "F") == "T"
