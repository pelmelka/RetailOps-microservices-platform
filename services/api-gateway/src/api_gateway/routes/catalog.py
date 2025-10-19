"""Catalog routes proxied through api-gateway."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from ..responses import call_upstream, gateway_headers, proxy_response
from ..upstream import get_upstream_client


router = APIRouter(tags=["gateway-catalog"])


@router.get("/api/catalog/items")
async def list_catalog_items(
    request: Request,
    client: Any = Depends(get_upstream_client),
) -> JSONResponse:
    response = await call_upstream(
        request,
        client,
        "GET",
        "catalog",
        "/catalog/items",
        headers=gateway_headers(request),
    )
    return proxy_response(response)


@router.get("/api/catalog/items/{item_id}")
async def get_catalog_item(
    item_id: str,
    request: Request,
    client: Any = Depends(get_upstream_client),
) -> JSONResponse:
    response = await call_upstream(
        request,
        client,
        "GET",
        "catalog",
        f"/catalog/items/{item_id}",
        headers=gateway_headers(request),
    )
    return proxy_response(response)
