from datetime import UTC, datetime

from fastapi.testclient import TestClient

from notification_service.main import (
    app,
    get_notification_provider,
    get_notification_repository,
)
from notification_service.provider import (
    LOCAL_SMTP_PROVIDER,
    NOTIFICATION_STATUS_SENT,
    NotificationProviderRequest,
    NotificationProviderResult,
    render_template,
)
from notification_service.repository import CreateNotification, Notification


NOTIFICATION_CREATED_AT = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)


class FakeNotificationProvider:
    def send(
        self,
        request: NotificationProviderRequest,
    ) -> NotificationProviderResult:
        return NotificationProviderResult(
            status=NOTIFICATION_STATUS_SENT,
            provider=LOCAL_SMTP_PROVIDER,
            provider_reference="local-mail-test-001",
            sent_at=NOTIFICATION_CREATED_AT,
            delivery_attempts=1,
            last_error=None,
        )


class FakeNotificationRepository:
    def __init__(self) -> None:
        self.notifications: dict[str, Notification] = {}

    async def create_notification(
        self,
        notification: CreateNotification,
    ) -> Notification:
        created = Notification(
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
            created_at=NOTIFICATION_CREATED_AT,
            updated_at=NOTIFICATION_CREATED_AT,
        )
        self.notifications[notification.id] = created
        return created

    async def find_notification_by_id(
        self,
        notification_id: str,
    ) -> Notification | None:
        return self.notifications.get(notification_id)


def make_client(
    repository: FakeNotificationRepository | None = None,
    provider: FakeNotificationProvider | None = None,
) -> TestClient:
    app.dependency_overrides.clear()
    if repository is not None:
        app.dependency_overrides[get_notification_repository] = lambda: repository
    if provider is not None:
        app.dependency_overrides[get_notification_provider] = lambda: provider
    return TestClient(app)


def test_health_returns_200() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.status_code == 200


def test_ready_returns_200() -> None:
    client = make_client()

    response = client.get("/ready")

    assert response.status_code == 200


def test_health_response_includes_service_name() -> None:
    client = make_client()

    response = client.get("/health")

    assert response.json()["service"] == "notification-service"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "notification-request-1"},
    )

    assert response.headers["X-Correlation-ID"] == "notification-request-1"


def test_trace_headers_do_not_break_health_request() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "notification-request-2",
            "X-Debug-Trace-ID": "future-run",
            "X-Request-Source": "future-scenario",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "notification-request-2"


def test_render_template_returns_subject_and_message() -> None:
    rendered = render_template(
        template_key="payment_completed",
        order_id="order-local-check",
    )

    assert rendered.subject == "Local workflow payment completed"
    assert "order-local-check" in rendered.message


def test_create_notification_renders_template_and_returns_sent_status() -> None:
    repository = FakeNotificationRepository()
    client = make_client(repository, FakeNotificationProvider())

    response = client.post(
        "/notifications",
        json={
            "order_id": "order-local-check",
            "channel": "email",
            "recipient": "local-user@example.test",
            "template_key": "payment_completed",
        },
    )

    assert response.status_code == 201
    assert response.json()["status"] == NOTIFICATION_STATUS_SENT
    assert response.json()["template_key"] == "payment_completed"
    assert response.json()["subject"] == "Local workflow payment completed"
    assert response.json()["provider"] == LOCAL_SMTP_PROVIDER
    assert response.json()["provider_reference"] == "local-mail-test-001"
    assert response.json()["delivery_attempts"] == 1


def test_create_notification_rejects_invalid_template_key() -> None:
    client = make_client(FakeNotificationRepository(), FakeNotificationProvider())

    response = client.post(
        "/notifications",
        json={
            "order_id": "order-local-check",
            "channel": "email",
            "recipient": "local-user@example.test",
            "template_key": "unknown_template",
        },
    )

    assert response.status_code == 422


def test_get_notification_returns_stored_notification() -> None:
    repository = FakeNotificationRepository()
    repository.notifications["notification-test-001"] = Notification(
        id="notification-test-001",
        order_id="order-local-check",
        channel="email",
        status=NOTIFICATION_STATUS_SENT,
        recipient="local-user@example.test",
        template_key="payment_completed",
        subject="Local workflow payment completed",
        message="Local workflow payment completed for order order-local-check.",
        provider=LOCAL_SMTP_PROVIDER,
        provider_reference="local-mail-test-001",
        sent_at=NOTIFICATION_CREATED_AT,
        delivery_attempts=1,
        last_error=None,
        created_at=NOTIFICATION_CREATED_AT,
        updated_at=NOTIFICATION_CREATED_AT,
    )
    client = make_client(repository)

    response = client.get("/notifications/notification-test-001")

    assert response.status_code == 200
    assert response.json()["id"] == "notification-test-001"
    assert response.json()["provider_reference"] == "local-mail-test-001"


def test_get_notification_returns_404_for_missing_notification() -> None:
    client = make_client(FakeNotificationRepository())

    response = client.get("/notifications/not-existing-notification")

    assert response.status_code == 404
    assert response.json() == {"detail": "Notification not found"}
