"""Shared health and readiness response helpers."""


def build_health_response(service_name: str, status: str = "ok") -> dict[str, str]:
    """Build the standard health/readiness response body."""
    return {
        "service": service_name,
        "status": status,
    }
