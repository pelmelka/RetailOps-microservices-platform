"""Catalog service application entrypoint."""

from typing import Protocol

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)

from .repository import CatalogItem
from .repository import CatalogRepository
from .schemas import CatalogItemResponse, CatalogItemsResponse

app = create_app("catalog-service")


class CatalogStorage(Protocol):
    async def list_active_items(self) -> list[CatalogItem]:
        """Return active catalog items."""

    async def find_active_item_by_id(self, item_id: str) -> CatalogItem | None:
        """Return one active catalog item by stable id."""


def get_catalog_repository() -> CatalogStorage:
    engine = getattr(app.state, "catalog_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.catalog_database_engine = engine
        app.state.catalog_session_factory = create_async_session_factory(engine)

    return CatalogRepository(app.state.catalog_session_factory)


def item_response(item: CatalogItem) -> CatalogItemResponse:
    return CatalogItemResponse(
        id=item.id,
        sku=item.sku,
        name=item.name,
        description=item.description,
        price_kopecks=item.price_kopecks,
        currency=item.currency,
    )


@app.get("/catalog/items", response_model=CatalogItemsResponse, tags=["catalog"])
async def list_catalog_items(
    repository: CatalogStorage = Depends(get_catalog_repository),
) -> CatalogItemsResponse:
    items = await repository.list_active_items()
    return CatalogItemsResponse(items=[item_response(item) for item in items])


@app.get(
    "/catalog/items/{item_id}",
    response_model=CatalogItemResponse,
    tags=["catalog"],
)
async def get_catalog_item(
    item_id: str,
    repository: CatalogStorage = Depends(get_catalog_repository),
) -> CatalogItemResponse:
    item = await repository.find_active_item_by_id(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Catalog item not found",
        )

    return item_response(item)


async def dispose_catalog_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "catalog_database_engine", None)
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_catalog_database_engine)
