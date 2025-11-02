"""Request and response schemas for workflow-service."""

from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


PaymentScenario = Literal[
    "success",
    "insufficient_funds",
    "provider_unavailable",
    "suspected_fraud",
]


class StartOrderWorkflowRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: str
    user_email: str
    catalog_item_id: str
    quantity: int = Field(gt=0)
    idempotency_key: str | None = None
    correlation_id: str


class RequestPaymentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    user_id: str
    idempotency_key: str | None = None
    correlation_id: str
    payment_scenario: PaymentScenario = Field(
        default="success",
        validation_alias=AliasChoices("payment_scenario", "mock_scenario"),
    )


class WorkflowAcceptedResponse(BaseModel):
    workflow_id: str
    status: str
    correlation_id: str
    order_id: str | None = None


class WorkflowRunResponse(BaseModel):
    id: str
    workflow_type: str
    user_id: str
    user_email: str | None = None
    order_id: str | None = None
    status: str
    current_step: str | None = None
    failed_step: str | None = None
    failure_code: str | None = None
    last_error: str | None = None
    correlation_id: str
    idempotency_key: str | None = None
    invoice_document_id: str | None = None
    receipt_document_id: str | None = None
    payment_id: str | None = None
    notification_id: str | None = None
    payment_scenario: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
