from fastapi.testclient import TestClient

from mwp_common import create_app


def test_health_returns_200() -> None:
    client = TestClient(create_app("test-service"))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "service": "test-service",
        "status": "ok",
    }


def test_ready_returns_200() -> None:
    client = TestClient(create_app("test-service"))

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "service": "test-service",
        "status": "ok",
    }
