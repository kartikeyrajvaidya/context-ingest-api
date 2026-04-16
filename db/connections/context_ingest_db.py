"""Async + sync SQLAlchemy engines for ContextIngest API.

The class exposes one process-wide async engine plus an `async_scoped_session`
keyed on `current_task`, so each request handler gets its own session even
when many run concurrently. A lazy sync engine is kept around for Alembic.
"""

from asyncio import current_task

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import async_scoped_session
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from configs.db import DBConfig


class ContextIngestDB:
    engine = None
    session = None
    async_session_factory = None

    @classmethod
    def __get_sync_engine_opts(cls):
        return {
            "connect_args": {
                "options": "-c statement_timeout={0}".format(DBConfig.DB_STATEMENT_TIMEOUT),
                "application_name": DBConfig.DB_APPLICATION_NAME,
            },
            "echo": DBConfig.DB_ECHO,
            "echo_pool": DBConfig.DB_ECHO_POOL,
            "pool_size": 10,
            "max_overflow": 10,
            "pool_recycle": 300,
            "pool_pre_ping": True,
            "pool_use_lifo": True,
        }

    @classmethod
    def __get_async_engine_opts(cls):
        return {
            "connect_args": {
                "statement_cache_size": 0,
                "command_timeout": int(DBConfig.DB_STATEMENT_TIMEOUT) / 1000,
                "server_settings": {
                    "application_name": DBConfig.DB_APPLICATION_NAME,
                    "statement_timeout": str(DBConfig.DB_STATEMENT_TIMEOUT),
                },
            },
            "poolclass": NullPool,
            "echo": DBConfig.DB_ECHO,
            "echo_pool": DBConfig.DB_ECHO_POOL,
            "execution_options": {"compiled_cache": None},
        }

    @classmethod
    def get_sync_engine(cls):
        return create_engine(DBConfig.DB_CONNECTION_URI, **cls.__get_sync_engine_opts())

    @classmethod
    async def connect(cls):
        if cls.engine:
            return

        cls.engine = create_async_engine(
            DBConfig.DB_CONNECTION_URI_ASYNCPG,
            **cls.__get_async_engine_opts(),
        )

        cls.async_session_factory = async_sessionmaker(
            cls.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )

        cls.session = async_scoped_session(
            cls.async_session_factory,
            scopefunc=current_task,
        )

    @classmethod
    async def get_session(cls) -> AsyncSession:
        if not cls.session:
            await cls.connect()
        return cls.session()

    @classmethod
    async def disconnect(cls):
        if cls.engine:
            await cls.engine.dispose()
            cls.engine = None
            cls.session = None
            cls.async_session_factory = None
