"""Gateway response and upstream error helpers."""

from __future__ import annotations

from typing import Any, Mapping

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from mwp_common import (
    CORRELATION_ID_HEADER,
    ECHOGATE_RUN_ID_HEADER,
    ECHOGATE_SCENARIO_ID_HEADER,
)
from mwp_common.correlation import request_context

from .upstream import UpstreamResponse, UpstreamServiceError, UpstreamTimeoutError


class GatewayError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}


def gateway_error_payload(request: Request, code: str, message: str) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "correlation_id": getattr(request.state, "correlation_id", None),
        }
    }


async def handle_gateway_error(request: Request, exc: GatewayError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=gateway_error_payload(request, exc.code, exc.message),
        headers=dict(exc.headers),
    )


def gateway_headers(
    request: Request,
    *,
    authorization: str | None = None,
) -> dict[str, str]:
    headers: dict[str, str] = {}
    for header_name in (
        CORRELATION_ID_HEADER,
        ECHOGATE_RUN_ID_HEADER,
        ECHOGATE_SCENARIO_ID_HEADER,
    ):
        value = request.headers.get(header_name)
        if value:
            headers[header_name] = value
    if authorization:
        headers["Authorization"] = authorization
    return headers


def proxy_response(upstream_response: UpstreamResponse) -> JSONResponse:
    return JSONResponse(
        status_code=upstream_response.status_code,
        content=upstream_response.body,
    )


def log_gateway_event(request: Request, event: str, **fields: Any) -> None:
    context = request_context(request)
    context.update({key: value for key, value in fields.items() if value is not None})
    request.app.state.logger.info(event, extra=context)


async def call_upstream(
    request: Request,
    client: Any,
    method: str,
    service: str,
    path: str,
    *,
    json: Any | None = None,
    headers: Mapping[str, str] | None = None,
) -> UpstreamResponse:
    try:
        return await client.request(
            method,
            service,
            path,
            json=json,
            headers=headers,
        )
    except UpstreamTimeoutError as exc:
        log_gateway_event(request, "gateway.upstream.error", step=service)
        raise GatewayError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "UPSTREAM_TIMEOUT",
            "Upstream service timed out",
        ) from exc
    except UpstreamServiceError as exc:
        log_gateway_event(request, "gateway.upstream.error", step=service)
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Upstream service error",
        ) from exc


async def download_upstream(
    request: Request,
    client: Any,
    service: str,
    path: str,
    *,
    headers: Mapping[str, str] | None = None,
) -> UpstreamResponse:
    try:
        return await client.download(service, path, headers=headers)
    except UpstreamTimeoutError as exc:
        log_gateway_event(request, "gateway.upstream.error", step=service)
        raise GatewayError(
            status.HTTP_504_GATEWAY_TIMEOUT,
            "UPSTREAM_TIMEOUT",
            "Upstream service timed out",
        ) from exc
    except UpstreamServiceError as exc:
        log_gateway_event(request, "gateway.upstream.error", step=service)
        raise GatewayError(
            status.HTTP_502_BAD_GATEWAY,
            "UPSTREAM_SERVICE_ERROR",
            "Upstream service error",
        ) from exc


def download_response(upstream_response: UpstreamResponse) -> Response:
    return Response(
        content=upstream_response.content or b"",
        media_type=upstream_response.headers.get("content-type", "application/pdf"),
    )
