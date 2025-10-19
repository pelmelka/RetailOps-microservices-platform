"""Order read routes and workflow command intake routes."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import JSONResponse

from ..idempotency import (
    IdempotencyStorage,
    get_idempotency_store,
    idempotent_json_response,
)
from ..ownership import ensure_order_status, load_owned_order, transition_order
from ..responses import (
    GatewayError,
    call_upstream,
    gateway_headers,
    log_gateway_event,
    proxy_response,
)
from ..schemas import (
    CreateGatewayNotificationRequest,
    CreateGatewayOrderRequest,
    CreateGatewayPaymentRequest,
)
from ..security import protected_user
from ..upstream import get_upstream_client
from ..workflow_commands import (
    load_workflow_for_order,
    request_order_payment,
    start_order_workflow,
)


router = APIRouter(tags=["gateway-orders"])


@router.post("/api/orders")
async def create_order(
    request_body: CreateGatewayOrderRequest,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client: Any = Depends(get_upstream_client),
    store: IdempotencyStorage = Depends(get_idempotency_store),
) -> JSONResponse:
    async def handler() -> tuple[int, Any]:
        body = await start_order_workflow(
            request,
            client,
            user=user,
            catalog_item_id=request_body.catalog_item_id,
            quantity=request_body.quantity,
            idempotency_key=idempotency_key or "",
        )
        log_gateway_event(
            request,
            "gateway.workflow.accepted",
            user_id=user["user_id"],
            workflow_id=body.get("workflow_id"),
        )
        return status.HTTP_202_ACCEPTED, body

    return await idempotent_json_response(
        request,
        user,
        idempotency_key,
        request_body.model_dump(mode="json"),
        store,
        handler,
    )


@router.get("/api/orders")
async def list_orders(
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    client: Any = Depends(get_upstream_client),
) -> JSONResponse:
    user_id = quote(user["user_id"], safe="")
    response = await call_upstream(
        request,
        client,
        "GET",
        "order",
        f"/orders?user_id={user_id}",
        headers=gateway_headers(request),
    )
    return proxy_response(response)


@router.get("/api/orders/{order_id}")
async def get_order(
    order_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    client: Any = Depends(get_upstream_client),
) -> dict[str, Any]:
    return await load_owned_order(request, client, user, order_id)


@router.get("/api/orders/{order_id}/history")
async def get_order_history(
    order_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    client: Any = Depends(get_upstream_client),
) -> JSONResponse:
    await load_owned_order(request, client, user, order_id)
    response = await call_upstream(
        request,
        client,
        "GET",
        "order",
        f"/orders/{order_id}/history",
        headers=gateway_headers(request),
    )
    return proxy_response(response)


@router.get("/api/orders/{order_id}/workflow")
async def get_order_workflow(
    order_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    client: Any = Depends(get_upstream_client),
) -> dict[str, Any]:
    await load_owned_order(request, client, user, order_id)
    return await load_workflow_for_order(
        request,
        client,
        order_id=order_id,
        user_id=user["user_id"],
    )


@router.post("/api/orders/{order_id}/payments")
async def create_payment(
    order_id: str,
    request_body: CreateGatewayPaymentRequest,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client: Any = Depends(get_upstream_client),
    store: IdempotencyStorage = Depends(get_idempotency_store),
) -> JSONResponse:
    async def handler() -> tuple[int, Any]:
        await load_owned_order(request, client, user, order_id)
        body = await request_order_payment(
            request,
            client,
            user=user,
            order_id=order_id,
            payment_scenario=request_body.payment_scenario,
            idempotency_key=idempotency_key or "",
        )
        log_gateway_event(
            request,
            "gateway.payment.requested",
            user_id=user["user_id"],
            order_id=order_id,
            workflow_id=body.get("workflow_id"),
        )
        return status.HTTP_202_ACCEPTED, body

    return await idempotent_json_response(
        request,
        user,
        idempotency_key,
        request_body.model_dump(mode="json"),
        store,
        handler,
    )


@router.post("/api/orders/{order_id}/notifications", tags=["gateway-legacy"])
async def create_notification(
    order_id: str,
    request_body: CreateGatewayNotificationRequest,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client: Any = Depends(get_upstream_client),
    store: IdempotencyStorage = Depends(get_idempotency_store),
) -> JSONResponse:
    async def handler() -> tuple[int, Any]:
        order = await load_owned_order(request, client, user, order_id)
        order_status = order.get("status")
        if order_status == "receipt_generated":
            template_key = request_body.template_key or "workflow_completed"
            allowed_templates = {"workflow_completed"}
        elif order_status == "payment_failed":
            template_key = request_body.template_key or "payment_failed"
            allowed_templates = {"payment_failed"}
        else:
            template_key = request_body.template_key or "workflow_completed"
            allowed_templates = set()

        if template_key not in allowed_templates:
            ensure_order_status(
                request,
                order,
                {"receipt_generated", "payment_failed"},
                "Notification is not allowed for the current order state",
            )
            raise GatewayError(
                status.HTTP_409_CONFLICT,
                "WORKFLOW_STEP_CONFLICT",
                "Notification template is not allowed for the current order state",
            )

        notification_response = await call_upstream(
            request,
            client,
            "POST",
            "notification",
            "/notifications",
            json={
                "order_id": order_id,
                "channel": request_body.channel,
                "recipient": user["email"],
                "template_key": template_key,
            },
            headers=gateway_headers(request),
        )
        if notification_response.status_code != status.HTTP_201_CREATED:
            raise GatewayError(
                status.HTTP_502_BAD_GATEWAY,
                "UPSTREAM_SERVICE_ERROR",
                "Notification service error",
            )

        if (
            order_status == "receipt_generated"
            and template_key == "workflow_completed"
            and notification_response.body.get("status") == "sent"
        ):
            await transition_order(
                request,
                client,
                order_id,
                next_status="notification_sent",
                reason="Legacy/manual workflow notification sent",
            )

        log_gateway_event(
            request,
            "gateway.legacy.notification.sent",
            user_id=user["user_id"],
            order_id=order_id,
            notification_id=notification_response.body.get("id"),
            status=notification_response.body.get("status"),
        )
        return status.HTTP_201_CREATED, notification_response.body

    return await idempotent_json_response(
        request,
        user,
        idempotency_key,
        request_body.model_dump(mode="json"),
        store,
        handler,
    )
