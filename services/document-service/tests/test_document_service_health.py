from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient

from document_service.generator import GeneratedDocument, LocalPdfDocumentGenerator
from document_service.main import app, get_document_generator, get_document_repository
from document_service.repository import (
    DOCUMENT_STATUS_GENERATED,
    DOCUMENT_TYPE_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    CreateDocumentMetadata,
    DocumentMetadata,
)


DOCUMENT_CREATED_AT = datetime(2026, 5, 24, 12, 0, 0, tzinfo=UTC)


def document_metadata(
    *,
    document_id: str = "document-test-001",
    document_type: str = DOCUMENT_TYPE_INVOICE,
    storage_path: str = "local-document.pdf",
    size_bytes: int = 32,
    checksum_sha256: str = "a" * 64,
) -> DocumentMetadata:
    return DocumentMetadata(
        id=document_id,
        order_id="order-local-check",
        document_type=document_type,
        status=DOCUMENT_STATUS_GENERATED,
        document_ref=f"local-document://{document_type}/{document_id}",
        document_number=f"MWP-{document_type.upper()}-0001",
        document_title=f"Local Workflow {document_type.title()}",
        content_type="application/pdf",
        storage_path=storage_path,
        size_bytes=size_bytes,
        checksum_sha256=checksum_sha256,
        generator="local-pdf-generator",
        created_at=DOCUMENT_CREATED_AT,
        updated_at=DOCUMENT_CREATED_AT,
    )


class FakeDocumentRepository:
    def __init__(self) -> None:
        self.documents: dict[str, DocumentMetadata] = {}

    async def create_document_metadata(
        self,
        document: CreateDocumentMetadata,
    ) -> DocumentMetadata:
        created = DocumentMetadata(
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
            created_at=DOCUMENT_CREATED_AT,
            updated_at=DOCUMENT_CREATED_AT,
        )
        self.documents[document.id] = created
        return created

    async def find_document_by_id(self, document_id: str) -> DocumentMetadata | None:
        return self.documents.get(document_id)


class FakeDocumentGenerator:
    def __init__(self, storage_path: Path) -> None:
        self._storage_path = storage_path

    def generate(self, *, order_id: str, document_type: str) -> GeneratedDocument:
        file_bytes = self._storage_path.read_bytes()
        document_id = f"document-test-{document_type}"
        return GeneratedDocument(
            metadata=CreateDocumentMetadata(
                id=document_id,
                order_id=order_id,
                document_type=document_type,
                status=DOCUMENT_STATUS_GENERATED,
                document_ref=f"local-document://{document_type}/{document_id}",
                document_number=f"MWP-{document_type.upper()}-0001",
                document_title=f"Local Workflow {document_type.title()}",
                content_type="application/pdf",
                storage_path=str(self._storage_path),
                size_bytes=len(file_bytes),
                checksum_sha256=sha256(file_bytes).hexdigest(),
                generator="local-pdf-generator",
            ),
            storage_path=self._storage_path,
        )


def make_client(
    *,
    repository: FakeDocumentRepository | None = None,
    generator: FakeDocumentGenerator | None = None,
) -> TestClient:
    app.dependency_overrides.clear()
    if repository is not None:
        app.dependency_overrides[get_document_repository] = lambda: repository
    if generator is not None:
        app.dependency_overrides[get_document_generator] = lambda: generator
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

    assert response.json()["service"] == "document-service"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "document-request-1"},
    )

    assert response.headers["X-Correlation-ID"] == "document-request-1"



def test_unknown_trace_headers_do_not_break_health_request() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "document-request-2",
            "X-Request-Source": "smoke-check",
            "X-Debug-Trace-ID": "trace-1",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "document-request-2"


def test_local_pdf_generator_writes_pdf_and_metadata(tmp_path: Path) -> None:
    generator = LocalPdfDocumentGenerator(storage_dir=tmp_path)

    generated = generator.generate(
        order_id="order-local-check",
        document_type=DOCUMENT_TYPE_INVOICE,
    )

    assert generated.storage_path.is_file()
    assert generated.metadata.content_type == "application/pdf"
    assert generated.metadata.size_bytes > 0
    assert len(generated.metadata.checksum_sha256) == 64
    assert generated.metadata.storage_path == str(generated.storage_path)


def test_create_invoice_generates_pdf_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 invoice")
    repository = FakeDocumentRepository()
    client = make_client(
        repository=repository,
        generator=FakeDocumentGenerator(pdf_path),
    )

    response = client.post(
        "/documents/invoice",
        json={"order_id": "order-local-check"},
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == DOCUMENT_TYPE_INVOICE
    assert response.json()["content_type"] == "application/pdf"
    assert response.json()["size_bytes"] > 0
    assert len(response.json()["checksum_sha256"]) == 64


def test_create_receipt_generates_pdf_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "receipt.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 receipt")
    repository = FakeDocumentRepository()
    client = make_client(
        repository=repository,
        generator=FakeDocumentGenerator(pdf_path),
    )

    response = client.post(
        "/documents/receipt",
        json={"order_id": "order-local-check"},
    )

    assert response.status_code == 201
    assert response.json()["document_type"] == DOCUMENT_TYPE_RECEIPT
    assert response.json()["document_ref"].startswith("local-document://receipt/")


def test_get_document_returns_stored_metadata(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 invoice")
    repository = FakeDocumentRepository()
    repository.documents["document-test-001"] = document_metadata(
        storage_path=str(pdf_path),
        size_bytes=pdf_path.stat().st_size,
        checksum_sha256=sha256(pdf_path.read_bytes()).hexdigest(),
    )
    client = make_client(repository=repository)

    response = client.get("/documents/document-test-001")

    assert response.status_code == 200
    assert response.json()["id"] == "document-test-001"
    assert response.json()["generator"] == "local-pdf-generator"


def test_download_document_returns_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 invoice")
    repository = FakeDocumentRepository()
    repository.documents["document-test-001"] = document_metadata(
        storage_path=str(pdf_path),
        size_bytes=pdf_path.stat().st_size,
        checksum_sha256=sha256(pdf_path.read_bytes()).hexdigest(),
    )
    client = make_client(repository=repository)

    response = client.get("/documents/document-test-001/download")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == b"%PDF-1.4 invoice"


def test_get_document_returns_404_for_missing_document() -> None:
    client = make_client(repository=FakeDocumentRepository())

    response = client.get("/documents/not-existing-document")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document not found"}


def test_download_document_returns_404_for_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.pdf"
    repository = FakeDocumentRepository()
    repository.documents["document-test-001"] = document_metadata(
        storage_path=str(missing_path),
    )
    client = make_client(repository=repository)

    response = client.get("/documents/document-test-001/download")

    assert response.status_code == 404
    assert response.json() == {"detail": "Document file not found"}
