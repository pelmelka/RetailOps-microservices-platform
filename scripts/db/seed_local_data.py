from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy import text

from mwp_common import (
    create_async_database_engine_from_config,
    create_async_session_factory,
)


TEST_USER = {
    "id": "user-local-001",
    "username": "local-user",
    "email": "local-user@example.test",
    "display_name": "Local Workflow User",
    # Hash for local development password: local-password.
    # This is deterministic seed data, not a production credential.
    "password_hash": (
        "$argon2id$v=19$m=65536,t=3,p=4$/mT+uwydb4yZrut/OL2C4Q"
        "$nr2BDN6gP6wecqJCGKcHSmBWjVEs3LFpZItDIdOtdpo"
    ),
}

CATALOG_ITEMS = [
    {
        "id": "catalog-item-basic",
        "sku": "MWP-BASIC",
        "name": "Basic Workflow Package",
        "description": "Deterministic catalog item for the critical workflow.",
        "price_kopecks": 199000,
        "currency": "RUB",
    },
    {
        "id": "catalog-item-pro",
        "sku": "MWP-PRO",
        "name": "Pro Workflow Package",
        "description": "Second deterministic catalog item for local validation.",
        "price_kopecks": 499000,
        "currency": "RUB",
    },
]


async def seed() -> None:
    engine = create_async_database_engine_from_config()
    session_factory = create_async_session_factory(engine)
    now = datetime.now(UTC)

    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO auth_users (
                        id, username, email, display_name, password_hash, is_active,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :username, :email, :display_name, :password_hash, true,
                        :created_at, :updated_at
                    )
                    ON CONFLICT (id) DO UPDATE SET
                        username = EXCLUDED.username,
                        email = EXCLUDED.email,
                        display_name = EXCLUDED.display_name,
                        password_hash = EXCLUDED.password_hash,
                        is_active = EXCLUDED.is_active,
                        updated_at = EXCLUDED.updated_at
                    """
                ),
                {
                    **TEST_USER,
                    "created_at": now,
                    "updated_at": now,
                },
            )

            for item in CATALOG_ITEMS:
                await session.execute(
                    text(
                        """
                        INSERT INTO catalog_items (
                            id, sku, name, description, price_kopecks, currency,
                            is_active, created_at, updated_at
                        )
                        VALUES (
                            :id, :sku, :name, :description, :price_kopecks, :currency,
                            true, :created_at, :updated_at
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            sku = EXCLUDED.sku,
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            price_kopecks = EXCLUDED.price_kopecks,
                            currency = EXCLUDED.currency,
                            is_active = EXCLUDED.is_active,
                            updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {
                        **item,
                        "created_at": now,
                        "updated_at": now,
                    },
                )

            await session.commit()
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
