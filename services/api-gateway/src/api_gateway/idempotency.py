"""PostgreSQL-backed idempotency storage for api-gateway mutations."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping, Protocol
from uuid import uuid4

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mwp_common import (
    create_async_database_engine_from_config,
    create_async_session_factory,
)

from .responses import GatewayError


@dataclass(frozen=True)
class IdempotencyRecord:
    user_id: str
    idempotency_key: str
    method: str
    path: str
    request_hash: str
    response_status: int
    response_body: Any


class IdempotencyStorage(Protocol):
    async def find_record(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        method: str,
        path: str,
    ) -> IdempotencyRecord | None:
        """Return an existing idempotency record."""

    async def store_record(self, record: IdempotencyRecord) -> None:
        """Store one idempotency record."""


def request_hash(payload: Any) -> str:
    canonical_payload = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


class GatewayIdempotencyRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def find_record(
        self,
        *,
        user_id: str,
        idempotency_key: str,
        method: str,
        path: str,
    ) -> IdempotencyRecord | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT user_id, idempotency_key, method, path, request_hash,
                        response_status, response_body
                    FROM gateway_idempotency_keys
                    WHERE user_id = :user_id
                        AND idempotency_key = :idempotency_key
                        AND method = :method
                        AND path = :path
                    """
                ),
                {
                    "user_id": user_id,
                    "idempotency_key": idempotency_key,
                    "method": method,
                    "path": path,
                },
            )
            row = result.mappings().first()

        if row is None:
            return None
        return self._record_from_row(row)

    async def store_record(self, record: IdempotencyRecord) -> None:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO gateway_idempotency_keys (
                        id, user_id, idempotency_key, method, path,
                        request_hash, response_status, response_body,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :user_id, :idempotency_key, :method, :path,
                        :request_hash, :response_status,
                        CAST(:response_body AS JSONB),
                        :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": f"idempotency-{uuid4().hex}",
                    "user_id": record.user_id,
                    "idempotency_key": record.idempotency_key,
                    "method": record.method,
                    "path": record.path,
                    "request_hash": record.request_hash,
                    "response_status": record.response_status,
                    "response_body": json.dumps(record.response_body),
                    "created_at": now,
                    "updated_at": now,
                },
            )
            await session.commit()

    @staticmethod
    def _record_from_row(row: Mapping[str, Any]) -> IdempotencyRecord:
        response_body = row["response_body"]
        if isinstance(response_body, str):
            response_body = json.loads(response_body)
        return IdempotencyRecord(
            user_id=row["user_id"],
            idempotency_key=row["idempotency_key"],
            method=row["method"],
            path=row["path"],
            request_hash=row["request_hash"],
            response_status=row["response_status"],
            response_body=response_body,
        )


def get_idempotency_store(request: Request) -> IdempotencyStorage:
    engine = getattr(request.app.state, "gateway_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        request.app.state.gateway_database_engine = engine
        request.app.state.gateway_session_factory = create_async_session_factory(engine)

    return GatewayIdempotencyRepository(request.app.state.gateway_session_factory)


async def idempotent_json_response(
    request: Request,
    user: Mapping[str, Any],
    idempotency_key: str | None,
    request_payload: Any,
    store: IdempotencyStorage,
    handler: Callable[[], Awaitable[tuple[int, Any]]],
) -> JSONResponse:
    if not idempotency_key:
        raise GatewayError(
            status.HTTP_400_BAD_REQUEST,
            "IDEMPOTENCY_KEY_REQUIRED",
            "Idempotency-Key header is required",
        )

    method = request.method
    path = request.url.path
    hashed_request = request_hash(request_payload)
    record = await store.find_record(
        user_id=user["user_id"],
        idempotency_key=idempotency_key,
        method=method,
        path=path,
    )
    if record is not None:
        if record.request_hash != hashed_request:
            raise GatewayError(
                status.HTTP_409_CONFLICT,
                "IDEMPOTENCY_KEY_CONFLICT",
                "Idempotency-Key was already used with a different request",
            )
        return JSONResponse(
            status_code=record.response_status,
            content=record.response_body,
            headers={"Idempotency-Replayed": "true"},
        )

    response_status, response_body = await handler()
    await store.store_record(
        IdempotencyRecord(
            user_id=user["user_id"],
            idempotency_key=idempotency_key,
            method=method,
            path=path,
            request_hash=hashed_request,
            response_status=response_status,
            response_body=response_body,
        )
    )
    return JSONResponse(status_code=response_status, content=response_body)
