"""Request and response schemas for notification-service endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class CreateNotificationRequest(BaseModel):
    order_id: str
    channel: Literal["email"] = "email"
    recipient: str
    template_key: Literal[
        "order_created",
        "invoice_generated",
        "payment_completed",
        "payment_failed",
        "receipt_generated",
        "workflow_completed",
    ]


class NotificationResponse(BaseModel):
    id: str
    order_id: str
    channel: str
    status: str
    recipient: str
    template_key: str | None = None
    subject: str | None = None
    message: str
    provider: str | None = None
    provider_reference: str | None = None
    sent_at: datetime | None = None
    delivery_attempts: int
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime
