"""Workflow service application entrypoint."""

from __future__ import annotations

import asyncio
from typing import Protocol

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    RedisStreamsClient,
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)
from mwp_common.workflow_contracts import (
    COMMAND_ORDER_CREATE,
    COMMAND_PAYMENT_REQUESTED,
    WORKFLOW_COMMANDS_STREAM,
    command_fields,
)

from .config import WorkflowConfig, get_workflow_config
from .repository import (
    STATUS_AWAITING_PAYMENT,
    STATUS_COMPLETED,
    STATUS_FAILED,
    CreateWorkflowRun,
    WorkflowRepository,
    WorkflowRun,
)
from .schemas import (
    RequestPaymentRequest,
    StartOrderWorkflowRequest,
    WorkflowAcceptedResponse,
    WorkflowRunResponse,
)
from .upstream import WorkflowUpstreamClient
from .worker import WorkflowProcessor


app = create_app("workflow-service")


class WorkflowStorage(Protocol):
    async def create_workflow_run(self, request: CreateWorkflowRun) -> WorkflowRun:
        """Create a workflow run."""

    async def find_by_idempotency_key(
        self,
        *,
        user_id: str,
        idempotency_key: str | None,
    ) -> WorkflowRun | None:
        """Find a workflow run by external idempotency key."""

    async def find_by_id(self, workflow_id: str) -> WorkflowRun | None:
        """Find one workflow run."""

    async def find_by_order_for_user(
        self,
        *,
        order_id: str,
        user_id: str,
    ) -> WorkflowRun | None:
        """Find the checkout workflow for an order/user pair."""


def get_repository() -> WorkflowStorage:
    engine = getattr(app.state, "workflow_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.workflow_database_engine = engine
        app.state.workflow_session_factory = create_async_session_factory(engine)
    return WorkflowRepository(app.state.workflow_session_factory)


def workflow_response(workflow: WorkflowRun) -> WorkflowRunResponse:
    return WorkflowRunResponse(
        id=workflow.id,
        workflow_type=workflow.workflow_type,
        user_id=workflow.user_id,
        user_email=workflow.user_email,
        order_id=workflow.order_id,
        status=workflow.status,
        current_step=workflow.current_step,
        failed_step=workflow.failed_step,
        failure_code=workflow.failure_code,
        last_error=workflow.last_error,
        correlation_id=workflow.correlation_id,
        idempotency_key=workflow.idempotency_key,
        invoice_document_id=workflow.invoice_document_id,
        receipt_document_id=workflow.receipt_document_id,
        payment_id=workflow.payment_id,
        notification_id=workflow.notification_id,
        payment_scenario=workflow.payment_scenario,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        completed_at=workflow.completed_at,
    )


async def publish_command(redis_url: str, fields: dict[str, str]) -> None:
    redis = RedisStreamsClient(redis_url)
    try:
        await redis.xadd(WORKFLOW_COMMANDS_STREAM, fields)
    finally:
        await redis.close()


@app.post(
    "/workflows/order-checkout",
    response_model=WorkflowAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def start_order_checkout_workflow(
    request_body: StartOrderWorkflowRequest,
    repository: WorkflowStorage = Depends(get_repository),
) -> WorkflowAcceptedResponse:
    config = get_workflow_config()
    existing = await repository.find_by_idempotency_key(
        user_id=request_body.user_id,
        idempotency_key=request_body.idempotency_key,
    )
    workflow = existing or await repository.create_workflow_run(
        CreateWorkflowRun(
            user_id=request_body.user_id,
            user_email=request_body.user_email,
            catalog_item_id=request_body.catalog_item_id,
            quantity=request_body.quantity,
            correlation_id=request_body.correlation_id,
            idempotency_key=request_body.idempotency_key,
        )
    )
    if existing is None:
        await publish_command(
            config.redis_url,
            command_fields(
                message_type=COMMAND_ORDER_CREATE,
                workflow_id=workflow.id,
                correlation_id=workflow.correlation_id,
                user_id=workflow.user_id,
                catalog_item_id=workflow.catalog_item_id,
                quantity=workflow.quantity,
            ),
        )
    return WorkflowAcceptedResponse(
        workflow_id=workflow.id,
        status=workflow.status,
        correlation_id=workflow.correlation_id,
        order_id=workflow.order_id,
    )


@app.post(
    "/workflows/orders/{order_id}/payments",
    response_model=WorkflowAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["workflows"],
)
async def request_order_payment(
    order_id: str,
    request_body: RequestPaymentRequest,
    repository: WorkflowStorage = Depends(get_repository),
) -> WorkflowAcceptedResponse:
    config = get_workflow_config()
    workflow = await repository.find_by_order_for_user(
        order_id=order_id,
        user_id=request_body.user_id,
    )
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    if workflow.status in {STATUS_COMPLETED, STATUS_FAILED}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow is already terminal",
        )
    if workflow.status != STATUS_AWAITING_PAYMENT:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workflow is not awaiting payment",
        )
    await publish_command(
        config.redis_url,
        command_fields(
            message_type=COMMAND_PAYMENT_REQUESTED,
            workflow_id=workflow.id,
            correlation_id=request_body.correlation_id,
            user_id=workflow.user_id,
            order_id=workflow.order_id,
            payment_scenario=request_body.payment_scenario,
            idempotency_key=request_body.idempotency_key,
        ),
    )
    return WorkflowAcceptedResponse(
        workflow_id=workflow.id,
        status=workflow.status,
        correlation_id=workflow.correlation_id,
        order_id=workflow.order_id,
    )


@app.get(
    "/workflows/orders/{order_id}",
    response_model=WorkflowRunResponse,
    tags=["workflows"],
)
async def get_order_workflow(
    order_id: str,
    user_id: str,
    repository: WorkflowStorage = Depends(get_repository),
) -> WorkflowRunResponse:
    workflow = await repository.find_by_order_for_user(
        order_id=order_id,
        user_id=user_id,
    )
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    return workflow_response(workflow)


@app.get(
    "/workflows/{workflow_id}",
    response_model=WorkflowRunResponse,
    tags=["workflows"],
)
async def get_workflow(
    workflow_id: str,
    repository: WorkflowStorage = Depends(get_repository),
) -> WorkflowRunResponse:
    workflow = await repository.find_by_id(workflow_id)
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )
    return workflow_response(workflow)


async def start_background_worker() -> None:
    config: WorkflowConfig = get_workflow_config()
    if not config.worker_enabled:
        app.state.logger.info("workflow.worker.disabled")
        return
    worker_engine = create_async_database_engine_from_config()
    repository = WorkflowRepository(create_async_session_factory(worker_engine))
    redis = RedisStreamsClient(config.redis_url)
    upstream = WorkflowUpstreamClient(config)
    stop_event = asyncio.Event()
    processor = WorkflowProcessor(
        repository=repository,
        redis=redis,
        upstream=upstream,
        consumer_name=config.worker_consumer_name,
        logger=app.state.logger,
    )
    app.state.workflow_worker_stop_event = stop_event
    app.state.workflow_worker_redis = redis
    app.state.workflow_worker_task = asyncio.create_task(processor.run(stop_event))
    app.state.workflow_worker_repository = repository
    app.state.workflow_worker_database_engine = worker_engine


async def stop_background_worker() -> None:
    stop_event: asyncio.Event | None = getattr(
        app.state,
        "workflow_worker_stop_event",
        None,
    )
    task: asyncio.Task | None = getattr(app.state, "workflow_worker_task", None)
    redis: RedisStreamsClient | None = getattr(app.state, "workflow_worker_redis", None)
    if stop_event is not None:
        stop_event.set()
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    if redis is not None:
        await redis.close()


async def dispose_workflow_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "workflow_database_engine", None)
    if engine is not None:
        await engine.dispose()
    worker_engine: AsyncEngine | None = getattr(
        app.state,
        "workflow_worker_database_engine",
        None,
    )
    if worker_engine is not None:
        await worker_engine.dispose()


app.router.on_startup.append(start_background_worker)
app.router.on_shutdown.append(stop_background_worker)
app.router.on_shutdown.append(dispose_workflow_database_engine)
