"""Order service application entrypoint."""

from typing import Protocol

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)

from .repository import (
    CreateOrder,
    InvalidOrderTransitionError,
    Order,
    OrderHistoryEntry,
    OrderRepository,
    TransitionOrder,
)
from .schemas import (
    CreateOrderRequest,
    OrderHistoryEntryResponse,
    OrderHistoryResponse,
    OrderResponse,
    OrdersResponse,
    TransitionOrderRequest,
)

app = create_app("order-service")


class OrderStorage(Protocol):
    async def create_order(self, order: CreateOrder) -> Order:
        """Create an order with initial status history."""

    async def find_order_by_id(self, order_id: str) -> Order | None:
        """Return one stored order by id."""

    async def list_orders_by_user(self, user_id: str) -> list[Order]:
        """Return stored orders for a user."""

    async def list_order_history(self, order_id: str) -> list[OrderHistoryEntry]:
        """Return status history for one order."""

    async def transition_order(
        self,
        order_id: str,
        transition: TransitionOrder,
    ) -> Order | None:
        """Transition one order and append status history."""


def get_order_repository() -> OrderStorage:
    engine = getattr(app.state, "order_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.order_database_engine = engine
        app.state.order_session_factory = create_async_session_factory(engine)

    return OrderRepository(app.state.order_session_factory)


def order_response(order: Order) -> OrderResponse:
    return OrderResponse(
        id=order.id,
        user_id=order.user_id,
        catalog_item_id=order.catalog_item_id,
        status=order.status,
        quantity=order.quantity,
        unit_price_kopecks=order.unit_price_kopecks,
        total_kopecks=order.total_kopecks,
        currency=order.currency,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def history_entry_response(entry: OrderHistoryEntry) -> OrderHistoryEntryResponse:
    return OrderHistoryEntryResponse(
        id=entry.id,
        order_id=entry.order_id,
        status=entry.status,
        reason=entry.reason,
        created_at=entry.created_at,
    )


@app.post("/orders", response_model=OrderResponse, tags=["orders"])
async def create_order(
    request: CreateOrderRequest,
    repository: OrderStorage = Depends(get_order_repository),
) -> OrderResponse:
    order = await repository.create_order(
        CreateOrder(
            user_id=request.user_id,
            catalog_item_id=request.catalog_item_id,
            quantity=request.quantity,
            unit_price_kopecks=request.unit_price_kopecks,
            total_kopecks=request.total_kopecks,
            currency=request.currency,
        )
    )
    return order_response(order)


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["orders"])
async def get_order(
    order_id: str,
    repository: OrderStorage = Depends(get_order_repository),
) -> OrderResponse:
    order = await repository.find_order_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order_response(order)


@app.get("/orders", response_model=OrdersResponse, tags=["orders"])
async def list_orders(
    user_id: str,
    repository: OrderStorage = Depends(get_order_repository),
) -> OrdersResponse:
    orders = await repository.list_orders_by_user(user_id)
    return OrdersResponse(orders=[order_response(order) for order in orders])


@app.get(
    "/orders/{order_id}/history",
    response_model=OrderHistoryResponse,
    tags=["orders"],
)
async def get_order_history(
    order_id: str,
    repository: OrderStorage = Depends(get_order_repository),
) -> OrderHistoryResponse:
    order = await repository.find_order_by_id(order_id)
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    history = await repository.list_order_history(order_id)
    return OrderHistoryResponse(
        history=[history_entry_response(entry) for entry in history]
    )


@app.post(
    "/orders/{order_id}/transitions",
    response_model=OrderResponse,
    tags=["orders"],
)
async def transition_order(
    order_id: str,
    request: TransitionOrderRequest,
    repository: OrderStorage = Depends(get_order_repository),
) -> OrderResponse:
    try:
        order = await repository.transition_order(
            order_id,
            TransitionOrder(status=request.status, reason=request.reason),
        )
    except InvalidOrderTransitionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Invalid order transition",
        ) from exc

    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    return order_response(order)


async def dispose_order_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "order_database_engine", None)
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_order_database_engine)
