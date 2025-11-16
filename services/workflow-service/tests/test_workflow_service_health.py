from fastapi.testclient import TestClient

from workflow_service.main import app
from workflow_service.schemas import RequestPaymentRequest


def make_client(monkeypatch) -> TestClient:
    monkeypatch.setenv("WORKFLOW_WORKER_ENABLED", "false")
    app.dependency_overrides.clear()
    return TestClient(app)


def test_health_returns_200(monkeypatch) -> None:
    client = make_client(monkeypatch)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["service"] == "workflow-service"


def test_payment_request_accepts_legacy_mock_scenario_alias() -> None:
    request = RequestPaymentRequest.model_validate(
        {
            "user_id": "user-local-001",
            "correlation_id": "correlation-test",
            "mock_scenario": "insufficient_funds",
        }
    )

    assert request.payment_scenario == "insufficient_funds"
