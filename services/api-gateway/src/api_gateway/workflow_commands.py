"""Client helpers for workflow-service command intake."""

from __future__ import annotations

from typing import Any, Mapping
from urllib.parse import quote

from fastapi import Request, status

from .responses import GatewayError, call_upstream, gateway_headers


async def start_order_workflow(
    request: Request,
    client: Any,
    *,
    user: Mapping[str, Any],
    catalog_item_id: str,
    quantity: int,
    idempotency_key: str,
) -> dict[str, Any]:
    response = await call_upstream(
        request,
        client,
        "POST",
        "workflow",
        "/workflows/order-checkout",
        json={
            "user_id": user["user_id"],
            "user_email": user["email"],
            "catalog_item_id": catalog_item_id,
            "quantity": quantity,
            "idempotency_key": idempotency_key,
            "correlation_id": request.headers.get("X-Correlation-ID")
            or getattr(request.state, "correlation_id", None),
        },
        headers=gateway_headers(request),
    )
    if response.status_code != status.HTTP_202_ACCEPTED:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Workflow service error",
        )
    return response.body


async def request_order_payment(
    request: Request,
    client: Any,
    *,
    user: Mapping[str, Any],
    order_id: str,
    payment_scenario: str,
    idempotency_key: str,
) -> dict[str, Any]:
    response = await call_upstream(
        request,
        client,
        "POST",
        "workflow",
        f"/workflows/orders/{order_id}/payments",
        json={
            "user_id": user["user_id"],
            "payment_scenario": payment_scenario,
            "idempotency_key": idempotency_key,
            "correlation_id": request.headers.get("X-Correlation-ID")
            or getattr(request.state, "correlation_id", None),
        },
        headers=gateway_headers(request),
    )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "WORKFLOW_NOT_FOUND",
            "Workflow not found",
        )
    if response.status_code == status.HTTP_409_CONFLICT:
        raise GatewayError(
            status.HTTP_409_CONFLICT,
            "WORKFLOW_STEP_CONFLICT",
            "Workflow is not awaiting payment",
        )
    if response.status_code != status.HTTP_202_ACCEPTED:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Workflow service error",
        )
    return response.body


async def load_workflow(
    request: Request,
    client: Any,
    workflow_id: str,
) -> dict[str, Any]:
    response = await call_upstream(
        request,
        client,
        "GET",
        "workflow",
        f"/workflows/{workflow_id}",
        headers=gateway_headers(request),
    )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "WORKFLOW_NOT_FOUND",
            "Workflow not found",
        )
    if response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Workflow service error",
        )
    return response.body


async def load_workflow_for_order(
    request: Request,
    client: Any,
    *,
    order_id: str,
    user_id: str,
) -> dict[str, Any]:
    encoded_user_id = quote(user_id, safe="")
    response = await call_upstream(
        request,
        client,
        "GET",
        "workflow",
        f"/workflows/orders/{order_id}?user_id={encoded_user_id}",
        headers=gateway_headers(request),
    )
    if response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "WORKFLOW_NOT_FOUND",
            "Workflow not found",
        )
    if response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Workflow service error",
        )
    return response.body
