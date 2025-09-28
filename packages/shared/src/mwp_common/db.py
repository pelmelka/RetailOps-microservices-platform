"""Async SQLAlchemy helpers for PostgreSQL persistence."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import RuntimeConfig, require_database_url


ASYNC_POSTGRESQL_SCHEME = "postgresql+asyncpg://"
PLAIN_POSTGRESQL_SCHEME = "postgresql://"


def normalize_database_url(database_url: str) -> str:
    """Return a SQLAlchemy async PostgreSQL URL for asyncpg."""

    if database_url.startswith(ASYNC_POSTGRESQL_SCHEME):
        return database_url
    if database_url.startswith(PLAIN_POSTGRESQL_SCHEME):
        return database_url.replace(
            PLAIN_POSTGRESQL_SCHEME,
            ASYNC_POSTGRESQL_SCHEME,
            1,
        )
    raise ValueError(
        "DATABASE_URL must use postgresql+asyncpg:// or postgresql:// scheme"
    )


def create_async_database_engine(
    database_url: str,
    **engine_options: object,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine without opening a connection."""

    return create_async_engine(
        normalize_database_url(database_url),
        **engine_options,
    )


def create_async_database_engine_from_config(
    config: RuntimeConfig | None = None,
    **engine_options: object,
) -> AsyncEngine:
    """Create an async SQLAlchemy engine from runtime configuration."""

    return create_async_database_engine(
        require_database_url(config),
        **engine_options,
    )


def create_async_session_factory(
    engine: AsyncEngine,
    **session_options: object,
) -> async_sessionmaker[AsyncSession]:
    """Create an AsyncSession factory for service repositories."""

    return async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        **session_options,
    )
