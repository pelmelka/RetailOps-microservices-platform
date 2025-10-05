"""Auth service application entrypoint."""

from typing import Protocol

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)
from mwp_common.correlation import request_context

from .repository import (
    AuthUser,
    AuthUserRepository,
    CreateAuthUser,
    DuplicateAuthUserError,
)
from .schemas import AuthUserResponse, LoginRequest, LoginResponse, RegisterRequest
from .security import (
    ACCESS_TOKEN_TYPE,
    InvalidAccessTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

app = create_app("auth-service")


class AuthRepository(Protocol):
    async def create_user(self, user: CreateAuthUser) -> AuthUser:
        """Create a new active auth user."""

    async def find_user_by_username(self, username: str) -> AuthUser | None:
        """Return an auth user by username."""

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        """Return an auth user by email."""

    async def find_user_by_id(self, user_id: str) -> AuthUser | None:
        """Return an auth user by id."""


def get_auth_repository() -> AuthRepository:
    engine = getattr(app.state, "auth_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.auth_database_engine = engine
        app.state.auth_session_factory = create_async_session_factory(engine)

    return AuthUserRepository(app.state.auth_session_factory)


def user_response(user: AuthUser) -> AuthUserResponse:
    return AuthUserResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
    )


def log_auth_event(request: Request, event: str) -> None:
    app.state.logger.info(event, extra=request_context(request))


def unauthorized(detail: str = "Invalid authentication credentials") -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def current_user_from_authorization(
    authorization: str | None,
    repository: AuthRepository,
) -> AuthUser:
    if authorization is None:
        raise unauthorized("Missing bearer token")

    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != ACCESS_TOKEN_TYPE or not token:
        raise unauthorized()

    try:
        payload = decode_access_token(token)
    except InvalidAccessTokenError as exc:
        raise unauthorized() from exc

    user = await repository.find_user_by_id(payload.user_id)
    if user is None or not user.is_active:
        raise unauthorized()

    return user


@app.post(
    "/auth/register",
    response_model=AuthUserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["auth"],
)
async def register(
    request_body: RegisterRequest,
    request: Request,
    repository: AuthRepository = Depends(get_auth_repository),
) -> AuthUserResponse:
    if await repository.find_user_by_username(request_body.username) is not None:
        log_auth_event(request, "auth.registration_failed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already exists",
        )

    if await repository.find_user_by_email(request_body.email) is not None:
        log_auth_event(request, "auth.registration_failed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    try:
        user = await repository.create_user(
            CreateAuthUser(
                username=request_body.username,
                email=request_body.email,
                display_name=request_body.display_name,
                password_hash=hash_password(request_body.password),
            )
        )
    except DuplicateAuthUserError as exc:
        log_auth_event(request, "auth.registration_failed")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        ) from exc

    log_auth_event(request, "auth.user_registered")
    return user_response(user)


@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(
    credentials: LoginRequest,
    request: Request,
    repository: AuthRepository = Depends(get_auth_repository),
) -> LoginResponse:
    user = await repository.find_user_by_username(credentials.username)
    if (
        user is None
        or not user.is_active
        or not verify_password(credentials.password, user.password_hash)
    ):
        log_auth_event(request, "auth.login_failed")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    token = create_access_token(user_id=user.id, username=user.username)
    log_auth_event(request, "auth.login_succeeded")
    return LoginResponse(
        user_id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        access_token=token.value,
        token_type=ACCESS_TOKEN_TYPE,
        expires_in=token.expires_in,
    )


@app.get("/auth/me", response_model=AuthUserResponse, tags=["auth"])
async def me(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    repository: AuthRepository = Depends(get_auth_repository),
) -> AuthUserResponse:
    user = await current_user_from_authorization(authorization, repository)
    log_auth_event(request, "auth.me_requested")
    return user_response(user)


async def dispose_auth_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "auth_database_engine", None)
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_auth_database_engine)
