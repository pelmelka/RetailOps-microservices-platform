"""PostgreSQL-backed provider-style payment storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True)
class CreatePayment:
    order_id: str
    status: str
    amount_kopecks: int
    currency: str
    payment_method: str
    provider: str
    provider_reference: str
    provider_scenario: str
    failure_code: str | None
    failure_reason: str | None
    processed_at: datetime


@dataclass(frozen=True)
class Payment:
    id: str
    order_id: str
    status: str
    amount_kopecks: int
    currency: str
    payment_method: str | None
    provider: str | None
    provider_reference: str | None
    provider_scenario: str | None
    failure_code: str | None
    failure_reason: str | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PaymentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_payment(self, payment: CreatePayment) -> Payment:
        now = datetime.now(UTC)
        payment_id = f"payment-{uuid4().hex}"

        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    INSERT INTO payments (
                        id, order_id, status, amount_kopecks, currency,
                        payment_method, provider, provider_reference,
                        provider_scenario, failure_code, failure_reason,
                        processed_at, created_at, updated_at
                    )
                    VALUES (
                        :id, :order_id, :status, :amount_kopecks, :currency,
                        :payment_method, :provider, :provider_reference,
                        :provider_scenario, :failure_code, :failure_reason,
                        :processed_at, :created_at, :updated_at
                    )
                    RETURNING
                        id, order_id, status, amount_kopecks, currency,
                        payment_method, provider, provider_reference,
                        provider_scenario, failure_code, failure_reason,
                        processed_at, created_at, updated_at
                    """
                ),
                {
                    **payment.__dict__,
                    "id": payment_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            row = result.mappings().one()
            await session.commit()

        return self._payment_from_row(row)

    async def find_payment_by_id(self, payment_id: str) -> Payment | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, order_id, status, amount_kopecks, currency,
                        payment_method, provider, provider_reference,
                        provider_scenario, failure_code, failure_reason,
                        processed_at, created_at, updated_at
                    FROM payments
                    WHERE id = :payment_id
                    """
                ),
                {"payment_id": payment_id},
            )
            row = result.mappings().first()

        if row is None:
            return None

        return self._payment_from_row(row)

    @staticmethod
    def _payment_from_row(row: Mapping[str, Any]) -> Payment:
        return Payment(
            id=row["id"],
            order_id=row["order_id"],
            status=row["status"],
            amount_kopecks=row["amount_kopecks"],
            currency=row["currency"],
            payment_method=row["payment_method"],
            provider=row["provider"],
            provider_reference=row["provider_reference"],
            provider_scenario=row["provider_scenario"],
            failure_code=row["failure_code"],
            failure_reason=row["failure_reason"],
            processed_at=row["processed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
