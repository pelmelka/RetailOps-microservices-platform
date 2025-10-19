"""Document download routes and legacy/manual document mutations."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, Request, Response, status
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
    download_response,
    download_upstream,
    gateway_headers,
    log_gateway_event,
)
from ..security import protected_user
from ..upstream import get_upstream_client


router = APIRouter(tags=["gateway-documents"])


@router.post("/api/orders/{order_id}/documents/invoice", tags=["gateway-legacy"])
async def create_invoice(
    order_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client: Any = Depends(get_upstream_client),
    store: IdempotencyStorage = Depends(get_idempotency_store),
) -> JSONResponse:
    async def handler() -> tuple[int, Any]:
        order = await load_owned_order(request, client, user, order_id)
        ensure_order_status(
            request,
            order,
            {"created"},
            "Invoice can be generated only for a created order",
        )
        document_response = await call_upstream(
            request,
            client,
            "POST",
            "document",
            "/documents/invoice",
            json={"order_id": order_id},
            headers=gateway_headers(request),
        )
        if document_response.status_code != status.HTTP_201_CREATED:
            raise GatewayError(
                status.HTTP_502_BAD_GATEWAY,
                "UPSTREAM_SERVICE_ERROR",
                "Document service error",
            )
        await transition_order(
            request,
            client,
            order_id,
            next_status="invoice_generated",
            reason="Legacy/manual invoice PDF generated",
        )
        log_gateway_event(
            request,
            "gateway.legacy.invoice.generated",
            user_id=user["user_id"],
            order_id=order_id,
            document_id=document_response.body.get("id"),
        )
        return status.HTTP_201_CREATED, document_response.body

    return await idempotent_json_response(
        request,
        user,
        idempotency_key,
        {},
        store,
        handler,
    )


@router.post("/api/orders/{order_id}/documents/receipt", tags=["gateway-legacy"])
async def create_receipt(
    order_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    client: Any = Depends(get_upstream_client),
    store: IdempotencyStorage = Depends(get_idempotency_store),
) -> JSONResponse:
    async def handler() -> tuple[int, Any]:
        order = await load_owned_order(request, client, user, order_id)
        ensure_order_status(
            request,
            order,
            {"payment_completed"},
            "Receipt can be generated only after completed payment",
        )
        document_response = await call_upstream(
            request,
            client,
            "POST",
            "document",
            "/documents/receipt",
            json={"order_id": order_id},
            headers=gateway_headers(request),
        )
        if document_response.status_code != status.HTTP_201_CREATED:
            raise GatewayError(
                status.HTTP_502_BAD_GATEWAY,
                "UPSTREAM_SERVICE_ERROR",
                "Document service error",
            )
        await transition_order(
            request,
            client,
            order_id,
            next_status="receipt_generated",
            reason="Legacy/manual receipt PDF generated",
        )
        log_gateway_event(
            request,
            "gateway.legacy.receipt.generated",
            user_id=user["user_id"],
            order_id=order_id,
            document_id=document_response.body.get("id"),
        )
        return status.HTTP_201_CREATED, document_response.body

    return await idempotent_json_response(
        request,
        user,
        idempotency_key,
        {},
        store,
        handler,
    )


@router.get("/api/orders/{order_id}/documents/{document_id}/download")
async def download_document(
    order_id: str,
    document_id: str,
    request: Request,
    user: dict[str, Any] = Depends(protected_user),
    client: Any = Depends(get_upstream_client),
) -> Response:
    await load_owned_order(request, client, user, order_id)
    metadata_response = await call_upstream(
        request,
        client,
        "GET",
        "document",
        f"/documents/{document_id}",
        headers=gateway_headers(request),
    )
    if metadata_response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            "Document not found",
        )
    if metadata_response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Document service error",
        )
    if metadata_response.body.get("order_id") != order_id:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            "Document not found",
        )

    file_response = await download_upstream(
        request,
        client,
        "document",
        f"/documents/{document_id}/download",
        headers=gateway_headers(request),
    )
    if file_response.status_code == status.HTTP_404_NOT_FOUND:
        raise GatewayError(
            status.HTTP_404_NOT_FOUND,
            "DOCUMENT_NOT_FOUND",
            "Document not found",
        )
    if file_response.status_code != status.HTTP_200_OK:
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Document service error",
        )
    return download_response(file_response)
