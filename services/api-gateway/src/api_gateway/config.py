"""Runtime configuration for api-gateway orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping


@dataclass(frozen=True)
class GatewayConfig:
    auth_service_url: str
    catalog_service_url: str
    order_service_url: str
    document_service_url: str
    payment_service_url: str
    notification_service_url: str
    workflow_service_url: str
    upstream_timeout_seconds: float
    cors_allowed_origins: tuple[str, ...]


def _read_float(
    source: Mapping[str, str],
    name: str,
    default: float,
) -> float:
    raw_value = source.get(name)
    if raw_value is None or raw_value == "":
        return default
    return float(raw_value)


def _read_origins(source: Mapping[str, str]) -> tuple[str, ...]:
    raw_value = source.get(
        "GATEWAY_CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173",
    )
    return tuple(origin.strip() for origin in raw_value.split(",") if origin.strip())


def get_gateway_config(env: Mapping[str, str] | None = None) -> GatewayConfig:
    source = environ if env is None else env
    return GatewayConfig(
        auth_service_url=source.get("AUTH_SERVICE_URL", "http://auth-service:8000"),
        catalog_service_url=source.get(
            "CATALOG_SERVICE_URL",
            "http://catalog-service:8000",
        ),
        order_service_url=source.get("ORDER_SERVICE_URL", "http://order-service:8000"),
        document_service_url=source.get(
            "DOCUMENT_SERVICE_URL",
            "http://document-service:8000",
        ),
        payment_service_url=source.get(
            "PAYMENT_SERVICE_URL",
            "http://payment-service:8000",
        ),
        notification_service_url=source.get(
            "NOTIFICATION_SERVICE_URL",
            "http://notification-service:8000",
        ),
        workflow_service_url=source.get(
            "WORKFLOW_SERVICE_URL",
            "http://workflow-service:8000",
        ),
        upstream_timeout_seconds=_read_float(
            source,
            "UPSTREAM_TIMEOUT_SECONDS",
            5.0,
        ),
        cors_allowed_origins=_read_origins(source),
    )
