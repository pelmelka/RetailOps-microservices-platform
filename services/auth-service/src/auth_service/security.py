"""Password hashing and JWT helpers for auth-service."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from os import environ
from typing import Any, Mapping

import jwt
from pwdlib import PasswordHash


JWT_SECRET_KEY_ENV = "JWT_SECRET_KEY"
JWT_ALGORITHM_ENV = "JWT_ALGORITHM"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES_ENV = "JWT_ACCESS_TOKEN_EXPIRE_MINUTES"

DEFAULT_JWT_SECRET_KEY = "change-me-local-development-secret"
DEFAULT_JWT_ALGORITHM = "HS256"
DEFAULT_JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60
ACCESS_TOKEN_TYPE = "bearer"


@dataclass(frozen=True)
class AuthSecurityConfig:
    jwt_secret_key: str
    jwt_algorithm: str
    access_token_expire_minutes: int


@dataclass(frozen=True)
class AccessToken:
    value: str
    expires_in: int


@dataclass(frozen=True)
class AccessTokenPayload:
    user_id: str
    username: str | None
    expires_at: datetime


class InvalidAccessTokenError(RuntimeError):
    """Raised when an access token cannot be decoded or validated."""


password_hasher = PasswordHash.recommended()


def get_auth_security_config(
    env: Mapping[str, str] | None = None,
) -> AuthSecurityConfig:
    source = environ if env is None else env
    expire_minutes_raw = source.get(
        JWT_ACCESS_TOKEN_EXPIRE_MINUTES_ENV,
        str(DEFAULT_JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    try:
        expire_minutes = int(expire_minutes_raw)
    except ValueError:
        expire_minutes = DEFAULT_JWT_ACCESS_TOKEN_EXPIRE_MINUTES

    return AuthSecurityConfig(
        jwt_secret_key=source.get(JWT_SECRET_KEY_ENV, DEFAULT_JWT_SECRET_KEY),
        jwt_algorithm=source.get(JWT_ALGORITHM_ENV, DEFAULT_JWT_ALGORITHM),
        access_token_expire_minutes=expire_minutes,
    )


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False

    try:
        return password_hasher.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(
    *,
    user_id: str,
    username: str,
    config: AuthSecurityConfig | None = None,
) -> AccessToken:
    security_config = get_auth_security_config() if config is None else config
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(
        minutes=security_config.access_token_expire_minutes
    )
    payload = {
        "sub": user_id,
        "username": username,
        "iat": issued_at,
        "exp": expires_at,
    }
    token = jwt.encode(
        payload,
        security_config.jwt_secret_key,
        algorithm=security_config.jwt_algorithm,
    )

    return AccessToken(
        value=token,
        expires_in=security_config.access_token_expire_minutes * 60,
    )


def decode_access_token(
    token: str,
    config: AuthSecurityConfig | None = None,
) -> AccessTokenPayload:
    security_config = get_auth_security_config() if config is None else config

    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            security_config.jwt_secret_key,
            algorithms=[security_config.jwt_algorithm],
        )
    except jwt.PyJWTError as exc:
        raise InvalidAccessTokenError("Invalid access token") from exc

    user_id = payload.get("sub")
    expires_at = payload.get("exp")
    if not isinstance(user_id, str) or not isinstance(expires_at, int):
        raise InvalidAccessTokenError("Invalid access token")

    username = payload.get("username")
    if username is not None and not isinstance(username, str):
        raise InvalidAccessTokenError("Invalid access token")

    return AccessTokenPayload(
        user_id=user_id,
        username=username,
        expires_at=datetime.fromtimestamp(expires_at, tz=UTC),
    )
