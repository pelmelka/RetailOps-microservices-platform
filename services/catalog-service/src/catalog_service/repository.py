"""PostgreSQL-backed catalog item lookup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True)
class CatalogItem:
    id: str
    sku: str
    name: str
    description: str
    price_kopecks: int
    currency: str


class CatalogRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def list_active_items(self) -> list[CatalogItem]:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, sku, name, description, price_kopecks, currency
                    FROM catalog_items
                    WHERE is_active = true
                    ORDER BY id
                    """
                )
            )
            rows = result.mappings().all()

        return [self._item_from_row(row) for row in rows]

    async def find_active_item_by_id(self, item_id: str) -> CatalogItem | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, sku, name, description, price_kopecks, currency
                    FROM catalog_items
                    WHERE id = :item_id AND is_active = true
                    """
                ),
                {"item_id": item_id},
            )
            row = result.mappings().first()

        if row is None:
            return None

        return self._item_from_row(row)

    @staticmethod
    def _item_from_row(row: Mapping[str, Any]) -> CatalogItem:
        return CatalogItem(
            id=row["id"],
            sku=row["sku"],
            name=row["name"],
            description=row["description"],
            price_kopecks=row["price_kopecks"],
            currency=row["currency"],
        )
