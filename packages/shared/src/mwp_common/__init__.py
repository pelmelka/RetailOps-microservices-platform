"""Shared FastAPI foundation for backend services."""

from .app import create_app
from .correlation import (
    CORRELATION_ID_HEADER,
    ECHOGATE_RUN_ID_HEADER,
    ECHOGATE_SCENARIO_ID_HEADER,
)
from .config import (
    DATABASE_URL_ENV,
    REDIS_URL_ENV,
    MissingDatabaseUrlError,
    RuntimeConfig,
    get_runtime_config,
    require_database_url,
)
from .db import (
    create_async_database_engine,
    create_async_database_engine_from_config,
    create_async_session_factory,
    normalize_database_url,
)
from .redis_streams import RedisStreamsClient, RedisStreamError, StreamMessage

__all__ = [
    "CORRELATION_ID_HEADER",
    "DATABASE_URL_ENV",
    "ECHOGATE_RUN_ID_HEADER",
    "ECHOGATE_SCENARIO_ID_HEADER",
    "MissingDatabaseUrlError",
    "REDIS_URL_ENV",
    "RuntimeConfig",
    "RedisStreamError",
    "RedisStreamsClient",
    "create_app",
    "create_async_database_engine",
    "create_async_database_engine_from_config",
    "create_async_session_factory",
    "get_runtime_config",
    "normalize_database_url",
    "require_database_url",
    "StreamMessage",
]
