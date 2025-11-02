"""Redis Streams contracts for the order checkout workflow."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


WORKFLOW_COMMANDS_STREAM = "project.workflow.commands"
WORKFLOW_EVENTS_STREAM = "project.workflow.events"
WORKFLOW_DEAD_LETTER_STREAM = "project.workflow.dead_letter"

WORKFLOW_COMMANDS_GROUP = "workflow-service.commands"
WORKFLOW_EVENTS_GROUP = "workflow-service.events"

WORKFLOW_TYPE_ORDER_CHECKOUT = "order_checkout"

COMMAND_ORDER_CREATE = "order.create"
COMMAND_DOCUMENT_GENERATE_INVOICE = "document.generate_invoice"
COMMAND_PAYMENT_REQUESTED = "payment.requested"
COMMAND_PAYMENT_PROCESS = "payment.process"
COMMAND_DOCUMENT_GENERATE_RECEIPT = "document.generate_receipt"
COMMAND_NOTIFICATION_SEND = "notification.send"
COMMAND_NOTIFICATION_RETRY_REQUESTED = "notification.retry_requested"
COMMAND_WORKFLOW_MARK_FAILED = "workflow.mark_failed"

EVENT_ORDER_CREATED = "order.created"
EVENT_DOCUMENT_INVOICE_GENERATED = "document.invoice_generated"
EVENT_WORKFLOW_AWAITING_PAYMENT = "workflow.awaiting_payment"
EVENT_PAYMENT_COMPLETED = "payment.completed"
EVENT_PAYMENT_FAILED = "payment.failed"
EVENT_DOCUMENT_RECEIPT_GENERATED = "document.receipt_generated"
EVENT_NOTIFICATION_SENT = "notification.sent"
EVENT_NOTIFICATION_FAILED = "notification.failed"
EVENT_WORKFLOW_COMPLETED = "workflow.completed"
EVENT_WORKFLOW_FAILED = "workflow.failed"

MESSAGE_VERSION = "1"
PRODUCER_WORKFLOW_SERVICE = "workflow-service"


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_message_id() -> str:
    return str(uuid4())


def command_fields(
    *,
    message_type: str,
    workflow_id: str,
    correlation_id: str,
    causation_id: str | None = None,
    producer: str = PRODUCER_WORKFLOW_SERVICE,
    **fields: object,
) -> dict[str, str]:
    command_id = new_message_id()
    payload: dict[str, object] = {
        "message_id": command_id,
        "command_id": command_id,
        "message_type": message_type,
        "message_version": MESSAGE_VERSION,
        "workflow_id": workflow_id,
        "correlation_id": correlation_id,
        "causation_id": causation_id or "",
        "producer": producer,
        "created_at": utc_now_iso(),
    }
    payload.update(fields)
    return {key: "" if value is None else str(value) for key, value in payload.items()}


def event_fields(
    *,
    message_type: str,
    workflow_id: str,
    correlation_id: str,
    causation_id: str | None = None,
    producer: str = PRODUCER_WORKFLOW_SERVICE,
    **fields: object,
) -> dict[str, str]:
    event_id = new_message_id()
    payload: dict[str, object] = {
        "message_id": event_id,
        "event_id": event_id,
        "message_type": message_type,
        "message_version": MESSAGE_VERSION,
        "workflow_id": workflow_id,
        "correlation_id": correlation_id,
        "causation_id": causation_id or "",
        "producer": producer,
        "occurred_at": utc_now_iso(),
    }
    payload.update(fields)
    return {key: "" if value is None else str(value) for key, value in payload.items()}
