"""Request schemas for api-gateway workflow endpoints."""

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class CreateGatewayOrderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    catalog_item_id: str
    quantity: int = Field(gt=0)


class CreateGatewayPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    payment_scenario: Literal[
        "success",
        "insufficient_funds",
        "provider_unavailable",
        "suspected_fraud",
    ] = Field(
        default="success",
        validation_alias=AliasChoices("payment_scenario", "mock_scenario"),
    )


class CreateGatewayNotificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: Literal[
        "payment_failed",
        "workflow_completed",
    ] | None = None
    channel: Literal["email"] = "email"
