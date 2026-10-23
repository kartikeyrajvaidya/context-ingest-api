"""Async transaction helpers used by actions and route handlers."""

import traceback
from contextlib import asynccontextmanager

from db import db
from libs.logger import get_logger

logger = get_logger(__name__)


async def release_session() -> None:
    """Close the current task's scoped session and drop it from the registry.

    Ends any open transaction (uncommitted reads roll back) and returns the
    connection. Safe to call when no session exists. Call it before slow
    network work so no transaction is held across it.
    """
    if db.session is not None:
        await db.session.remove()


async def release_session_dependency():
    """FastAPI dependency that releases the scoped session on every exit path.

    Registered app-wide, so early returns and raised HTTP errors (429, 404)
    never leave a read transaction or connection open.
    """
    try:
        yield
    finally:
        await release_session()


@asynccontextmanager
async def commit_transaction_async():
    """Context manager form for actions that orchestrate work outside a request."""
    session = await db.get_session()
    try:
        yield session
    except Exception as exc:
        logger.error(exc)
        logger.error(traceback.format_exc())
        await session.rollback()
        raise
    finally:
        await session.commit()
        await session.close()
