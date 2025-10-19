"""Auth routes proxied through api-gateway."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from ..responses import call_upstream, gateway_headers, proxy_response
from ..security import protected_user
from ..upstream import get_upstream_client


router = APIRouter(tags=["gateway-auth"])


@router.post("/api/auth/register")
async def register(
    request: Request,
    body: dict[str, Any] = Body(...),
    client: Any = Depends(get_upstream_client),
) -> JSONResponse:
    response = await call_upstream(
        request,
        client,
        "POST",
        "auth",
        "/auth/register",
        json=body,
        headers=gateway_headers(request),
    )
    return proxy_response(response)


@router.post("/api/auth/login")
async def login(
    request: Request,
    body: dict[str, Any] = Body(...),
    client: Any = Depends(get_upstream_client),
) -> JSONResponse:
    response = await call_upstream(
        request,
        client,
        "POST",
        "auth",
        "/auth/login",
        json=body,
        headers=gateway_headers(request),
    )
    return proxy_response(response)


@router.get("/api/auth/me")
async def me(user: dict[str, Any] = Depends(protected_user)) -> dict[str, Any]:
    return user
