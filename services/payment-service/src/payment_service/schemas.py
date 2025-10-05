"""Request and response schemas for payment-service endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class CreatePaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order_id: str
    amount_kopecks: int = Field(gt=0)
    currency: Literal["RUB"] = "RUB"
    payment_method: Literal["card"] = "card"
    mock_scenario: Literal[
        "success",
        "insufficient_funds",
        "provider_unavailable",
        "suspected_fraud",
    ] | None = None
    failure_reason: str | None = None


class PaymentResponse(BaseModel):
    id: str
    order_id: str
    status: str
    amount_kopecks: int
    currency: str
    payment_method: str | None = None
    provider: str | None = None
    provider_reference: str | None = None
    provider_scenario: str | None = None
    failure_code: str | None = None
    failure_reason: str | None = None
    processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
