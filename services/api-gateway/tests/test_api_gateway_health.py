from typing import Any, Mapping

from fastapi.testclient import TestClient

from api_gateway.idempotency import IdempotencyRecord
from api_gateway.main import app, get_idempotency_store, get_upstream_client
from api_gateway.upstream import UpstreamResponse, UpstreamTimeoutError


CURRENT_USER = {
    "user_id": "user-local-001",
    "username": "local-user",
    "email": "local-user@example.test",
    "display_name": "Local User",
    "is_active": True,
}


def order(status: str = "created", user_id: str = "user-local-001") -> dict[str, Any]:
    return {
        "id": "order-test-001",
        "user_id": user_id,
        "catalog_item_id": "catalog-item-basic",
        "status": status,
        "quantity": 2,
        "unit_price_kopecks": 199000,
        "total_kopecks": 398000,
        "currency": "RUB",
        "created_at": "2026-05-26T12:00:00Z",
        "updated_at": "2026-05-26T12:00:00Z",
    }


class FakeUpstreamClient:
    def __init__(self) -> None:
        self.responses: dict[tuple[str, str, str], list[UpstreamResponse]] = {}
        self.requests: list[dict[str, Any]] = []

    def add(
        self,
        method: str,
        service: str,
        path: str,
        status_code: int,
        body: Any,
        headers: Mapping[str, str] | None = None,
        content: bytes | None = None,
    ) -> None:
        key = (method, service, path)
        self.responses.setdefault(key, []).append(
            UpstreamResponse(
                status_code=status_code,
                body=body,
                headers=headers or {},
                content=content,
            )
        )

    async def request(
        self,
        method: str,
        service: str,
        path: str,
        *,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> UpstreamResponse:
        self.requests.append(
            {
                "method": method,
                "service": service,
                "path": path,
                "json": json,
                "headers": dict(headers or {}),
            }
        )
        return self._pop(method, service, path)

    async def download(
        self,
        service: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> UpstreamResponse:
        self.requests.append(
            {
                "method": "GET",
                "service": service,
                "path": path,
                "json": None,
                "headers": dict(headers or {}),
            }
        )
        return self._pop("GET", service, path)

    def _pop(self, method: str, service: str, path: str) -> UpstreamResponse:
        key = (method, service, path)
        if key not in self.responses or not self.responses[key]:
            raise AssertionError(f"Unexpected upstream request: {key}")
        return self.responses[key].pop(0)


class FakeIdempotencyStore:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str, str, str], IdempotencyRecord] = {}

    async def find_record(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        method: str,
        path: str,
    ) -> IdempotencyRecord | None:
        return self.records.get((user_id, idempotency_key, method, path))

    async def store_record(self, record: IdempotencyRecord) -> None:
        self.records[
            (
                record.user_id,
                record.idempotency_key,
                record.method,
                record.path,
            )
        ] = record


class TimeoutUpstreamClient:
    async def request(
        self,
        method: str,
        service: str,
        path: str,
        *,
        json: Any | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> UpstreamResponse:
        raise UpstreamTimeoutError("timed out")

    async def download(
        self,
        service: str,
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> UpstreamResponse:
        raise UpstreamTimeoutError("timed out")


def make_client(
    upstream: FakeUpstreamClient | TimeoutUpstreamClient | None = None,
    store: FakeIdempotencyStore | None = None,
) -> TestClient:
    app.dependency_overrides.clear()
    if upstream is not None:
        app.dependency_overrides[get_upstream_client] = lambda: upstream
    if store is not None:
        app.dependency_overrides[get_idempotency_store] = lambda: store
    return TestClient(app)


def add_current_user(upstream: FakeUpstreamClient, status_code: int = 200) -> None:
    upstream.add("GET", "auth", "/auth/me", status_code, CURRENT_USER)


def auth_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    headers = {"Authorization": "Bearer local-token"}
    if extra:
        headers.update(extra)
    return headers


def test_health_returns_200() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "api-gateway"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get("/health", headers={"X-Correlation-ID": "gateway-request-1"})

    assert response.headers["X-Correlation-ID"] == "gateway-request-1"


def test_public_auth_register_proxy() -> None:
    upstream = FakeUpstreamClient()
    upstream.add("POST", "auth", "/auth/register", 201, {**CURRENT_USER})
    client = make_client(upstream)

    response = client.post(
        "/api/auth/register",
        json={
            "username": "new-user",
            "email": "new-user@example.test",
            "password": "new-password-123",
        },
    )

    assert response.status_code == 201
    assert upstream.requests[0]["service"] == "auth"


def test_public_login_proxy() -> None:
    upstream = FakeUpstreamClient()
    upstream.add(
        "POST",
        "auth",
        "/auth/login",
        200,
        {"access_token": "signed-token", "token_type": "bearer"},
    )
    client = make_client(upstream)

    response = client.post(
        "/api/auth/login",
        json={"username": "local-user", "password": "local-password"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"] == "signed-token"


def test_public_catalog_list_proxy() -> None:
    upstream = FakeUpstreamClient()
    upstream.add("GET", "catalog", "/catalog/items", 200, {"items": []})
    client = make_client(upstream)

    response = client.get("/api/catalog/items")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_upstream_timeout_maps_to_504() -> None:
    client = make_client(TimeoutUpstreamClient())

    response = client.get("/api/catalog/items")

    assert response.status_code == 504
    assert response.json()["error"]["code"] == "UPSTREAM_TIMEOUT"


def test_protected_me_success() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    client = make_client(upstream)

    response = client.get("/api/auth/me", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["user_id"] == "user-local-001"


def test_protected_me_missing_token_returns_401() -> None:
    client = make_client(FakeUpstreamClient())

    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_TOKEN_MISSING"


def test_create_order_routes_to_workflow_service() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    add_current_user(upstream)
    upstream.add(
        "POST",
        "workflow",
        "/workflows/order-checkout",
        202,
        {
            "workflow_id": "workflow-test-001",
            "status": "accepted",
            "correlation_id": "correlation-test",
        },
    )
    client = make_client(upstream, FakeIdempotencyStore())

    response = client.post(
        "/api/orders",
        headers=auth_headers({"Idempotency-Key": "order-key-1"}),
        json={"catalog_item_id": "catalog-item-basic", "quantity": 2},
    )

    assert response.status_code == 202
    workflow_request = [
        call for call in upstream.requests if call["service"] == "workflow"
    ][0]
    assert workflow_request["json"]["user_id"] == "user-local-001"
    assert workflow_request["json"]["user_email"] == "local-user@example.test"
    assert workflow_request["json"]["catalog_item_id"] == "catalog-item-basic"


def test_create_order_requires_idempotency_key() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    client = make_client(upstream, FakeIdempotencyStore())

    response = client.post(
        "/api/orders",
        headers=auth_headers(),
        json={"catalog_item_id": "catalog-item-basic", "quantity": 1},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"


def test_create_order_rejects_user_id_from_client() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    client = make_client(upstream, FakeIdempotencyStore())

    response = client.post(
        "/api/orders",
        headers=auth_headers({"Idempotency-Key": "order-key-1"}),
        json={
            "catalog_item_id": "catalog-item-basic",
            "quantity": 2,
            "user_id": "evil-user",
        },
    )

    assert response.status_code == 422


def test_idempotency_replays_same_request() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    add_current_user(upstream)
    upstream.add(
        "POST",
        "workflow",
        "/workflows/order-checkout",
        202,
        {
            "workflow_id": "workflow-test-001",
            "status": "accepted",
            "correlation_id": "correlation-test",
        },
    )
    store = FakeIdempotencyStore()
    client = make_client(upstream, store)

    first = client.post(
        "/api/orders",
        headers=auth_headers({"Idempotency-Key": "order-key-1"}),
        json={"catalog_item_id": "catalog-item-basic", "quantity": 2},
    )
    second = client.post(
        "/api/orders",
        headers=auth_headers({"Idempotency-Key": "order-key-1"}),
        json={"catalog_item_id": "catalog-item-basic", "quantity": 2},
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.headers["Idempotency-Replayed"] == "true"
    assert first.json() == second.json()


def test_ownership_check_hides_foreign_order() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add("GET", "order", "/orders/order-test-001", 200, order("created", "other-user"))
    client = make_client(upstream)

    response = client.get("/api/orders/order-test-001", headers=auth_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ORDER_OWNERSHIP_NOT_FOUND"


def test_get_workflow_hides_foreign_workflow() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add(
        "GET",
        "workflow",
        "/workflows/workflow-test-001",
        200,
        {"id": "workflow-test-001", "user_id": "other-user"},
    )
    client = make_client(upstream)

    response = client.get("/api/workflows/workflow-test-001", headers=auth_headers())

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "WORKFLOW_NOT_FOUND"


def test_get_order_workflow_checks_order_ownership_and_routes_to_workflow() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add("GET", "order", "/orders/order-test-001", 200, order("notification_sent"))
    upstream.add(
        "GET",
        "workflow",
        "/workflows/orders/order-test-001?user_id=user-local-001",
        200,
        {
            "id": "workflow-test-001",
            "user_id": "user-local-001",
            "order_id": "order-test-001",
            "status": "completed",
        },
    )
    client = make_client(upstream)

    response = client.get(
        "/api/orders/order-test-001/workflow",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["id"] == "workflow-test-001"


def test_payment_request_routes_to_workflow_after_ownership_check() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add("GET", "order", "/orders/order-test-001", 200, order("invoice_generated"))
    upstream.add(
        "POST",
        "workflow",
        "/workflows/orders/order-test-001/payments",
        202,
        {
            "workflow_id": "workflow-test-001",
            "status": "awaiting_payment",
            "correlation_id": "correlation-test",
            "order_id": "order-test-001",
        },
    )
    client = make_client(upstream, FakeIdempotencyStore())

    response = client.post(
        "/api/orders/order-test-001/payments",
        headers=auth_headers({"Idempotency-Key": "payment-key-1"}),
        json={"payment_scenario": "success"},
    )

    assert response.status_code == 202
    workflow_request = [
        call for call in upstream.requests if call["service"] == "workflow"
    ][0]
    assert workflow_request["json"]["payment_scenario"] == "success"


def test_legacy_invoice_calls_document_and_order_transition() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add("GET", "order", "/orders/order-test-001", 200, order("created"))
    upstream.add(
        "POST",
        "document",
        "/documents/invoice",
        201,
        {"id": "document-invoice-001", "order_id": "order-test-001"},
    )
    upstream.add(
        "POST",
        "order",
        "/orders/order-test-001/transitions",
        200,
        order("invoice_generated"),
    )
    client = make_client(upstream, FakeIdempotencyStore())

    response = client.post(
        "/api/orders/order-test-001/documents/invoice",
        headers=auth_headers({"Idempotency-Key": "invoice-key-1"}),
        json={},
    )

    assert response.status_code == 201
    transition_request = upstream.requests[-1]
    assert transition_request["path"] == "/orders/order-test-001/transitions"
    assert transition_request["json"]["status"] == "invoice_generated"


def test_receipt_before_payment_completed_returns_409() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add("GET", "order", "/orders/order-test-001", 200, order("invoice_generated"))
    client = make_client(upstream, FakeIdempotencyStore())

    response = client.post(
        "/api/orders/order-test-001/documents/receipt",
        headers=auth_headers({"Idempotency-Key": "receipt-key-1"}),
        json={},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "WORKFLOW_STEP_CONFLICT"


def test_download_document_checks_metadata_order() -> None:
    upstream = FakeUpstreamClient()
    add_current_user(upstream)
    upstream.add("GET", "order", "/orders/order-test-001", 200, order("invoice_generated"))
    upstream.add(
        "GET",
        "document",
        "/documents/document-test-001",
        200,
        {"id": "document-test-001", "order_id": "order-test-001"},
    )
    upstream.add(
        "GET",
        "document",
        "/documents/document-test-001/download",
        200,
        None,
        {"content-type": "application/pdf"},
        b"%PDF",
    )
    client = make_client(upstream)

    response = client.get(
        "/api/orders/order-test-001/documents/document-test-001/download",
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.content == b"%PDF"
