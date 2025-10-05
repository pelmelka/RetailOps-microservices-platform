"""PostgreSQL-backed auth user storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@dataclass(frozen=True)
class CreateAuthUser:
    username: str
    email: str
    display_name: str | None
    password_hash: str


@dataclass(frozen=True)
class AuthUser:
    id: str
    username: str
    email: str
    display_name: str | None
    password_hash: str | None
    is_active: bool


class DuplicateAuthUserError(RuntimeError):
    """Raised when username or email violates auth_users uniqueness."""


class AuthUserRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_user(self, user: CreateAuthUser) -> AuthUser:
        now = datetime.now(UTC)
        user_id = f"user-{uuid4().hex}"
        display_name = user.display_name or user.username

        async with self._session_factory() as session:
            try:
                await session.execute(
                    text(
                        """
                        INSERT INTO auth_users (
                            id, username, email, display_name, password_hash,
                            is_active, created_at, updated_at
                        )
                        VALUES (
                            :id, :username, :email, :display_name, :password_hash,
                            true, :created_at, :updated_at
                        )
                        """
                    ),
                    {
                        "id": user_id,
                        "username": user.username,
                        "email": user.email,
                        "display_name": display_name,
                        "password_hash": user.password_hash,
                        "created_at": now,
                        "updated_at": now,
                    },
                )
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise DuplicateAuthUserError("Duplicate auth user") from exc

        return AuthUser(
            id=user_id,
            username=user.username,
            email=user.email,
            display_name=display_name,
            password_hash=user.password_hash,
            is_active=True,
        )

    async def find_user_by_username(self, username: str) -> AuthUser | None:
        return await self._find_user("username", username)

    async def find_user_by_email(self, email: str) -> AuthUser | None:
        return await self._find_user("email", email)

    async def find_user_by_id(self, user_id: str) -> AuthUser | None:
        return await self._find_user("id", user_id)

    async def _find_user(self, column: str, value: str) -> AuthUser | None:
        if column not in {"id", "username", "email"}:
            raise ValueError("Unsupported auth user lookup")

        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    f"""
                    SELECT id, username, email, display_name, password_hash, is_active
                    FROM auth_users
                    WHERE {column} = :value
                    """
                ),
                {"value": value},
            )
            row = result.mappings().first()

        if row is None:
            return None

        return self._user_from_row(row)

    @staticmethod
    def _user_from_row(row: Mapping[str, Any]) -> AuthUser:
        return AuthUser(
            id=row["id"],
            username=row["username"],
            email=row["email"],
            display_name=row["display_name"],
            password_hash=row["password_hash"],
            is_active=row["is_active"],
        )
