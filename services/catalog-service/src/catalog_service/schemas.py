"""Response schemas for catalog-service endpoints."""

from typing import Literal

from pydantic import BaseModel


class CatalogItemResponse(BaseModel):
    id: str
    sku: str
    name: str
    description: str
    price_kopecks: int
    currency: Literal["RUB"]


class CatalogItemsResponse(BaseModel):
    items: list[CatalogItemResponse]
