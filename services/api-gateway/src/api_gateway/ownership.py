"""Ownership and state checks for protected gateway resources."""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import Request, status

from .responses import GatewayError, call_upstream, gateway_headers, log_gateway_event


async def load_owned_order(
    request: Request,
    client: Any,
    user: Mapping[str, Any],
    order_id: str,
) -> dict[str, Any]:
    response = await call_upstream(
        request,
        client,
        "GET",
        "order",
        f"/orders/{order_id}",
        headers=gateway_headers(request),
    )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "ORDER_NOT_FOUND",
            "Order not found",
        )
    if response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Order service error",
        )
    if response.body.get("user_id") != user.get("user_id"):
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "ORDER_OWNERSHIP_NOT_FOUND",
            "Order not found",
        )
    return response.body


def ensure_order_status(
    request: Request,
    order: Mapping[str, Any],
    allowed_statuses: set[str],
    message: str,
) -> None:
    if order.get("status") not in allowed_statuses:
        log_gateway_event(
            request,
            "gateway.step.conflict",
            order_id=order.get("id"),
            status=order.get("status"),
        )
        raise GatewayError(
            status.HTTP_409_CONFLICT,
            "WORKFLOW_STEP_CONFLICT",
            message,
        )


async def transition_order(
    request: Request,
    client: Any,
    order_id: str,
    *,
    next_status: str,
    reason: str,
) -> dict[str, Any]:
    response = await call_upstream(
        request,
        client,
        "POST",
        "order",
        f"/orders/{order_id}/transitions",
        json={"status": next_status, "reason": reason},
        headers=gateway_headers(request),
    )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "ORDER_NOT_FOUND",
            "Order not found",
        )
    if response.status_code == status.HTTP_409_CONFLICT:
        raise GatewayError(
            status.HTTP_409_CONFLICT,
            "ORDER_TRANSITION_CONFLICT",
            "Order transition conflict",
        )
    if response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Order service error",
        )
    return response.body
