"""Smoke-check the Redis Streams async workflow through api-gateway."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from time import sleep, time
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


GATEWAY_URL = "http://localhost:8000"
COMPOSE_FILE = "deploy/docker-compose/docker-compose.yml"
COMPOSE_ENV = "deploy/docker-compose/.env.example"


@dataclass(frozen=True)
class SmokeResponse:
    status: int
    body: Any
    headers: dict[str, str]
    content: bytes


def request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    idempotency_key: str | None = None,
    body: dict[str, Any] | None = None,
    expected: set[int] | None = None,
) -> SmokeResponse:
    expected_statuses = expected or {200}
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    data = None if body is None else json.dumps(body).encode("utf-8")
    req = Request(f"{GATEWAY_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as response:
            content = response.read()
            status = response.status
            response_headers = dict(response.headers)
    except HTTPError as exc:
        content = exc.read()
        status = exc.code
        response_headers = dict(exc.headers)
    except URLError as exc:
        raise RuntimeError(f"{method} {path} failed: {exc}") from exc

    if status not in expected_statuses:
        raise RuntimeError(
            f"{method} {path} returned {status}, expected {expected_statuses}: "
            f"{content.decode('utf-8', errors='replace')}"
        )

    content_type = {
        key.lower(): value for key, value in response_headers.items()
    }.get("content-type", "")
    parsed_body: Any = None
    if content and "application/json" in content_type:
        parsed_body = json.loads(content.decode("utf-8"))

    return SmokeResponse(status, parsed_body, response_headers, content)


def wait_for(
    description: str,
    fetch: Callable[[], dict[str, Any]],
    predicate: Callable[[dict[str, Any]], bool],
    *,
    timeout_seconds: int = 70,
) -> dict[str, Any]:
    deadline = time() + timeout_seconds
    last: dict[str, Any] | None = None
    while time() < deadline:
        last = fetch()
        if predicate(last):
            return last
        sleep(1.5)
    raise RuntimeError(f"Timed out waiting for {description}; last={last}")


def assert_history_statuses(history: dict[str, Any], expected_statuses: list[str]) -> None:
    actual_statuses = [entry["status"] for entry in history["history"]]
    missing_statuses = [
        status for status in expected_statuses if status not in actual_statuses
    ]
    if missing_statuses:
        raise RuntimeError(
            f"Order history is missing statuses {missing_statuses}; "
            f"actual statuses: {actual_statuses}"
        )


def redis_stream_contains(stream: str, workflow_id: str) -> bool:
    command = compose_command() + [
        "-f",
        COMPOSE_FILE,
        "--env-file",
        COMPOSE_ENV,
        "exec",
        "-T",
        "redis",
        "redis-cli",
        "XRANGE",
        stream,
        "-",
        "+",
    ]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return workflow_id in result.stdout


def compose_command() -> list[str]:
    docker_compose = subprocess.run(
        ["docker", "compose", "version"],
        capture_output=True,
        text=True,
    )
    if docker_compose.returncode == 0:
        return ["docker", "compose"]
    return ["docker-compose"]


def main() -> int:
    run_id = str(int(time()))
    print("SMOKE async Redis Streams workflow through api-gateway")

    request("GET", "/health")
    print("PASS health")

    login = request(
        "POST",
        "/api/auth/login",
        body={"username": "local-user", "password": "local-password"},
    ).body
    token = login["access_token"]
    print("PASS login")

    catalog = request("GET", "/api/catalog/items").body
    if not catalog["items"]:
        raise RuntimeError("Catalog is empty")
    print("PASS catalog")

    accepted = request(
        "POST",
        "/api/orders",
        token=token,
        idempotency_key=f"async-order-success-{run_id}",
        body={"catalog_item_id": "catalog-item-basic", "quantity": 2},
        expected={202},
    ).body
    workflow_id = accepted["workflow_id"]
    print("PASS workflow accepted")

    workflow = wait_for(
        "invoice and awaiting_payment",
        lambda: request("GET", f"/api/workflows/{workflow_id}", token=token).body,
        lambda body: body.get("status") == "awaiting_payment"
        and body.get("order_id")
        and body.get("invoice_document_id"),
    )
    order_id = workflow["order_id"]
    invoice_id = workflow["invoice_document_id"]
    print("PASS invoice generated and workflow awaiting payment")

    invoice_pdf = request(
        "GET",
        f"/api/orders/{order_id}/documents/{invoice_id}/download",
        token=token,
    )
    if not invoice_pdf.content:
        raise RuntimeError("Downloaded invoice PDF is empty")
    print("PASS invoice download")

    request(
        "POST",
        f"/api/orders/{order_id}/payments",
        token=token,
        idempotency_key=f"async-payment-success-{run_id}",
        body={"payment_scenario": "success"},
        expected={202},
    )
    print("PASS payment request accepted")

    workflow = wait_for(
        "workflow completed",
        lambda: request("GET", f"/api/workflows/{workflow_id}", token=token).body,
        lambda body: body.get("status") == "completed"
        and body.get("receipt_document_id")
        and body.get("notification_id"),
    )
    receipt_id = workflow["receipt_document_id"]
    print("PASS workflow completed")

    history = request("GET", f"/api/orders/{order_id}/history", token=token).body
    assert_history_statuses(
        history,
        [
            "created",
            "invoice_generated",
            "payment_completed",
            "receipt_generated",
            "notification_sent",
        ],
    )
    print("PASS happy-path history")

    receipt_pdf = request(
        "GET",
        f"/api/orders/{order_id}/documents/{receipt_id}/download",
        token=token,
    )
    if not receipt_pdf.content:
        raise RuntimeError("Downloaded receipt PDF is empty")
    print("PASS receipt download")

    failure_accepted = request(
        "POST",
        "/api/orders",
        token=token,
        idempotency_key=f"async-order-failure-{run_id}",
        body={"catalog_item_id": "catalog-item-basic", "quantity": 1},
        expected={202},
    ).body
    failure_workflow_id = failure_accepted["workflow_id"]
    failure_workflow = wait_for(
        "failure workflow awaiting payment",
        lambda: request(
            "GET",
            f"/api/workflows/{failure_workflow_id}",
            token=token,
        ).body,
        lambda body: body.get("status") == "awaiting_payment"
        and body.get("order_id"),
    )
    failure_order_id = failure_workflow["order_id"]
    request(
        "POST",
        f"/api/orders/{failure_order_id}/payments",
        token=token,
        idempotency_key=f"async-payment-failure-{run_id}",
        body={"payment_scenario": "insufficient_funds"},
        expected={202},
    )
    failure_workflow = wait_for(
        "controlled payment failure",
        lambda: request(
            "GET",
            f"/api/workflows/{failure_workflow_id}",
            token=token,
        ).body,
        lambda body: body.get("failure_code") == "INSUFFICIENT_FUNDS",
    )
    if failure_workflow.get("receipt_document_id"):
        raise RuntimeError("Receipt was generated after failed payment")
    print("PASS controlled payment failure")

    request(
        "POST",
        f"/api/orders/{failure_order_id}/payments",
        token=token,
        idempotency_key=f"async-payment-retry-{run_id}",
        body={"payment_scenario": "success"},
        expected={202},
    )
    wait_for(
        "retry completion",
        lambda: request(
            "GET",
            f"/api/workflows/{failure_workflow_id}",
            token=token,
        ).body,
        lambda body: body.get("status") == "completed",
    )
    print("PASS retry after insufficient funds")

    if not redis_stream_contains("project.workflow.commands", workflow_id):
        raise RuntimeError("Workflow id not found in commands stream")
    if not redis_stream_contains("project.workflow.events", workflow_id):
        raise RuntimeError("Workflow id not found in events stream")
    print("PASS Redis Streams contain commands/events")

    print("PASS async workflow smoke")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL async workflow smoke: {exc}", file=sys.stderr)
        raise SystemExit(1)
