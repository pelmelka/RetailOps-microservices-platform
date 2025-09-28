import pytest

from mwp_common.config import (
    MissingDatabaseUrlError,
    RuntimeConfig,
    get_runtime_config,
    require_database_url,
)


def test_database_url_is_read_from_environment_mapping() -> None:
    config = get_runtime_config(
        {
            "DATABASE_URL": "postgresql+asyncpg://mwp:secret@postgres:5432/mwp",
            "REDIS_URL": "redis://redis:6379/0",
        }
    )

    assert config.database_url == "postgresql+asyncpg://mwp:secret@postgres:5432/mwp"
    assert config.redis_url == "redis://redis:6379/0"


def test_missing_database_url_is_explicit() -> None:
    with pytest.raises(MissingDatabaseUrlError, match="DATABASE_URL is required"):
        require_database_url(RuntimeConfig())
