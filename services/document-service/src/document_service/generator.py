"""Local PDF document generation boundary."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from os import environ
from pathlib import Path
from uuid import uuid4

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .repository import (
    DOCUMENT_STATUS_GENERATED,
    DOCUMENT_TYPE_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    CreateDocumentMetadata,
)


DOCUMENT_STORAGE_DIR_ENV = "DOCUMENT_STORAGE_DIR"
DEFAULT_DOCUMENT_STORAGE_DIR = "./local-data/documents"
PDF_CONTENT_TYPE = "application/pdf"
LOCAL_PDF_GENERATOR = "local-pdf-generator"


@dataclass(frozen=True)
class GeneratedDocument:
    metadata: CreateDocumentMetadata
    storage_path: Path


def get_document_storage_dir() -> Path:
    return Path(environ.get(DOCUMENT_STORAGE_DIR_ENV, DEFAULT_DOCUMENT_STORAGE_DIR))


class LocalPdfDocumentGenerator:
    def __init__(self, storage_dir: Path | None = None) -> None:
        self._storage_dir = storage_dir or get_document_storage_dir()

    def generate(self, *, order_id: str, document_type: str) -> GeneratedDocument:
        generated_at = datetime.now(UTC)
        document_id = f"document-{uuid4().hex}"
        document_number = self._document_number(document_type, document_id)
        document_title = self._document_title(document_type)
        storage_path = self._storage_dir / document_type / f"{document_id}.pdf"
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        self._write_pdf(
            storage_path=storage_path,
            document_number=document_number,
            document_title=document_title,
            document_type=document_type,
            order_id=order_id,
            generated_at=generated_at,
        )

        file_bytes = storage_path.read_bytes()
        checksum = sha256(file_bytes).hexdigest()

        metadata = CreateDocumentMetadata(
            id=document_id,
            order_id=order_id,
            document_type=document_type,
            status=DOCUMENT_STATUS_GENERATED,
            document_ref=f"local-document://{document_type}/{document_id}",
            document_number=document_number,
            document_title=document_title,
            content_type=PDF_CONTENT_TYPE,
            storage_path=str(storage_path),
            size_bytes=len(file_bytes),
            checksum_sha256=checksum,
            generator=LOCAL_PDF_GENERATOR,
        )

        return GeneratedDocument(metadata=metadata, storage_path=storage_path)

    @staticmethod
    def _document_number(document_type: str, document_id: str) -> str:
        prefix = "INV" if document_type == DOCUMENT_TYPE_INVOICE else "REC"
        return f"MWP-{prefix}-{document_id[-8:].upper()}"

    @staticmethod
    def _document_title(document_type: str) -> str:
        if document_type == DOCUMENT_TYPE_RECEIPT:
            return "Local Workflow Receipt"
        return "Local Workflow Invoice"

    @staticmethod
    def _write_pdf(
        *,
        storage_path: Path,
        document_number: str,
        document_title: str,
        document_type: str,
        order_id: str,
        generated_at: datetime,
    ) -> None:
        pdf = canvas.Canvas(str(storage_path), pagesize=letter)
        width, height = letter
        y = height - 72

        pdf.setTitle(document_title)
        pdf.setFont("Helvetica-Bold", 18)
        pdf.drawString(72, y, document_title)
        y -= 36

        pdf.setFont("Helvetica", 11)
        rows = [
            ("Document number", document_number),
            ("Document type", document_type),
            ("Order ID", order_id),
            ("Generated at", generated_at.isoformat()),
            ("Workflow", "RetailOps-microservices-platform local TASK-013"),
            ("Provider", LOCAL_PDF_GENERATOR),
        ]

        for label, value in rows:
            pdf.setFont("Helvetica-Bold", 11)
            pdf.drawString(72, y, f"{label}:")
            pdf.setFont("Helvetica", 11)
            pdf.drawString(190, y, value)
            y -= 22

        pdf.line(72, y - 4, width - 72, y - 4)
        y -= 32
        pdf.drawString(
            72,
            y,
            "This PDF is generated locally for deterministic workflow validation.",
        )
        pdf.showPage()
        pdf.save()
