"""Gateway auth boundary helpers."""

from __future__ import annotations

from typing import Any

from fastapi import Depends, Header, Request, status

from .responses import GatewayError, call_upstream, gateway_headers, log_gateway_event
from .upstream import get_upstream_client


async def current_user(
    request: Request,
    authorization: str | None,
    client: Any,
) -> dict[str, Any]:
    if not authorization:
        raise GatewayError(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_TOKEN_MISSING",
            "Bearer token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token:
        raise GatewayError(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_TOKEN_INVALID",
            "Bearer token is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )

    response = await call_upstream(
        request,
        client,
        "GET",
        "auth",
        "/auth/me",
        headers=gateway_headers(request, authorization=authorization),
    )
    if response.status_code == status.HTTP_401_UNAUTHORIZED:
        raise GatewayError(
            status.HTTP_401_UNAUTHORIZED,
            "AUTH_TOKEN_INVALID",
            "Bearer token is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Auth service error",
        )

    log_gateway_event(
        request,
        "gateway.auth.me_resolved",
        user_id=response.body.get("user_id"),
    )
    return response.body


async def protected_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    client: Any = Depends(get_upstream_client),
) -> dict[str, Any]:
    return await current_user(request, authorization, client)
