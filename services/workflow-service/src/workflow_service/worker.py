"""Redis Streams worker for the order checkout saga."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from mwp_common import CORRELATION_ID_HEADER, RedisStreamsClient, StreamMessage
from mwp_common.workflow_contracts import (
    COMMAND_DOCUMENT_GENERATE_INVOICE,
    COMMAND_DOCUMENT_GENERATE_RECEIPT,
    COMMAND_NOTIFICATION_SEND,
    COMMAND_ORDER_CREATE,
    COMMAND_PAYMENT_PROCESS,
    COMMAND_PAYMENT_REQUESTED,
    COMMAND_WORKFLOW_MARK_FAILED,
    EVENT_DOCUMENT_INVOICE_GENERATED,
    EVENT_DOCUMENT_RECEIPT_GENERATED,
    EVENT_NOTIFICATION_FAILED,
    EVENT_NOTIFICATION_SENT,
    EVENT_ORDER_CREATED,
    EVENT_PAYMENT_COMPLETED,
    EVENT_PAYMENT_FAILED,
    EVENT_WORKFLOW_AWAITING_PAYMENT,
    EVENT_WORKFLOW_COMPLETED,
    EVENT_WORKFLOW_FAILED,
    WORKFLOW_COMMANDS_GROUP,
    WORKFLOW_COMMANDS_STREAM,
    WORKFLOW_DEAD_LETTER_STREAM,
    WORKFLOW_EVENTS_GROUP,
    WORKFLOW_EVENTS_STREAM,
    command_fields,
    event_fields,
)

from .repository import (
    STATUS_AWAITING_PAYMENT,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_INVOICE_GENERATING,
    STATUS_NOTIFICATION_FAILED,
    STATUS_NOTIFICATION_SENDING,
    STATUS_ORDER_CREATING,
    STATUS_PAYMENT_PROCESSING,
    STATUS_PAYMENT_REQUESTED,
    STATUS_RECEIPT_GENERATING,
    WorkflowRepository,
    WorkflowRun,
)
from .upstream import WorkflowUpstreamClient


PAYMENT_FAILURE_RETRYABLE = {
    "INSUFFICIENT_FUNDS",
    "PROVIDER_UNAVAILABLE",
}


class WorkflowProcessor:
    def __init__(
        self,
        *,
        repository: WorkflowRepository,
        redis: RedisStreamsClient,
        upstream: WorkflowUpstreamClient,
        consumer_name: str,
        logger: logging.Logger,
    ) -> None:
        self._repository = repository
        self._redis = redis
        self._upstream = upstream
        self._consumer_name = consumer_name
        self._logger = logger

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self._ensure_groups()
                await self._run_once(stop_event)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("workflow.worker.loop_error")
                try:
                    await self._redis.close()
                finally:
                    await self._sleep(stop_event, 2.0)

    async def _ensure_groups(self) -> None:
        await self._redis.xgroup_create(WORKFLOW_COMMANDS_STREAM, WORKFLOW_COMMANDS_GROUP)
        await self._redis.xgroup_create(WORKFLOW_EVENTS_STREAM, WORKFLOW_EVENTS_GROUP)

    async def _run_once(self, stop_event: asyncio.Event) -> None:
        command_messages = await self._redis.xreadgroup(
            stream=WORKFLOW_COMMANDS_STREAM,
            group=WORKFLOW_COMMANDS_GROUP,
            consumer=self._consumer_name,
            count=10,
            block_ms=500,
        )
        for message in command_messages:
            await self._process_message(
                message,
                group_name=WORKFLOW_COMMANDS_GROUP,
                handler=self._handle_command,
            )

        event_messages = await self._redis.xreadgroup(
            stream=WORKFLOW_EVENTS_STREAM,
            group=WORKFLOW_EVENTS_GROUP,
            consumer=self._consumer_name,
            count=10,
            block_ms=100,
        )
        for message in event_messages:
            await self._process_message(
                message,
                group_name=WORKFLOW_EVENTS_GROUP,
                handler=self._handle_event,
            )

        if not command_messages and not event_messages:
            await self._sleep(stop_event, 0.1)

    async def _process_message(
        self,
        message: StreamMessage,
        *,
        group_name: str,
        handler: Any,
    ) -> None:
        message_type = message.fields.get("message_type", "")
        workflow_id = message.fields.get("workflow_id") or None
        order_id = message.fields.get("order_id") or None
        processed_status = "processed"
        error: str | None = None
        try:
            await handler(message)
        except Exception as exc:
            processed_status = "failed"
            error = str(exc)
            await self._publish_dead_letter(message, error)
            if workflow_id:
                await self._mark_failed(
                    workflow_id=workflow_id,
                    correlation_id=message.fields.get("correlation_id", ""),
                    failed_step=message_type or "unknown",
                    failure_code="WORKFLOW_WORKER_ERROR",
                    last_error=error,
                    causation_id=message.fields.get("message_id"),
                )
            self._logger.exception(
                "workflow.message.failed",
                extra={
                    "workflow_id": workflow_id,
                    "order_id": order_id,
                    "message_type": message_type,
                    "redis_message_id": message.message_id,
                },
            )
        finally:
            inserted = await self._repository.record_processed_message(
                stream_name=message.stream,
                group_name=group_name,
                consumer_name=self._consumer_name,
                redis_message_id=message.message_id,
                message_id=message.fields.get("message_id", ""),
                message_type=message_type,
                workflow_id=workflow_id,
                order_id=order_id,
                status=processed_status,
                error=error,
            )
            if inserted:
                await self._redis.xack(message.stream, group_name, message.message_id)

    async def _handle_event(self, message: StreamMessage) -> None:
        self._logger.info(
            "workflow.event.observed",
            extra={
                "workflow_id": message.fields.get("workflow_id"),
                "order_id": message.fields.get("order_id"),
                "message_type": message.fields.get("message_type"),
            },
        )

    async def _handle_command(self, message: StreamMessage) -> None:
        message_type = message.fields.get("message_type")
        if message_type == COMMAND_ORDER_CREATE:
            await self._handle_order_create(message)
            return
        if message_type == COMMAND_DOCUMENT_GENERATE_INVOICE:
            await self._handle_generate_invoice(message)
            return
        if message_type == COMMAND_PAYMENT_REQUESTED:
            await self._handle_payment_requested(message)
            return
        if message_type == COMMAND_PAYMENT_PROCESS:
            await self._handle_payment_process(message)
            return
        if message_type == COMMAND_DOCUMENT_GENERATE_RECEIPT:
            await self._handle_generate_receipt(message)
            return
        if message_type == COMMAND_NOTIFICATION_SEND:
            await self._handle_notification_send(message)
            return
        if message_type == COMMAND_WORKFLOW_MARK_FAILED:
            await self._mark_failed(
                workflow_id=message.fields["workflow_id"],
                correlation_id=message.fields.get("correlation_id", ""),
                failed_step=message.fields.get("failed_step") or "manual",
                failure_code=message.fields.get("failure_code") or "WORKFLOW_FAILED",
                last_error=message.fields.get("last_error") or "Workflow marked failed",
                causation_id=message.fields.get("message_id"),
            )
            return
        raise ValueError(f"Unsupported command type: {message_type}")

    async def _handle_order_create(self, message: StreamMessage) -> None:
        fields = message.fields
        workflow = await self._require_workflow(fields["workflow_id"])
        await self._repository.update_workflow(
            workflow.id,
            status=STATUS_ORDER_CREATING,
            current_step=STATUS_ORDER_CREATING,
        )
        catalog_item = await self._call_json(
            "GET",
            "catalog",
            f"/catalog/items/{workflow.catalog_item_id}",
            correlation_id=workflow.correlation_id,
            expected_statuses={200},
        )
        unit_price_kopecks = catalog_item["price_kopecks"]
        quantity = workflow.quantity or 1
        order = await self._call_json(
            "POST",
            "order",
            "/orders",
            json={
                "user_id": workflow.user_id,
                "catalog_item_id": workflow.catalog_item_id,
                "quantity": quantity,
                "unit_price_kopecks": unit_price_kopecks,
                "total_kopecks": quantity * unit_price_kopecks,
                "currency": catalog_item["currency"],
            },
            correlation_id=workflow.correlation_id,
            expected_statuses={200, 201},
        )
        workflow = await self._repository.update_workflow(
            workflow.id,
            order_id=order["id"],
            status=STATUS_INVOICE_GENERATING,
            current_step=STATUS_INVOICE_GENERATING,
        )
        await self._publish_event(
            EVENT_ORDER_CREATED,
            workflow=workflow,
            causation_id=fields.get("message_id"),
            order_id=order["id"],
            user_id=workflow.user_id,
        )
        await self._publish_command(
            COMMAND_DOCUMENT_GENERATE_INVOICE,
            workflow=workflow,
            causation_id=fields.get("message_id"),
            order_id=order["id"],
            user_id=workflow.user_id,
        )

    async def _handle_generate_invoice(self, message: StreamMessage) -> None:
        workflow = await self._require_workflow(message.fields["workflow_id"])
        if not workflow.order_id:
            raise ValueError("Workflow has no order_id for invoice generation")
        await self._repository.update_workflow(
            workflow.id,
            status=STATUS_INVOICE_GENERATING,
            current_step=STATUS_INVOICE_GENERATING,
        )
        document = await self._call_json(
            "POST",
            "document",
            "/documents/invoice",
            json={"order_id": workflow.order_id},
            correlation_id=workflow.correlation_id,
            expected_statuses={201},
        )
        await self._transition_order(
            workflow.order_id,
            "invoice_generated",
            "Invoice PDF generated by async workflow",
            correlation_id=workflow.correlation_id,
        )
        workflow = await self._repository.update_workflow(
            workflow.id,
            status=STATUS_AWAITING_PAYMENT,
            current_step=STATUS_AWAITING_PAYMENT,
            invoice_document_id=document["id"],
            failed_step=None,
            failure_code=None,
            last_error=None,
        )
        await self._publish_event(
            EVENT_DOCUMENT_INVOICE_GENERATED,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
            document_id=document["id"],
        )
        await self._publish_event(
            EVENT_WORKFLOW_AWAITING_PAYMENT,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
        )

    async def _handle_payment_requested(self, message: StreamMessage) -> None:
        workflow = await self._require_workflow(message.fields["workflow_id"])
        scenario = message.fields.get("payment_scenario") or "success"
        workflow = await self._repository.update_workflow(
            workflow.id,
            status=STATUS_PAYMENT_REQUESTED,
            current_step=STATUS_PAYMENT_REQUESTED,
            payment_scenario=scenario,
            failed_step=None,
            failure_code=None,
            last_error=None,
        )
        await self._publish_command(
            COMMAND_PAYMENT_PROCESS,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
            user_id=workflow.user_id,
            payment_scenario=scenario,
        )

    async def _handle_payment_process(self, message: StreamMessage) -> None:
        workflow = await self._require_workflow(message.fields["workflow_id"])
        if not workflow.order_id:
            raise ValueError("Workflow has no order_id for payment")
        order = await self._call_json(
            "GET",
            "order",
            f"/orders/{workflow.order_id}",
            correlation_id=workflow.correlation_id,
            expected_statuses={200},
        )
        scenario = message.fields.get("payment_scenario") or "success"
        workflow = await self._repository.update_workflow(
            workflow.id,
            status=STATUS_PAYMENT_PROCESSING,
            current_step=STATUS_PAYMENT_PROCESSING,
            payment_scenario=scenario,
        )
        payment = await self._call_json(
            "POST",
            "payment",
            "/payments",
            json={
                "order_id": workflow.order_id,
                "amount_kopecks": order["total_kopecks"],
                "currency": order["currency"],
                "payment_method": "card",
                "mock_scenario": scenario,
            },
            correlation_id=workflow.correlation_id,
            expected_statuses={201},
        )
        if payment.get("status") == "completed":
            await self._handle_payment_completed(message, workflow, payment)
            return
        await self._handle_payment_failed(message, workflow, payment)

    async def _handle_payment_completed(
        self,
        message: StreamMessage,
        workflow: WorkflowRun,
        payment: dict[str, Any],
    ) -> None:
        assert workflow.order_id is not None
        await self._transition_order(
            workflow.order_id,
            "payment_completed",
            "Local payment simulation completed",
            correlation_id=workflow.correlation_id,
        )
        workflow = await self._repository.update_workflow(
            workflow.id,
            status=STATUS_RECEIPT_GENERATING,
            current_step=STATUS_RECEIPT_GENERATING,
            payment_id=payment["id"],
            failed_step=None,
            failure_code=None,
            last_error=None,
        )
        await self._publish_event(
            EVENT_PAYMENT_COMPLETED,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
            payment_id=payment["id"],
        )
        await self._publish_command(
            COMMAND_DOCUMENT_GENERATE_RECEIPT,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
        )

    async def _handle_payment_failed(
        self,
        message: StreamMessage,
        workflow: WorkflowRun,
        payment: dict[str, Any],
    ) -> None:
        assert workflow.order_id is not None
        failure_code = payment.get("failure_code") or "PAYMENT_FAILED"
        await self._transition_order(
            workflow.order_id,
            "payment_failed",
            f"Local payment simulation failed: {failure_code}",
            correlation_id=workflow.correlation_id,
        )
        await self._publish_event(
            EVENT_PAYMENT_FAILED,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
            payment_id=payment["id"],
            failure_code=failure_code,
        )
        if failure_code in PAYMENT_FAILURE_RETRYABLE:
            await self._repository.update_workflow(
                workflow.id,
                status=STATUS_AWAITING_PAYMENT,
                current_step="payment_failed",
                payment_id=payment["id"],
                failed_step="payment",
                failure_code=failure_code,
                last_error=payment.get("failure_reason"),
            )
            return
        await self._mark_failed(
            workflow_id=workflow.id,
            correlation_id=workflow.correlation_id,
            failed_step="payment",
            failure_code=failure_code,
            last_error=payment.get("failure_reason") or "Payment was rejected",
            causation_id=message.fields.get("message_id"),
        )

    async def _handle_generate_receipt(self, message: StreamMessage) -> None:
        workflow = await self._require_workflow(message.fields["workflow_id"])
        if not workflow.order_id:
            raise ValueError("Workflow has no order_id for receipt generation")
        document = await self._call_json(
            "POST",
            "document",
            "/documents/receipt",
            json={"order_id": workflow.order_id},
            correlation_id=workflow.correlation_id,
            expected_statuses={201},
        )
        await self._transition_order(
            workflow.order_id,
            "receipt_generated",
            "Receipt PDF generated by async workflow",
            correlation_id=workflow.correlation_id,
        )
        workflow = await self._repository.update_workflow(
            workflow.id,
            status=STATUS_NOTIFICATION_SENDING,
            current_step=STATUS_NOTIFICATION_SENDING,
            receipt_document_id=document["id"],
        )
        await self._publish_event(
            EVENT_DOCUMENT_RECEIPT_GENERATED,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
            document_id=document["id"],
        )
        await self._publish_command(
            COMMAND_NOTIFICATION_SEND,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
        )

    async def _handle_notification_send(self, message: StreamMessage) -> None:
        workflow = await self._require_workflow(message.fields["workflow_id"])
        if not workflow.order_id:
            raise ValueError("Workflow has no order_id for notification")
        notification = await self._call_json(
            "POST",
            "notification",
            "/notifications",
            json={
                "order_id": workflow.order_id,
                "channel": "email",
                "recipient": workflow.user_email or f"{workflow.user_id}@example.test",
                "template_key": "workflow_completed",
            },
            correlation_id=workflow.correlation_id,
            expected_statuses={201},
        )
        if notification.get("status") == "sent":
            await self._transition_order(
                workflow.order_id,
                "notification_sent",
                "Workflow notification sent",
                correlation_id=workflow.correlation_id,
            )
            workflow = await self._repository.update_workflow(
                workflow.id,
                status=STATUS_COMPLETED,
                current_step=STATUS_COMPLETED,
                notification_id=notification["id"],
                completed_at=datetime.now(UTC),
            )
            await self._publish_event(
                EVENT_NOTIFICATION_SENT,
                workflow=workflow,
                causation_id=message.fields.get("message_id"),
                order_id=workflow.order_id,
                notification_id=notification["id"],
            )
            await self._publish_event(
                EVENT_WORKFLOW_COMPLETED,
                workflow=workflow,
                causation_id=message.fields.get("message_id"),
                order_id=workflow.order_id,
            )
            return

        workflow = await self._repository.update_workflow(
            workflow.id,
            status=STATUS_NOTIFICATION_FAILED,
            current_step=STATUS_NOTIFICATION_FAILED,
            notification_id=notification["id"],
            failed_step="notification",
            failure_code="NOTIFICATION_FAILED",
            last_error=notification.get("last_error") or "Notification failed",
        )
        await self._publish_event(
            EVENT_NOTIFICATION_FAILED,
            workflow=workflow,
            causation_id=message.fields.get("message_id"),
            order_id=workflow.order_id,
            notification_id=notification["id"],
            failure_code="NOTIFICATION_FAILED",
        )

    async def _mark_failed(
        self,
        *,
        workflow_id: str,
        correlation_id: str,
        failed_step: str,
        failure_code: str,
        last_error: str,
        causation_id: str | None,
    ) -> None:
        workflow = await self._repository.update_workflow(
            workflow_id,
            status=STATUS_FAILED,
            current_step=STATUS_FAILED,
            failed_step=failed_step,
            failure_code=failure_code,
            last_error=last_error,
            completed_at=datetime.now(UTC),
        )
        await self._publish_event(
            EVENT_WORKFLOW_FAILED,
            workflow=workflow,
            causation_id=causation_id,
            order_id=workflow.order_id,
            failure_code=failure_code,
        )

    async def _require_workflow(self, workflow_id: str) -> WorkflowRun:
        workflow = await self._repository.find_by_id(workflow_id)
        if workflow is None:
            raise LookupError(f"Workflow not found: {workflow_id}")
        return workflow

    async def _transition_order(
        self,
        order_id: str,
        next_status: str,
        reason: str,
        *,
        correlation_id: str,
    ) -> dict[str, Any]:
        return await self._call_json(
            "POST",
            "order",
            f"/orders/{order_id}/transitions",
            json={"status": next_status, "reason": reason},
            correlation_id=correlation_id,
            expected_statuses={200},
        )

    async def _call_json(
        self,
        method: str,
        service: str,
        path: str,
        *,
        correlation_id: str,
        expected_statuses: set[int],
        json: Any | None = None,
    ) -> Any:
        response = await self._upstream.request(
            method,
            service,
            path,
            json=json,
            headers={CORRELATION_ID_HEADER: correlation_id},
        )
        if response.status_code not in expected_statuses:
            raise RuntimeError(
                f"{service} {method} {path} returned {response.status_code}: "
                f"{response.body}"
            )
        return response.body

    async def _publish_command(
        self,
        message_type: str,
        *,
        workflow: WorkflowRun,
        causation_id: str | None,
        **fields: object,
    ) -> str:
        return await self._redis.xadd(
            WORKFLOW_COMMANDS_STREAM,
            command_fields(
                message_type=message_type,
                workflow_id=workflow.id,
                correlation_id=workflow.correlation_id,
                causation_id=causation_id,
                **fields,
            ),
        )

    async def _publish_event(
        self,
        message_type: str,
        *,
        workflow: WorkflowRun,
        causation_id: str | None,
        **fields: object,
    ) -> str:
        return await self._redis.xadd(
            WORKFLOW_EVENTS_STREAM,
            event_fields(
                message_type=message_type,
                workflow_id=workflow.id,
                correlation_id=workflow.correlation_id,
                causation_id=causation_id,
                **fields,
            ),
        )

    async def _publish_dead_letter(self, message: StreamMessage, error: str) -> None:
        fields = {
            **message.fields,
            "source_stream": message.stream,
            "source_redis_message_id": message.message_id,
            "dead_letter_error": error,
            "dead_letter_at": datetime.now(UTC).isoformat(),
        }
        await self._redis.xadd(WORKFLOW_DEAD_LETTER_STREAM, fields)

    @staticmethod
    async def _sleep(stop_event: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=seconds)
        except TimeoutError:
            return
