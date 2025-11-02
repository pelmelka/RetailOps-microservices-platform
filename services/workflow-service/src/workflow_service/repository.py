"""PostgreSQL-backed workflow state storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mwp_common.workflow_contracts import WORKFLOW_TYPE_ORDER_CHECKOUT


STATUS_ACCEPTED = "accepted"
STATUS_ORDER_CREATING = "order_creating"
STATUS_INVOICE_GENERATING = "invoice_generating"
STATUS_AWAITING_PAYMENT = "awaiting_payment"
STATUS_PAYMENT_REQUESTED = "payment_requested"
STATUS_PAYMENT_PROCESSING = "payment_processing"
STATUS_RECEIPT_GENERATING = "receipt_generating"
STATUS_NOTIFICATION_SENDING = "notification_sending"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_NOTIFICATION_FAILED = "notification_failed"


@dataclass(frozen=True)
class CreateWorkflowRun:
    user_id: str
    user_email: str
    catalog_item_id: str
    quantity: int
    correlation_id: str
    idempotency_key: str | None = None


@dataclass(frozen=True)
class WorkflowRun:
    id: str
    workflow_type: str
    user_id: str
    user_email: str | None
    order_id: str | None
    status: str
    current_step: str | None
    failed_step: str | None
    failure_code: str | None
    last_error: str | None
    correlation_id: str
    idempotency_key: str | None
    catalog_item_id: str | None
    quantity: int | None
    invoice_document_id: str | None
    receipt_document_id: str | None
    payment_id: str | None
    notification_id: str | None
    payment_scenario: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class WorkflowRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_workflow_run(self, request: CreateWorkflowRun) -> WorkflowRun:
        now = datetime.now(UTC)
        workflow_id = str(uuid4())

        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    INSERT INTO workflow_runs (
                        id, workflow_type, user_id, user_email, order_id, status,
                        current_step, failed_step, failure_code, last_error,
                        correlation_id, idempotency_key, catalog_item_id, quantity,
                        invoice_document_id, receipt_document_id, payment_id,
                        notification_id, payment_scenario, created_at, updated_at,
                        completed_at
                    )
                    VALUES (
                        :id, :workflow_type, :user_id, :user_email, NULL, :status,
                        :current_step, NULL, NULL, NULL, :correlation_id,
                        :idempotency_key, :catalog_item_id, :quantity, NULL, NULL,
                        NULL, NULL, NULL, :created_at, :updated_at, NULL
                    )
                    RETURNING
                        id, workflow_type, user_id, user_email, order_id, status,
                        current_step, failed_step, failure_code, last_error,
                        correlation_id, idempotency_key, catalog_item_id, quantity,
                        invoice_document_id, receipt_document_id, payment_id,
                        notification_id, payment_scenario, created_at, updated_at,
                        completed_at
                    """
                ),
                {
                    "id": workflow_id,
                    "workflow_type": WORKFLOW_TYPE_ORDER_CHECKOUT,
                    "user_id": request.user_id,
                    "user_email": request.user_email,
                    "status": STATUS_ACCEPTED,
                    "current_step": STATUS_ACCEPTED,
                    "correlation_id": request.correlation_id,
                    "idempotency_key": request.idempotency_key,
                    "catalog_item_id": request.catalog_item_id,
                    "quantity": request.quantity,
                    "created_at": now,
                    "updated_at": now,
                },
            )
            row = result.mappings().one()
            await session.commit()

        return self._workflow_from_row(row)

    async def find_by_idempotency_key(
        self,
        *,
        user_id: str,
        idempotency_key: str | None,
    ) -> WorkflowRun | None:
        if not idempotency_key:
            return None
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, workflow_type, user_id, user_email, order_id, status,
                        current_step, failed_step, failure_code, last_error,
                        correlation_id, idempotency_key, catalog_item_id, quantity,
                        invoice_document_id, receipt_document_id, payment_id,
                        notification_id, payment_scenario, created_at, updated_at,
                        completed_at
                    FROM workflow_runs
                    WHERE user_id = :user_id
                        AND idempotency_key = :idempotency_key
                    ORDER BY created_at
                    LIMIT 1
                    """
                ),
                {"user_id": user_id, "idempotency_key": idempotency_key},
            )
            row = result.mappings().first()
        return None if row is None else self._workflow_from_row(row)

    async def find_by_id(self, workflow_id: str) -> WorkflowRun | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, workflow_type, user_id, user_email, order_id, status,
                        current_step, failed_step, failure_code, last_error,
                        correlation_id, idempotency_key, catalog_item_id, quantity,
                        invoice_document_id, receipt_document_id, payment_id,
                        notification_id, payment_scenario, created_at, updated_at,
                        completed_at
                    FROM workflow_runs
                    WHERE id = CAST(:workflow_id AS UUID)
                    """
                ),
                {"workflow_id": workflow_id},
            )
            row = result.mappings().first()
        return None if row is None else self._workflow_from_row(row)

    async def find_by_order_for_user(
        self,
        *,
        order_id: str,
        user_id: str,
    ) -> WorkflowRun | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, workflow_type, user_id, user_email, order_id, status,
                        current_step, failed_step, failure_code, last_error,
                        correlation_id, idempotency_key, catalog_item_id, quantity,
                        invoice_document_id, receipt_document_id, payment_id,
                        notification_id, payment_scenario, created_at, updated_at,
                        completed_at
                    FROM workflow_runs
                    WHERE order_id = :order_id
                        AND user_id = :user_id
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"order_id": order_id, "user_id": user_id},
            )
            row = result.mappings().first()
        return None if row is None else self._workflow_from_row(row)

    async def update_workflow(self, workflow_id: str, **updates: object) -> WorkflowRun:
        allowed_columns = {
            "order_id",
            "status",
            "current_step",
            "failed_step",
            "failure_code",
            "last_error",
            "invoice_document_id",
            "receipt_document_id",
            "payment_id",
            "notification_id",
            "payment_scenario",
            "completed_at",
        }
        unknown_columns = set(updates) - allowed_columns
        if unknown_columns:
            raise ValueError(f"Unsupported workflow columns: {unknown_columns}")

        updates["updated_at"] = datetime.now(UTC)
        set_clause = ", ".join(f"{column} = :{column}" for column in updates)
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    f"""
                    UPDATE workflow_runs
                    SET {set_clause}
                    WHERE id = CAST(:workflow_id AS UUID)
                    RETURNING
                        id, workflow_type, user_id, user_email, order_id, status,
                        current_step, failed_step, failure_code, last_error,
                        correlation_id, idempotency_key, catalog_item_id, quantity,
                        invoice_document_id, receipt_document_id, payment_id,
                        notification_id, payment_scenario, created_at, updated_at,
                        completed_at
                    """
                ),
                {"workflow_id": workflow_id, **updates},
            )
            row = result.mappings().first()
            await session.commit()
        if row is None:
            raise LookupError(f"Workflow not found: {workflow_id}")
        return self._workflow_from_row(row)

    async def record_processed_message(
        self,
        *,
        stream_name: str,
        group_name: str,
        consumer_name: str,
        redis_message_id: str,
        message_id: str,
        message_type: str,
        workflow_id: str | None,
        order_id: str | None,
        status: str,
        error: str | None = None,
    ) -> bool:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    INSERT INTO processed_stream_messages (
                        id, stream_name, group_name, consumer_name,
                        redis_message_id, message_id, message_type, workflow_id,
                        order_id, status, error, processed_at
                    )
                    VALUES (
                        :id, :stream_name, :group_name, :consumer_name,
                        :redis_message_id, :message_id, :message_type,
                        CAST(:workflow_id AS UUID), :order_id, :status, :error,
                        :processed_at
                    )
                    ON CONFLICT (
                        stream_name, group_name, consumer_name, redis_message_id
                    ) DO NOTHING
                    RETURNING id
                    """
                ),
                {
                    "id": str(uuid4()),
                    "stream_name": stream_name,
                    "group_name": group_name,
                    "consumer_name": consumer_name,
                    "redis_message_id": redis_message_id,
                    "message_id": message_id,
                    "message_type": message_type,
                    "workflow_id": workflow_id or None,
                    "order_id": order_id or None,
                    "status": status,
                    "error": error,
                    "processed_at": now,
                },
            )
            row = result.first()
            await session.commit()
        return row is not None

    @staticmethod
    def _workflow_from_row(row: Mapping[str, Any]) -> WorkflowRun:
        return WorkflowRun(
            id=str(row["id"]),
            workflow_type=row["workflow_type"],
            user_id=row["user_id"],
            user_email=row["user_email"],
            order_id=row["order_id"],
            status=row["status"],
            current_step=row["current_step"],
            failed_step=row["failed_step"],
            failure_code=row["failure_code"],
            last_error=row["last_error"],
            correlation_id=row["correlation_id"],
            idempotency_key=row["idempotency_key"],
            catalog_item_id=row["catalog_item_id"],
            quantity=row["quantity"],
            invoice_document_id=row["invoice_document_id"],
            receipt_document_id=row["receipt_document_id"],
            payment_id=row["payment_id"],
            notification_id=row["notification_id"],
            payment_scenario=row["payment_scenario"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )
