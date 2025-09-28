from fastapi.testclient import TestClient

from mwp_common import create_app


def test_correlation_id_is_preserved_when_provided() -> None:
    client = TestClient(create_app("test-service"))

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "request-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "request-123"


def test_correlation_id_is_generated_when_missing() -> None:
    client = TestClient(create_app("test-service"))

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"]



def test_unknown_trace_headers_do_not_break_requests() -> None:
    client = TestClient(create_app("test-service"))

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "request-456",
            "X-Request-Source": "smoke-check",
            "X-Debug-Trace-ID": "trace-1",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "request-456"
