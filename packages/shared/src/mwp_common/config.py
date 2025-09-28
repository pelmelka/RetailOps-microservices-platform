"""Runtime configuration helpers for backend services."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


DATABASE_URL_ENV = "DATABASE_URL"
REDIS_URL_ENV = "REDIS_URL"


@dataclass(frozen=True)
class RuntimeConfig:
    """Configuration values shared by backend services."""

    database_url: str | None = None
    redis_url: str | None = None


class MissingDatabaseUrlError(RuntimeError):
    """Raised when code requires DATABASE_URL but it is not configured."""


def get_runtime_config(env: Mapping[str, str] | None = None) -> RuntimeConfig:
    """Read runtime configuration from environment-like mapping."""

    source = environ if env is None else env
    return RuntimeConfig(
        database_url=source.get(DATABASE_URL_ENV),
        redis_url=source.get(REDIS_URL_ENV),
    )


def require_database_url(config: RuntimeConfig | None = None) -> str:
    """Return DATABASE_URL or raise an explicit configuration error."""

    runtime_config = get_runtime_config() if config is None else config
    if not runtime_config.database_url:
        raise MissingDatabaseUrlError("DATABASE_URL is required")
    return runtime_config.database_url
