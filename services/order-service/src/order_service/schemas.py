"""Request and response schemas for order-service endpoints."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    catalog_item_id: str
    quantity: int = Field(gt=0)
    unit_price_kopecks: int = Field(ge=0)
    total_kopecks: int = Field(ge=0)
    currency: Literal["RUB"] = "RUB"

    @model_validator(mode="after")
    def validate_total_matches_snapshot(self) -> "CreateOrderRequest":
        expected_total = self.quantity * self.unit_price_kopecks
        if self.total_kopecks != expected_total:
            raise ValueError(
                "total_kopecks must equal quantity * unit_price_kopecks"
            )
        return self


class OrderResponse(BaseModel):
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


class OrdersResponse(BaseModel):
    orders: list[OrderResponse]


class TransitionOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "invoice_generated",
        "payment_completed",
        "payment_failed",
        "receipt_generated",
        "notification_sent",
    ]
    reason: str | None = None


class OrderHistoryEntryResponse(BaseModel):
    id: str
    order_id: str
    status: str
    reason: str | None = None
    created_at: datetime


class OrderHistoryResponse(BaseModel):
    history: list[OrderHistoryEntryResponse]
