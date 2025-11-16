from datetime import UTC, datetime

from fastapi.testclient import TestClient

from order_service.main import app, get_order_repository
from order_service.repository import (
    ALLOWED_ORDER_TRANSITIONS,
    INITIAL_ORDER_REASON,
    INITIAL_ORDER_STATUS,
    CreateOrder,
    InvalidOrderTransitionError,
    Order,
    OrderHistoryEntry,
    TransitionOrder,
)


ORDER_CREATED_AT = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)


class FakeOrderRepository:
    def __init__(self) -> None:
        self.orders: dict[str, Order] = {}
        self.history: dict[str, list[OrderHistoryEntry]] = {}

    async def create_order(self, order: CreateOrder) -> Order:
        order_id = f"order-test-{len(self.orders) + 1:03d}"
        created = Order(
            id=order_id,
            user_id=order.user_id,
            catalog_item_id=order.catalog_item_id,
            status=INITIAL_ORDER_STATUS,
            quantity=order.quantity,
            unit_price_kopecks=order.unit_price_kopecks,
            total_kopecks=order.total_kopecks,
            currency=order.currency,
            created_at=ORDER_CREATED_AT,
            updated_at=ORDER_CREATED_AT,
        )
        self.orders[order_id] = created
        self.history[order_id] = [
            OrderHistoryEntry(
                id="order-history-test-001",
                order_id=order_id,
                status=INITIAL_ORDER_STATUS,
                reason=INITIAL_ORDER_REASON,
                created_at=ORDER_CREATED_AT,
            )
        ]
        return created

    async def find_order_by_id(self, order_id: str) -> Order | None:
        return self.orders.get(order_id)

    async def list_orders_by_user(self, user_id: str) -> list[Order]:
        return [order for order in self.orders.values() if order.user_id == user_id]

    async def list_order_history(self, order_id: str) -> list[OrderHistoryEntry]:
        return self.history.get(order_id, [])

    async def transition_order(
        self,
        order_id: str,
        transition: TransitionOrder,
    ) -> Order | None:
        order = self.orders.get(order_id)
        if order is None:
            return None
        if transition.status not in ALLOWED_ORDER_TRANSITIONS.get(order.status, set()):
            raise InvalidOrderTransitionError()

        transitioned = Order(
            id=order.id,
            user_id=order.user_id,
            catalog_item_id=order.catalog_item_id,
            status=transition.status,
            quantity=order.quantity,
            unit_price_kopecks=order.unit_price_kopecks,
            total_kopecks=order.total_kopecks,
            currency=order.currency,
            created_at=order.created_at,
            updated_at=ORDER_CREATED_AT,
        )
        self.orders[order_id] = transitioned
        self.history.setdefault(order_id, []).append(
            OrderHistoryEntry(
                id=f"order-history-test-{len(self.history[order_id]) + 1:03d}",
                order_id=order_id,
                status=transition.status,
                reason=transition.reason,
                created_at=ORDER_CREATED_AT,
            )
        )
        return transitioned


def make_client(repository: FakeOrderRepository | None = None) -> TestClient:
    app.dependency_overrides.clear()
    if repository is not None:
        app.dependency_overrides[get_order_repository] = lambda: repository
    return TestClient(app)


def test_health_returns_200() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200


def test_ready_returns_200() -> None:
    client = make_client()

    response = client.get("/ready")

    assert response.status_code == 200


def test_health_response_includes_service_name() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.json()["service"] == "order-service"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "order-request-1"},
    )

    assert response.headers["X-Correlation-ID"] == "order-request-1"



def test_unknown_trace_headers_do_not_break_health_request() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "order-request-2",
            "X-Request-Source": "smoke-check",
            "X-Debug-Trace-ID": "trace-1",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "order-request-2"


def test_create_order_returns_created_order() -> None:
    repository = FakeOrderRepository()
    client = make_client(repository)

    response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 3,
            "unit_price_kopecks": 199000,
            "total_kopecks": 597000,
            "currency": "RUB",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": "order-test-001",
        "user_id": "user-local-001",
        "catalog_item_id": "catalog-item-basic",
        "status": "created",
        "quantity": 3,
        "unit_price_kopecks": 199000,
        "total_kopecks": 597000,
        "currency": "RUB",
        "created_at": "2026-05-24T12:00:00Z",
        "updated_at": "2026-05-24T12:00:00Z",
    }


def test_create_order_creates_initial_history_entry() -> None:
    repository = FakeOrderRepository()
    client = make_client(repository)

    create_response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 1,
            "unit_price_kopecks": 199000,
            "total_kopecks": 199000,
            "currency": "RUB",
        },
    )
    order_id = create_response.json()["id"]

    history_response = client.get(f"/orders/{order_id}/history")

    assert history_response.status_code == 200
    assert history_response.json() == {
        "history": [
            {
                "id": "order-history-test-001",
                "order_id": "order-test-001",
                "status": "created",
                "reason": "Order created",
                "created_at": "2026-05-24T12:00:00Z",
            }
        ]
    }


def test_create_order_rejects_total_mismatch() -> None:
    client = make_client(FakeOrderRepository())

    response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 3,
            "unit_price_kopecks": 199000,
            "total_kopecks": 100,
            "currency": "RUB",
        },
    )

    assert response.status_code == 422


def test_create_order_rejects_zero_quantity() -> None:
    client = make_client(FakeOrderRepository())

    response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 0,
            "unit_price_kopecks": 199000,
            "total_kopecks": 0,
            "currency": "RUB",
        },
    )

    assert response.status_code == 422


def test_create_order_rejects_stale_total_cents_field() -> None:
    client = make_client(FakeOrderRepository())

    response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "total_cents": 1990,
            "currency": "USD",
        },
    )

    assert response.status_code == 422


def test_get_order_returns_stored_order() -> None:
    repository = FakeOrderRepository()
    created_order = Order(
        id="order-test-001",
        user_id="user-local-001",
        catalog_item_id="catalog-item-basic",
        status=INITIAL_ORDER_STATUS,
        quantity=1,
        unit_price_kopecks=199000,
        total_kopecks=199000,
        currency="RUB",
        created_at=ORDER_CREATED_AT,
        updated_at=ORDER_CREATED_AT,
    )
    repository.orders[created_order.id] = created_order
    client = make_client(repository)

    response = client.get("/orders/order-test-001")

    assert response.status_code == 200
    assert response.json()["id"] == "order-test-001"
    assert response.json()["status"] == "created"
    assert response.json()["quantity"] == 1
    assert response.json()["unit_price_kopecks"] == 199000


def test_get_order_returns_404_for_missing_order() -> None:
    client = make_client(FakeOrderRepository())

    response = client.get("/orders/not-existing-order")

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}


def test_list_orders_returns_legacy_currency_snapshot() -> None:
    repository = FakeOrderRepository()
    repository.orders["order-legacy-usd"] = Order(
        id="order-legacy-usd",
        user_id="user-local-001",
        catalog_item_id="catalog-item-basic",
        status=INITIAL_ORDER_STATUS,
        quantity=1,
        unit_price_kopecks=199000,
        total_kopecks=199000,
        currency="USD",
        created_at=ORDER_CREATED_AT,
        updated_at=ORDER_CREATED_AT,
    )
    client = make_client(repository)

    response = client.get("/orders?user_id=user-local-001")

    assert response.status_code == 200
    assert response.json()["orders"][0]["currency"] == "USD"


def test_get_order_history_returns_entries_ordered_by_repository() -> None:
    repository = FakeOrderRepository()
    order = Order(
        id="order-test-001",
        user_id="user-local-001",
        catalog_item_id="catalog-item-basic",
        status=INITIAL_ORDER_STATUS,
        quantity=1,
        unit_price_kopecks=199000,
        total_kopecks=199000,
        currency="RUB",
        created_at=ORDER_CREATED_AT,
        updated_at=ORDER_CREATED_AT,
    )
    repository.orders[order.id] = order
    repository.history[order.id] = [
        OrderHistoryEntry(
            id="order-history-test-001",
            order_id=order.id,
            status=INITIAL_ORDER_STATUS,
            reason=INITIAL_ORDER_REASON,
            created_at=ORDER_CREATED_AT,
        )
    ]
    client = make_client(repository)

    response = client.get("/orders/order-test-001/history")

    assert response.status_code == 200
    assert response.json()["history"][0]["status"] == "created"


def test_transition_order_updates_status() -> None:
    repository = FakeOrderRepository()
    client = make_client(repository)
    create_response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 1,
            "unit_price_kopecks": 199000,
            "total_kopecks": 199000,
            "currency": "RUB",
        },
    )
    order_id = create_response.json()["id"]

    response = client.post(
        f"/orders/{order_id}/transitions",
        json={
            "status": "invoice_generated",
            "reason": "Invoice PDF generated",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "invoice_generated"


def test_transition_order_appends_history() -> None:
    repository = FakeOrderRepository()
    client = make_client(repository)
    create_response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 1,
            "unit_price_kopecks": 199000,
            "total_kopecks": 199000,
            "currency": "RUB",
        },
    )
    order_id = create_response.json()["id"]

    client.post(
        f"/orders/{order_id}/transitions",
        json={
            "status": "invoice_generated",
            "reason": "Invoice PDF generated",
        },
    )
    history_response = client.get(f"/orders/{order_id}/history")

    assert history_response.status_code == 200
    assert [entry["status"] for entry in history_response.json()["history"]] == [
        "created",
        "invoice_generated",
    ]


def test_transition_order_rejects_invalid_transition() -> None:
    repository = FakeOrderRepository()
    client = make_client(repository)
    create_response = client.post(
        "/orders",
        json={
            "user_id": "user-local-001",
            "catalog_item_id": "catalog-item-basic",
            "quantity": 1,
            "unit_price_kopecks": 199000,
            "total_kopecks": 199000,
            "currency": "RUB",
        },
    )
    order_id = create_response.json()["id"]

    response = client.post(
        f"/orders/{order_id}/transitions",
        json={
            "status": "receipt_generated",
            "reason": "Receipt before payment",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Invalid order transition"}


def test_transition_order_returns_404_for_missing_order() -> None:
    client = make_client(FakeOrderRepository())

    response = client.post(
        "/orders/not-existing-order/transitions",
        json={
            "status": "invoice_generated",
            "reason": "Invoice PDF generated",
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Order not found"}
