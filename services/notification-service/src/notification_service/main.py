"""Notification service application entrypoint."""

from typing import Protocol
from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)
from mwp_common.correlation import request_context

from .provider import (
    LocalSmtpNotificationProvider,
    NotificationProviderRequest,
    NotificationProviderResult,
    render_template,
)
from .repository import CreateNotification, Notification, NotificationRepository
from .schemas import CreateNotificationRequest, NotificationResponse

app = create_app("notification-service")


class NotificationStorage(Protocol):
    async def create_notification(
        self,
        notification: CreateNotification,
    ) -> Notification:
        """Create a provider-style notification record."""

    async def find_notification_by_id(
        self,
        notification_id: str,
    ) -> Notification | None:
        """Return one stored notification by id."""


class NotificationProvider(Protocol):
    def send(
        self,
        request: NotificationProviderRequest,
    ) -> NotificationProviderResult:
        """Send a rendered notification through a local provider."""


def get_notification_repository() -> NotificationStorage:
    engine = getattr(app.state, "notification_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.notification_database_engine = engine
        app.state.notification_session_factory = create_async_session_factory(engine)

    return NotificationRepository(app.state.notification_session_factory)


def get_notification_provider() -> NotificationProvider:
    provider = getattr(app.state, "notification_provider", None)
    if provider is None:
        provider = LocalSmtpNotificationProvider()
        app.state.notification_provider = provider

    return provider


def notification_response(notification: Notification) -> NotificationResponse:
    return NotificationResponse(
        id=notification.id,
        order_id=notification.order_id,
        channel=notification.channel,
        status=notification.status,
        recipient=notification.recipient,
        template_key=notification.template_key,
        subject=notification.subject,
        message=notification.message,
        provider=notification.provider,
        provider_reference=notification.provider_reference,
        sent_at=notification.sent_at,
        delivery_attempts=notification.delivery_attempts,
        last_error=notification.last_error,
        created_at=notification.created_at,
        updated_at=notification.updated_at,
    )


def log_notification_event(request: Request, status_value: str) -> None:
    event = "notification.sent" if status_value == "sent" else "notification.failed"
    app.state.logger.info(event, extra=request_context(request))


@app.post(
    "/notifications",
    response_model=NotificationResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["notifications"],
)
async def create_notification(
    request_body: CreateNotificationRequest,
    request: Request,
    provider: NotificationProvider = Depends(get_notification_provider),
    repository: NotificationStorage = Depends(get_notification_repository),
) -> NotificationResponse:
    notification_id = f"notification-{uuid4().hex}"
    rendered = render_template(
        template_key=request_body.template_key,
        order_id=request_body.order_id,
    )
    provider_result = provider.send(
        NotificationProviderRequest(
            notification_id=notification_id,
            order_id=request_body.order_id,
            recipient=request_body.recipient,
            template_key=request_body.template_key,
            subject=rendered.subject,
            message=rendered.message,
        )
    )
    notification = await repository.create_notification(
        CreateNotification(
            id=notification_id,
            order_id=request_body.order_id,
            channel=request_body.channel,
            status=provider_result.status,
            recipient=request_body.recipient,
            template_key=request_body.template_key,
            subject=rendered.subject,
            message=rendered.message,
            provider=provider_result.provider,
            provider_reference=provider_result.provider_reference,
            sent_at=provider_result.sent_at,
            delivery_attempts=provider_result.delivery_attempts,
            last_error=provider_result.last_error,
        )
    )
    log_notification_event(request, notification.status)
    return notification_response(notification)


@app.get(
    "/notifications/{notification_id}",
    response_model=NotificationResponse,
    tags=["notifications"],
)
async def get_notification(
    notification_id: str,
    repository: NotificationStorage = Depends(get_notification_repository),
) -> NotificationResponse:
    notification = await repository.find_notification_by_id(notification_id)
    if notification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )

    return notification_response(notification)


async def dispose_notification_database_engine() -> None:
    engine: AsyncEngine | None = getattr(
        app.state,
        "notification_database_engine",
        None,
    )
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_notification_database_engine)
