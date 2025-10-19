"""API gateway application wiring."""

from __future__ import annotations

from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import create_app

from .config import get_gateway_config
from .idempotency import get_idempotency_store
from .responses import GatewayError, handle_gateway_error
from .routes import auth, catalog, documents, orders, workflows
from .upstream import get_upstream_client


app = create_app("api-gateway")
gateway_config = get_gateway_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(gateway_config.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_exception_handler(GatewayError, handle_gateway_error)

app.include_router(auth.router)
app.include_router(catalog.router)
app.include_router(orders.router)
app.include_router(documents.router)
app.include_router(workflows.router)


async def dispose_gateway_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "gateway_database_engine", None)
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_gateway_database_engine)

__all__ = ["app", "get_idempotency_store", "get_upstream_client"]
