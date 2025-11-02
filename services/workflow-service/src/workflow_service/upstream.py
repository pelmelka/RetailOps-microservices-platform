"""HTTP clients for workflow-service calls to domain services."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from .config import WorkflowConfig


@dataclass(frozen=True)
class UpstreamResponse:
    status_code: int
    body: Any
    headers: Mapping[str, str]


class UpstreamServiceError(RuntimeError):
    """Raised when an upstream service cannot be reached."""


class UpstreamTimeoutError(UpstreamServiceError):
    """Raised when an upstream service call times out."""


class WorkflowUpstreamClient:
    def __init__(self, config: WorkflowConfig) -> None:
        self._base_urls = {
            "catalog": config.catalog_service_url,
            "order": config.order_service_url,
            "document": config.document_service_url,
            "payment": config.payment_service_url,
            "notification": config.notification_service_url,
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
        base_url = self._base_urls[service].rstrip("/")
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.request(
                    method,
                    f"{base_url}{path}",
                    json=json,
                    headers=headers,
                )
        except httpx.TimeoutException as exc:
            raise UpstreamTimeoutError(str(exc)) from exc
        except httpx.RequestError as exc:
            raise UpstreamServiceError(str(exc)) from exc

        return UpstreamResponse(
            status_code=response.status_code,
            body=self._response_body(response),
            headers=response.headers,
        )

    @staticmethod
    def _response_body(response: httpx.Response) -> Any:
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return {"detail": response.text}
