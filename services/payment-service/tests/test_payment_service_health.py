from datetime import UTC, datetime

from fastapi.testclient import TestClient

from payment_service.main import app, get_payment_provider, get_payment_repository
from payment_service.provider import (
    FAILURE_CODE_INSUFFICIENT_FUNDS,
    FAILURE_CODE_PROVIDER_UNAVAILABLE,
    FAILURE_CODE_SUSPECTED_FRAUD,
    LOCAL_PAYMENT_PROVIDER_NAME,
    PAYMENT_SCENARIO_INSUFFICIENT_FUNDS,
    PAYMENT_SCENARIO_PROVIDER_UNAVAILABLE,
    PAYMENT_SCENARIO_SUCCESS,
    PAYMENT_SCENARIO_SUSPECTED_FRAUD,
    PAYMENT_STATUS_COMPLETED,
    PAYMENT_STATUS_FAILED,
    PaymentProviderRequest,
    PaymentProviderResult,
)
from payment_service.repository import CreatePayment, Payment


PAYMENT_CREATED_AT = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)


class FakePaymentProvider:
    def process_payment(self, request: PaymentProviderRequest) -> PaymentProviderResult:
        failure_codes = {
            PAYMENT_SCENARIO_INSUFFICIENT_FUNDS: FAILURE_CODE_INSUFFICIENT_FUNDS,
            PAYMENT_SCENARIO_PROVIDER_UNAVAILABLE: FAILURE_CODE_PROVIDER_UNAVAILABLE,
            PAYMENT_SCENARIO_SUSPECTED_FRAUD: FAILURE_CODE_SUSPECTED_FRAUD,
        }
        status = (
            PAYMENT_STATUS_COMPLETED
            if request.provider_scenario == PAYMENT_SCENARIO_SUCCESS
            else PAYMENT_STATUS_FAILED
        )
        return PaymentProviderResult(
            status=status,
            provider=LOCAL_PAYMENT_PROVIDER_NAME,
            provider_reference="local-pay-test-001",
            provider_scenario=request.provider_scenario,
            failure_code=failure_codes.get(request.provider_scenario),
            failure_reason=None
            if status == PAYMENT_STATUS_COMPLETED
            else request.failure_reason or f"{request.provider_scenario} failed",
            processed_at=PAYMENT_CREATED_AT,
        )


class FakePaymentRepository:
    def __init__(self) -> None:
        self.payments: dict[str, Payment] = {}

    async def create_payment(self, payment: CreatePayment) -> Payment:
        payment_id = f"payment-test-{len(self.payments) + 1:03d}"
        created = Payment(
            id=payment_id,
            order_id=payment.order_id,
            status=payment.status,
            amount_kopecks=payment.amount_kopecks,
            currency=payment.currency,
            payment_method=payment.payment_method,
            provider=payment.provider,
            provider_reference=payment.provider_reference,
            provider_scenario=payment.provider_scenario,
            failure_code=payment.failure_code,
            failure_reason=payment.failure_reason,
            processed_at=payment.processed_at,
            created_at=PAYMENT_CREATED_AT,
            updated_at=PAYMENT_CREATED_AT,
        )
        self.payments[payment_id] = created
        return created

    async def find_payment_by_id(self, payment_id: str) -> Payment | None:
        return self.payments.get(payment_id)


def make_client(
    repository: FakePaymentRepository | None = None,
    provider: FakePaymentProvider | None = None,
) -> TestClient:
    app.dependency_overrides.clear()
    if repository is not None:
        app.dependency_overrides[get_payment_repository] = lambda: repository
    if provider is not None:
        app.dependency_overrides[get_payment_provider] = lambda: provider
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

    assert response.json()["service"] == "payment-service"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "payment-request-1"},
    )

    assert response.headers["X-Correlation-ID"] == "payment-request-1"


def test_trace_headers_do_not_break_health_request() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "payment-request-2",
            "X-Debug-Trace-ID": "future-run",
            "X-Request-Source": "future-scenario",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "payment-request-2"


def test_create_payment_success_scenario() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "RUB",
            "payment_method": "card",
            "mock_scenario": "success",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == PAYMENT_STATUS_COMPLETED
    assert response.json()["provider"] == LOCAL_PAYMENT_PROVIDER_NAME
    assert response.json()["provider_scenario"] == PAYMENT_SCENARIO_SUCCESS
    assert response.json()["failure_code"] is None


def test_create_payment_insufficient_funds_scenario() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "RUB",
            "payment_method": "card",
            "mock_scenario": "insufficient_funds",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == PAYMENT_STATUS_FAILED
    assert response.json()["failure_code"] == FAILURE_CODE_INSUFFICIENT_FUNDS


def test_create_payment_provider_unavailable_scenario() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "RUB",
            "payment_method": "card",
            "mock_scenario": "provider_unavailable",
        },
    )

    assert response.status_code == 201
    assert response.json()["failure_code"] == FAILURE_CODE_PROVIDER_UNAVAILABLE


def test_create_payment_suspected_fraud_scenario() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "RUB",
            "payment_method": "card",
            "mock_scenario": "suspected_fraud",
        },
    )

    assert response.status_code == 201
    assert response.json()["failure_code"] == FAILURE_CODE_SUSPECTED_FRAUD


def test_create_payment_rejects_invalid_scenario() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "RUB",
            "mock_scenario": "not-a-scenario",
        },
    )

    assert response.status_code == 422


def test_create_payment_rejects_non_rub_currency() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "USD",
            "mock_scenario": "success",
        },
    )

    assert response.status_code == 422


def test_create_payment_rejects_old_mock_result_field() -> None:
    client = make_client(FakePaymentRepository(), FakePaymentProvider())

    response = client.post(
        "/payments",
        json={
            "order_id": "order-local-check",
            "amount_kopecks": 199000,
            "currency": "RUB",
            "mock_result": "failure",
        },
    )

    assert response.status_code == 422


def test_get_payment_returns_stored_payment() -> None:
    repository = FakePaymentRepository()
    repository.payments["payment-test-001"] = Payment(
        id="payment-test-001",
        order_id="order-local-check",
        status=PAYMENT_STATUS_COMPLETED,
        amount_kopecks=199000,
        currency="RUB",
        payment_method="card",
        provider=LOCAL_PAYMENT_PROVIDER_NAME,
        provider_reference="local-pay-test-001",
        provider_scenario=PAYMENT_SCENARIO_SUCCESS,
        failure_code=None,
        failure_reason=None,
        processed_at=PAYMENT_CREATED_AT,
        created_at=PAYMENT_CREATED_AT,
        updated_at=PAYMENT_CREATED_AT,
    )
    client = make_client(repository)

    response = client.get("/payments/payment-test-001")

    assert response.status_code == 200
    assert response.json()["id"] == "payment-test-001"
    assert response.json()["provider_reference"] == "local-pay-test-001"


def test_get_payment_returns_404_for_missing_payment() -> None:
    client = make_client(FakePaymentRepository())

    response = client.get("/payments/not-existing-payment")

    assert response.status_code == 404
    assert response.json() == {"detail": "Payment not found"}
