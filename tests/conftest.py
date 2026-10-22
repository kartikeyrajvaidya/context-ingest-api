"""Shared pytest fixtures.

Config classes read the environment at import time, so test defaults are set
here before any application module is imported. The safety gate and IP rate
limit are always off so tests never call OpenAI or trip the limiter. The
database URI comes from the shell when set (CI points it at a service
container).
"""

import os

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-used")
os.environ["SAFETY_ENABLED"] = "false"
os.environ["RATE_LIMIT_IP_PER_MINUTE"] = "1000"

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from api.server.run_api import app
from core.rate_limit import ip_limiter
from db import db


@pytest.fixture(autouse=True)
def _reset_ip_rate_limiter():
    ip_limiter._ip_timestamps.clear()
    yield
    ip_limiter._ip_timestamps.clear()


@pytest.fixture
def client():
    """App client without the lifespan, so no database connection is opened."""
    return TestClient(app)


def _database_reachable() -> bool:
    async def _probe() -> None:
        session = await db.get_session()
        try:
            await session.execute(text("SELECT 1"))
        finally:
            await session.close()
            await db.disconnect()

    try:
        asyncio.run(_probe())
    except Exception:
        return False
    return True


@pytest.fixture(scope="session")
def database():
    """Skip DB tests locally when Postgres is down; fail in CI (REQUIRE_DB=1)."""
    if not _database_reachable():
        if os.environ.get("REQUIRE_DB") == "1":
            pytest.fail("REQUIRE_DB=1 but the database is not reachable")
        pytest.skip("Postgres not reachable; run `docker compose up postgres -d`")
