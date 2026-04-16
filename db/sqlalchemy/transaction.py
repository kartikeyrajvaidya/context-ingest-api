"""Async transaction helpers used by actions and route handlers."""

import traceback
from contextlib import asynccontextmanager

from db import db
from libs.logger import get_logger

logger = get_logger(__name__)


async def commit_transaction_async_dependency():
    """FastAPI dependency that yields a session and commits on exit."""
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
