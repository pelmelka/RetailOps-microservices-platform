"""Correlation middleware and request context helpers."""

from uuid import uuid4

from fastapi import FastAPI, Request, Response

CORRELATION_ID_HEADER = "X-Correlation-ID"


def add_correlation_middleware(app: FastAPI) -> None:
    """Attach middleware that preserves or creates request correlation IDs."""

    @app.middleware("http")
    async def correlation_middleware(request: Request, call_next) -> Response:
        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers[CORRELATION_ID_HEADER] = correlation_id
        return response


def request_context(request: Request) -> dict[str, str | None]:
    """Return request identifiers stored by correlation middleware."""
    return {"correlation_id": getattr(request.state, "correlation_id", None)}
