"""Runtime configuration for workflow-service."""

from __future__ import annotations

from dataclasses import dataclass
from os import environ
from typing import Mapping

from mwp_common.config import get_runtime_config


@dataclass(frozen=True)
class WorkflowConfig:
    redis_url: str
    catalog_service_url: str
    order_service_url: str
    document_service_url: str
    payment_service_url: str
    notification_service_url: str
    upstream_timeout_seconds: float
    worker_enabled: bool
    worker_consumer_name: str


def _read_float(source: Mapping[str, str], name: str, default: float) -> float:
    raw_value = source.get(name)
    if raw_value is None or raw_value == "":
        return default
    return float(raw_value)


def _read_bool(source: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = source.get(name)
    if raw_value is None or raw_value == "":
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def get_workflow_config(env: Mapping[str, str] | None = None) -> WorkflowConfig:
    source = environ if env is None else env
    runtime = get_runtime_config(source)
    return WorkflowConfig(
        redis_url=runtime.redis_url or source.get("REDIS_URL", "redis://redis:6379/0"),
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
        upstream_timeout_seconds=_read_float(
            source,
            "UPSTREAM_TIMEOUT_SECONDS",
            5.0,
        ),
        worker_enabled=_read_bool(source, "WORKFLOW_WORKER_ENABLED", True),
        worker_consumer_name=source.get(
            "WORKFLOW_WORKER_CONSUMER_NAME",
            "workflow-service-local",
        ),
    )
