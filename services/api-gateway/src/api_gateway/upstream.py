"""HTTP upstream client for api-gateway service-to-service calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from .config import GatewayConfig


@dataclass(frozen=True)
class UpstreamResponse:
    status_code: int
    body: Any
    headers: Mapping[str, str]
    content: bytes | None = None


class UpstreamServiceError(RuntimeError):
    """Raised when an upstream service cannot be reached."""


class UpstreamTimeoutError(UpstreamServiceError):
    """Raised when an upstream service call times out."""


class HttpxUpstreamClient:
    def __init__(self, config: GatewayConfig) -> None:
        self._base_urls = {
            "auth": config.auth_service_url,
            "catalog": config.catalog_service_url,
            "order": config.order_service_url,
            "document": config.document_service_url,
            "payment": config.payment_service_url,
            "notification": config.notification_service_url,
            "workflow": config.workflow_service_url,
        }
        self._timeout = config.upstream_timeout_seconds

    async def request(
        self,
        method: str,
        service: str,
        path: str,
        *,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> UpstreamResponse:
        response = await self._send(
            method,
            service,
            path,
            json=json,
            headers=headers,
        )
        return UpstreamResponse(
            status_code=response.status_code,
            body=self._response_body(response),
            headers=response.headers,
        )

    async def download(
        self,
        service: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> UpstreamResponse:
        response = await self._send("GET", service, path, headers=headers)
        return UpstreamResponse(
            status_code=response.status_code,
            body=self._response_body(response),
            headers=response.headers,
            content=response.content,
        )

    async def _send(
        self,
        method: str,
        service: str,
        path: str,
        *,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        base_url = self._base_urls[service].rstrip("/")
        url = f"{base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                return await client.request(
                    method,
                    url,
                    json=json,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError(str(exc)) from exc
        except httpx.RequestError as exc:
            raise UpstreamServiceError(str(exc)) from exc

    @staticmethod
    def _response_body(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return {"detail": response.text}


def get_upstream_client() -> HttpxUpstreamClient:
    from .config import get_gateway_config

    return HttpxUpstreamClient(get_gateway_config())
