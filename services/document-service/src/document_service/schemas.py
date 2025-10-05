"""Request and response schemas for document-service endpoints."""

from datetime import datetime

from pydantic import BaseModel


class CreateDocumentRequest(BaseModel):
    order_id: str


class DocumentMetadataResponse(BaseModel):
    id: str
    order_id: str
    document_type: str
    status: str
    document_ref: str
    document_number: str | None = None
    document_title: str | None = None
    content_type: str | None = None
    storage_path: str | None = None
    size_bytes: int | None = None
    checksum_sha256: str | None = None
    generator: str | None = None
    created_at: datetime
    updated_at: datetime
