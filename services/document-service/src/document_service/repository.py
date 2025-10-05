"""PostgreSQL-backed document metadata storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


DOCUMENT_TYPE_INVOICE = "invoice"
DOCUMENT_TYPE_RECEIPT = "receipt"
DOCUMENT_STATUS_GENERATED = "generated"


@dataclass(frozen=True)
class CreateDocumentMetadata:
    id: str
    order_id: str
    document_type: str
    status: str
    document_ref: str
    document_number: str
    document_title: str
    content_type: str
    storage_path: str
    size_bytes: int
    checksum_sha256: str
    generator: str


@dataclass(frozen=True)
class DocumentMetadata:
    id: str
    order_id: str
    document_type: str
    status: str
    document_ref: str
    document_number: str | None
    document_title: str | None
    content_type: str | None
    storage_path: str | None
    size_bytes: int | None
    checksum_sha256: str | None
    generator: str | None
    created_at: datetime
    updated_at: datetime


class DocumentRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def create_document_metadata(
        self,
        document: CreateDocumentMetadata,
    ) -> DocumentMetadata:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    INSERT INTO document_metadata (
                        id, order_id, document_type, status, document_ref,
                        document_number, document_title, content_type, storage_path,
                        size_bytes, checksum_sha256, generator,
                        created_at, updated_at
                    )
                    VALUES (
                        :id, :order_id, :document_type, :status, :document_ref,
                        :document_number, :document_title, :content_type,
                        :storage_path, :size_bytes, :checksum_sha256, :generator,
                        :created_at, :updated_at
                    )
                    RETURNING
                        id, order_id, document_type, status, document_ref,
                        document_number, document_title, content_type, storage_path,
                        size_bytes, checksum_sha256, generator,
                        created_at, updated_at
                    """
                ),
                {
                    **document.__dict__,
                    "created_at": datetime.now(UTC),
                    "updated_at": datetime.now(UTC),
                },
            )
            row = result.mappings().one()
            await session.commit()

        return self._document_from_row(row)

    async def find_document_by_id(self, document_id: str) -> DocumentMetadata | None:
        async with self._session_factory() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id, order_id, document_type, status, document_ref,
                        document_number, document_title, content_type, storage_path,
                        size_bytes, checksum_sha256, generator,
                        created_at, updated_at
                    FROM document_metadata
                    WHERE id = :document_id
                    """
                ),
                {"document_id": document_id},
            )
            row = result.mappings().first()

        if row is None:
            return None

        return self._document_from_row(row)

    @staticmethod
    def _document_from_row(row: Mapping[str, Any]) -> DocumentMetadata:
        return DocumentMetadata(
            id=row["id"],
            order_id=row["order_id"],
            document_type=row["document_type"],
            status=row["status"],
            document_ref=row["document_ref"],
            document_number=row["document_number"],
            document_title=row["document_title"],
            content_type=row["content_type"],
            storage_path=row["storage_path"],
            size_bytes=row["size_bytes"],
            checksum_sha256=row["checksum_sha256"],
            generator=row["generator"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
