"""PostgreSQL-backed order state storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


INITIAL_ORDER_STATUS = "created"
INITIAL_ORDER_REASON = "Order created"

ORDER_STATUS_INVOICE_GENERATED = "invoice_generated"
ORDER_STATUS_PAYMENT_COMPLETED = "payment_completed"
ORDER_STATUS_PAYMENT_FAILED = "payment_failed"
ORDER_STATUS_RECEIPT_GENERATED = "receipt_generated"
ORDER_STATUS_NOTIFICATION_SENT = "notification_sent"

ALLOWED_ORDER_TRANSITIONS = {
    INITIAL_ORDER_STATUS: {
        ORDER_STATUS_INVOICE_GENERATED,
    },
    ORDER_STATUS_INVOICE_GENERATED: {
        ORDER_STATUS_PAYMENT_COMPLETED,
        ORDER_STATUS_PAYMENT_FAILED,
    },
    ORDER_STATUS_PAYMENT_FAILED: {
        ORDER_STATUS_PAYMENT_COMPLETED,
        ORDER_STATUS_PAYMENT_FAILED,
    },
    ORDER_STATUS_PAYMENT_COMPLETED: {
        ORDER_STATUS_RECEIPT_GENERATED,
    },
    ORDER_STATUS_RECEIPT_GENERATED: {
        ORDER_STATUS_NOTIFICATION_SENT,
    },
    ORDER_STATUS_NOTIFICATION_SENT: set(),
}


class InvalidOrderTransitionError(RuntimeError):
    """Raised when an order status transition is not allowed."""


@dataclass(frozen=True)
class CreateOrder:
    user_id: str
    catalog_item_id: str
    quantity: int
    unit_price_kopecks: int
    total_kopecks: int
    currency: str


@dataclass(frozen=True)
class TransitionOrder:
    status: str
    reason: str | None


@dataclass(frozen=True)
class Order:
    id: str
    user_id: str
    catalog_item_id: str
    status: str
    quantity: int
    unit_price_kopecks: int
    total_kopecks: int
    currency: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class OrderHistoryEntry:
    id: str
    order_id: str
    status: str
    reason: str | None
    created_at: datetime


class OrderRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_order(self, order: CreateOrder) -> Order:
        now = datetime.now(UTC)
        order_id = f"order-{uuid4().hex}"
        history_id = f"order-history-{uuid4().hex}"

        async with self._session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO orders (
                        id, user_id, catalog_item_id, status, quantity,
                        unit_price_kopecks, total_kopecks, currency,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :user_id, :catalog_item_id, :status, :quantity,
                        :unit_price_kopecks, :total_kopecks, :currency,
                        :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": order_id,
                    "user_id": order.user_id,
                    "catalog_item_id": order.catalog_item_id,
                    "status": INITIAL_ORDER_STATUS,
                    "quantity": order.quantity,
                    "unit_price_kopecks": order.unit_price_kopecks,
                    "total_kopecks": order.total_kopecks,
                    "currency": order.currency,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO order_status_history (
                        id, order_id, status, reason, created_at
                    )
                    VALUES (
                        :id, :order_id, :status, :reason, :created_at
                    )
                    """
                ),
                {
                    "id": history_id,
                    "order_id": order_id,
                    "status": INITIAL_ORDER_STATUS,
                    "reason": INITIAL_ORDER_REASON,
                    "created_at": now,
                },
            )
            await session.commit()

        return Order(
            id=order_id,
            user_id=order.user_id,
            catalog_item_id=order.catalog_item_id,
            status=INITIAL_ORDER_STATUS,
            quantity=order.quantity,
            unit_price_kopecks=order.unit_price_kopecks,
            total_kopecks=order.total_kopecks,
            currency=order.currency,
            created_at=now,
            updated_at=now,
        )

    async def find_order_by_id(self, order_id: str) -> Order | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, user_id, catalog_item_id, status, quantity,
                        unit_price_kopecks, total_kopecks, currency,
                        created_at, updated_at
                    FROM orders
                    WHERE id = :order_id
                    """
                ),
                {"order_id": order_id},
            )
            row = result.mappings().first()

        if row is None:
            return None

        return self._order_from_row(row)

    async def list_orders_by_user(self, user_id: str) -> list[Order]:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, user_id, catalog_item_id, status, quantity,
                        unit_price_kopecks, total_kopecks, currency,
                        created_at, updated_at
                    FROM orders
                    WHERE user_id = :user_id
                    ORDER BY created_at DESC, id DESC
                    """
                ),
                {"user_id": user_id},
            )
            rows = result.mappings().all()

        return [self._order_from_row(row) for row in rows]

    async def transition_order(
        self,
        order_id: str,
        transition: TransitionOrder,
    ) -> Order | None:
        now = datetime.now(UTC)
        history_id = f"order-history-{uuid4().hex}"

        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, user_id, catalog_item_id, status, quantity,
                        unit_price_kopecks, total_kopecks, currency,
                        created_at, updated_at
                    FROM orders
                    WHERE id = :order_id
                    FOR UPDATE
                    """
                ),
                {"order_id": order_id},
            )
            row = result.mappings().first()
            if row is None:
                return None

            current_status = row["status"]
            allowed_next_statuses = ALLOWED_ORDER_TRANSITIONS.get(current_status, set())
            if transition.status not in allowed_next_statuses:
                raise InvalidOrderTransitionError(
                    f"Cannot transition order from {current_status} "
                    f"to {transition.status}"
                )

            await session.execute(
                text(
                    """
                    UPDATE orders
                    SET status = :status,
                        updated_at = :updated_at
                    WHERE id = :order_id
                    """
                ),
                {
                    "order_id": order_id,
                    "status": transition.status,
                    "updated_at": now,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO order_status_history (
                        id, order_id, status, reason, created_at
                    )
                    VALUES (
                        :id, :order_id, :status, :reason, :created_at
                    )
                    """
                ),
                {
                    "id": history_id,
                    "order_id": order_id,
                    "status": transition.status,
                    "reason": transition.reason,
                    "created_at": now,
                },
            )
            await session.commit()

        return Order(
            id=row["id"],
            user_id=row["user_id"],
            catalog_item_id=row["catalog_item_id"],
            status=transition.status,
            quantity=row["quantity"],
            unit_price_kopecks=row["unit_price_kopecks"],
            total_kopecks=row["total_kopecks"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=now,
        )

    async def list_order_history(self, order_id: str) -> list[OrderHistoryEntry]:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, order_id, status, reason, created_at
                    FROM order_status_history
                    WHERE order_id = :order_id
                    ORDER BY created_at, id
                    """
                ),
                {"order_id": order_id},
            )
            rows = result.mappings().all()

        return [self._history_entry_from_row(row) for row in rows]

    @staticmethod
    def _order_from_row(row: Mapping[str, Any]) -> Order:
        return Order(
            id=row["id"],
            user_id=row["user_id"],
            catalog_item_id=row["catalog_item_id"],
            status=row["status"],
            quantity=row["quantity"],
            unit_price_kopecks=row["unit_price_kopecks"],
            total_kopecks=row["total_kopecks"],
            currency=row["currency"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _history_entry_from_row(row: Mapping[str, Any]) -> OrderHistoryEntry:
        return OrderHistoryEntry(
            id=row["id"],
            order_id=row["order_id"],
            status=row["status"],
            reason=row["reason"],
            created_at=row["created_at"],
        )
