"""Document service application entrypoint."""

from pathlib import Path
from typing import Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncEngine

from mwp_common import (
    create_app,
    create_async_database_engine_from_config,
    create_async_session_factory,
)
from mwp_common.correlation import request_context

from .generator import LocalPdfDocumentGenerator
from .repository import (
    DOCUMENT_TYPE_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    CreateDocumentMetadata,
    DocumentMetadata,
    DocumentRepository,
)
from .schemas import CreateDocumentRequest, DocumentMetadataResponse

app = create_app("document-service")


class DocumentStorage(Protocol):
    async def create_document_metadata(
        self,
        document: CreateDocumentMetadata,
    ) -> DocumentMetadata:
        """Store generated local document metadata."""

    async def find_document_by_id(self, document_id: str) -> DocumentMetadata | None:
        """Return one stored document metadata record by id."""


class DocumentGenerator(Protocol):
    def generate(self, *, order_id: str, document_type: str):
        """Generate a local document file and metadata."""


def get_document_repository() -> DocumentStorage:
    engine = getattr(app.state, "document_database_engine", None)
    if engine is None:
        engine = create_async_database_engine_from_config()
        app.state.document_database_engine = engine
        app.state.document_session_factory = create_async_session_factory(engine)

    return DocumentRepository(app.state.document_session_factory)


def get_document_generator() -> DocumentGenerator:
    generator = getattr(app.state, "document_generator", None)
    if generator is None:
        generator = LocalPdfDocumentGenerator()
        app.state.document_generator = generator

    return generator


def document_response(document: DocumentMetadata) -> DocumentMetadataResponse:
    return DocumentMetadataResponse(
        id=document.id,
        order_id=document.order_id,
        document_type=document.document_type,
        status=document.status,
        document_ref=document.document_ref,
        document_number=document.document_number,
        document_title=document.document_title,
        content_type=document.content_type,
        storage_path=document.storage_path,
        size_bytes=document.size_bytes,
        checksum_sha256=document.checksum_sha256,
        generator=document.generator,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def log_document_event(request: Request, event: str) -> None:
    app.state.logger.info(event, extra=request_context(request))


async def create_document(
    *,
    order_id: str,
    document_type: str,
    request: Request,
    generator: DocumentGenerator,
    repository: DocumentStorage,
) -> DocumentMetadataResponse:
    generated = generator.generate(order_id=order_id, document_type=document_type)
    document = await repository.create_document_metadata(generated.metadata)
    log_document_event(request, "document.generated")
    return document_response(document)


@app.post(
    "/documents/invoice",
    response_model=DocumentMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def create_invoice_metadata(
    request_body: CreateDocumentRequest,
    request: Request,
    generator: DocumentGenerator = Depends(get_document_generator),
    repository: DocumentStorage = Depends(get_document_repository),
) -> DocumentMetadataResponse:
    return await create_document(
        order_id=request_body.order_id,
        document_type=DOCUMENT_TYPE_INVOICE,
        request=request,
        generator=generator,
        repository=repository,
    )


@app.post(
    "/documents/receipt",
    response_model=DocumentMetadataResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
async def create_receipt_metadata(
    request_body: CreateDocumentRequest,
    request: Request,
    generator: DocumentGenerator = Depends(get_document_generator),
    repository: DocumentStorage = Depends(get_document_repository),
) -> DocumentMetadataResponse:
    return await create_document(
        order_id=request_body.order_id,
        document_type=DOCUMENT_TYPE_RECEIPT,
        request=request,
        generator=generator,
        repository=repository,
    )


@app.get(
    "/documents/{document_id}",
    response_model=DocumentMetadataResponse,
    tags=["documents"],
)
async def get_document(
    document_id: str,
    repository: DocumentStorage = Depends(get_document_repository),
) -> DocumentMetadataResponse:
    document = await repository.find_document_by_id(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    return document_response(document)


@app.get("/documents/{document_id}/download", tags=["documents"])
async def download_document(
    document_id: str,
    repository: DocumentStorage = Depends(get_document_repository),
) -> FileResponse:
    document = await repository.find_document_by_id(document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )
    if document.storage_path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    storage_path = Path(document.storage_path)
    if not storage_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found",
        )

    return FileResponse(
        path=storage_path,
        media_type=document.content_type or "application/pdf",
        filename=f"{document.document_number or document.id}.pdf",
    )


async def dispose_document_database_engine() -> None:
    engine: AsyncEngine | None = getattr(app.state, "document_database_engine", None)
    if engine is not None:
        await engine.dispose()


app.router.on_shutdown.append(dispose_document_database_engine)
