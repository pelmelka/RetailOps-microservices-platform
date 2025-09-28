"""FastAPI app factory used by backend services."""

from fastapi import FastAPI

from .correlation import add_correlation_middleware
from .health import build_health_response
from .logging import configure_json_logging


def create_app(service_name: str) -> FastAPI:
    """Create a FastAPI app with shared service defaults."""
    normalized_service_name = service_name.strip()
    if not normalized_service_name:
        raise ValueError("service_name must not be empty")

    app = FastAPI(title=normalized_service_name)
    app.state.service_name = normalized_service_name
    app.state.logger = configure_json_logging(normalized_service_name)

    add_correlation_middleware(app)

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return build_health_response(normalized_service_name)

    @app.get("/ready", tags=["health"])
    async def ready() -> dict[str, str]:
        return build_health_response(normalized_service_name)

    return app
