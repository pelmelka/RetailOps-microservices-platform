"""PostgreSQL-backed provider-style notification storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True)
class CreateNotification:
    id: str
    order_id: str
    channel: str
    status: str
    recipient: str
    template_key: str
    subject: str
    message: str
    provider: str
    provider_reference: str | None
    sent_at: datetime | None
    delivery_attempts: int
    last_error: str | None


@dataclass(frozen=True)
class Notification:
    id: str
    order_id: str
    channel: str
    status: str
    recipient: str
    template_key: str | None
    subject: str | None
    message: str
    provider: str | None
    provider_reference: str | None
    sent_at: datetime | None
    delivery_attempts: int
    last_error: str | None
    created_at: datetime
    updated_at: datetime


class NotificationRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_notification(
        self,
        notification: CreateNotification,
    ) -> Notification:
        now = datetime.now(UTC)

        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    INSERT INTO notifications (
                        id, order_id, channel, status, recipient, message,
                        template_key, subject, provider, provider_reference,
                        sent_at, delivery_attempts, last_error,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :order_id, :channel, :status, :recipient, :message,
                        :template_key, :subject, :provider, :provider_reference,
                        :sent_at, :delivery_attempts, :last_error,
                        :created_at, :updated_at
                    )
                    RETURNING
                        id, order_id, channel, status, recipient, message,
                        template_key, subject, provider, provider_reference,
                        sent_at, delivery_attempts, last_error,
                        created_at, updated_at
                    """
                ),
                {
                    **notification.__dict__,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            row = result.mappings().one()
            await session.commit()

        return self._notification_from_row(row)

    async def find_notification_by_id(
        self,
        notification_id: str,
    ) -> Notification | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, order_id, channel, status, recipient, message,
                        template_key, subject, provider, provider_reference,
                        sent_at, delivery_attempts, last_error,
                        created_at, updated_at
                    FROM notifications
                    WHERE id = :notification_id
                    """
                ),
                {"notification_id": notification_id},
            )
            row = result.mappings().first()

        if row is None:
            return None

        return self._notification_from_row(row)

    @staticmethod
    def _notification_from_row(row: Mapping[str, Any]) -> Notification:
        return Notification(
            id=row["id"],
            order_id=row["order_id"],
            channel=row["channel"],
            status=row["status"],
            recipient=row["recipient"],
            template_key=row["template_key"],
            subject=row["subject"],
            message=row["message"],
            provider=row["provider"],
            provider_reference=row["provider_reference"],
            sent_at=row["sent_at"],
            delivery_attempts=row["delivery_attempts"],
            last_error=row["last_error"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
