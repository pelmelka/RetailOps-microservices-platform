import importlib

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mwp_common.config import RuntimeConfig
from mwp_common.db import (
    create_async_database_engine,
    create_async_database_engine_from_config,
    create_async_session_factory,
    normalize_database_url,
)


def test_async_postgresql_url_is_preserved() -> None:
    database_url = "postgresql+asyncpg://mwp:secret@postgres:5432/mwp"

    assert normalize_database_url(database_url) == database_url


def test_plain_postgresql_url_is_normalized_to_asyncpg() -> None:
    assert (
        normalize_database_url("postgresql://mwp:secret@postgres:5432/mwp")
        == "postgresql+asyncpg://mwp:secret@postgres:5432/mwp"
    )


def test_importing_mwp_common_does_not_create_database_connection() -> None:
    module = importlib.import_module("mwp_common")

    assert module is not None


def test_async_engine_creation_does_not_connect_to_database() -> None:
    engine = create_async_database_engine(
        "postgresql+asyncpg://mwp:secret@postgres.invalid:5432/mwp"
    )

    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        engine.sync_engine.dispose()


def test_async_engine_creation_from_config_normalizes_url() -> None:
    engine = create_async_database_engine_from_config(
        RuntimeConfig(database_url="postgresql://mwp:secret@postgres.invalid:5432/mwp")
    )

    try:
        assert isinstance(engine, AsyncEngine)
        assert engine.url.drivername == "postgresql+asyncpg"
    finally:
        engine.sync_engine.dispose()


def test_async_session_factory_creation_does_not_connect_to_database() -> None:
    engine = create_async_database_engine(
        "postgresql+asyncpg://mwp:secret@postgres.invalid:5432/mwp"
    )

    try:
        session_factory = create_async_session_factory(engine)

        assert isinstance(session_factory, async_sessionmaker)
        assert session_factory.class_ is AsyncSession
    finally:
        engine.sync_engine.dispose()
