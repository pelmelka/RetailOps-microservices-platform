from fastapi.testclient import TestClient

from auth_service.main import app, get_auth_repository
from auth_service.repository import AuthUser, CreateAuthUser
from auth_service.security import create_access_token


LOCAL_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$/mT+uwydb4yZrut/OL2C4Q"
    "$nr2BDN6gP6wecqJCGKcHSmBWjVEs3LFpZItDIdOtdpo"
)


def local_user(is_active: bool = True) -> AuthUser:
    return AuthUser(
        id="user-local-001",
        username="local-user",
        email="local-user@example.test",
        display_name="Local Workflow User",
        password_hash=LOCAL_PASSWORD_HASH,
        is_active=is_active,
    )


class FakeAuthRepository:
    def __init__(self, users: list[AuthUser] | None = None) -> None:
        self.users: dict[str, AuthUser] = {
            user.id: user for user in users or []
        }

    async def create_user(self, user: CreateAuthUser) -> AuthUser:
        user_id = f"user-test-{len(self.users) + 1:03d}"
        created = AuthUser(
            id=user_id,
            username=user.username,
            email=user.email,
            display_name=user.display_name or user.username,
            password_hash=user.password_hash,
            is_active=True,
        )
        self.users[user_id] = created
        return created

    async def find_user_by_username(self, username: str) -> AuthUser | None:
        return next(
            (user for user in self.users.values() if user.username == username),
            None,
        )

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        return next(
            (user for user in self.users.values() if user.email == email),
            None,
        )

    async def find_user_by_id(self, user_id: str) -> AuthUser | None:
        return self.users.get(user_id)


def make_client(repository: FakeAuthRepository | None = None) -> TestClient:
    app.dependency_overrides.clear()
    if repository is not None:
        app.dependency_overrides[get_auth_repository] = lambda: repository
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

    assert response.json()["service"] == "auth-service"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "auth-request-1"},
    )

    assert response.headers["X-Correlation-ID"] == "auth-request-1"



def test_unknown_trace_headers_do_not_break_health_request() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "auth-request-2",
            "X-Request-Source": "smoke-check",
            "X-Debug-Trace-ID": "trace-1",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "auth-request-2"


def test_register_returns_created_user_without_password_hash() -> None:
    client = make_client(FakeAuthRepository())

    response = client.post(
        "/auth/register",
        json={
            "username": "New-User",
            "email": "NEW-USER@example.test",
            "password": "new-password-123",
            "display_name": "New Local User",
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "user_id": "user-test-001",
        "username": "new-user",
        "email": "new-user@example.test",
        "display_name": "New Local User",
        "is_active": True,
    }
    assert "password" not in response.json()
    assert "password_hash" not in response.json()


def test_register_returns_409_for_duplicate_username() -> None:
    client = make_client(FakeAuthRepository([local_user()]))

    response = client.post(
        "/auth/register",
        json={
            "username": "local-user",
            "email": "another-local-user@example.test",
            "password": "new-password-123",
            "display_name": "Duplicate Username",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}


def test_register_returns_409_for_duplicate_email() -> None:
    client = make_client(FakeAuthRepository([local_user()]))

    response = client.post(
        "/auth/register",
        json={
            "username": "another-local-user",
            "email": "local-user@example.test",
            "password": "new-password-123",
            "display_name": "Duplicate Email",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Email already exists"}


def test_register_rejects_invalid_email() -> None:
    client = make_client(FakeAuthRepository())

    response = client.post(
        "/auth/register",
        json={
            "username": "new-user",
            "email": "not-an-email",
            "password": "new-password-123",
        },
    )

    assert response.status_code == 422


def test_register_rejects_short_password() -> None:
    client = make_client(FakeAuthRepository())

    response = client.post(
        "/auth/register",
        json={
            "username": "new-user",
            "email": "new-user@example.test",
            "password": "short",
        },
    )

    assert response.status_code == 422


def test_login_returns_signed_access_token_and_user_context() -> None:
    client = make_client(FakeAuthRepository([local_user()]))

    response = client.post(
        "/auth/login",
        json={"username": "local-user", "password": "local-password"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["user_id"] == "user-local-001"
    assert payload["username"] == "local-user"
    assert payload["email"] == "local-user@example.test"
    assert payload["display_name"] == "Local Workflow User"
    assert payload["token_type"] == "bearer"
    assert payload["expires_in"] == 3600
    assert payload["access_token"].count(".") == 2


def test_login_rejects_invalid_password() -> None:
    client = make_client(FakeAuthRepository([local_user()]))

    response = client.post(
        "/auth/login",
        json={"username": "local-user", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_login_rejects_unknown_user() -> None:
    client = make_client(FakeAuthRepository())

    response = client.post(
        "/auth/login",
        json={"username": "missing-user", "password": "local-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_inactive_user_cannot_login() -> None:
    client = make_client(FakeAuthRepository([local_user(is_active=False)]))

    response = client.post(
        "/auth/login",
        json={"username": "local-user", "password": "local-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_login_rejects_user_without_password_hash() -> None:
    user = AuthUser(
        id="user-local-001",
        username="local-user",
        email="local-user@example.test",
        display_name="Local Workflow User",
        password_hash=None,
        is_active=True,
    )
    client = make_client(FakeAuthRepository([user]))

    response = client.post(
        "/auth/login",
        json={"username": "local-user", "password": "local-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid username or password"}


def test_login_validation_errors_use_fastapi_defaults() -> None:
    client = make_client(FakeAuthRepository())

    response = client.post("/auth/login", json={"username": "local-user"})

    assert response.status_code == 422


def test_me_returns_current_user_for_valid_token() -> None:
    repository = FakeAuthRepository([local_user()])
    token = create_access_token(user_id="user-local-001", username="local-user")
    client = make_client(repository)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token.value}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "user-local-001",
        "username": "local-user",
        "email": "local-user@example.test",
        "display_name": "Local Workflow User",
        "is_active": True,
    }


def test_me_returns_401_without_token() -> None:
    client = make_client(FakeAuthRepository([local_user()]))

    response = client.get("/auth/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing bearer token"}


def test_me_returns_401_for_invalid_token() -> None:
    client = make_client(FakeAuthRepository([local_user()]))

    response = client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid-token"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}


def test_me_returns_401_for_inactive_token_user() -> None:
    repository = FakeAuthRepository([local_user(is_active=False)])
    token = create_access_token(user_id="user-local-001", username="local-user")
    client = make_client(repository)

    response = client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {token.value}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid authentication credentials"}
