from fastapi.testclient import TestClient

from catalog_service.main import app, get_catalog_repository
from catalog_service.repository import CatalogItem


CATALOG_ITEM_BASIC = CatalogItem(
    id="catalog-item-basic",
    sku="MWP-BASIC",
    name="Basic Workflow Package",
    description="Deterministic catalog item for the critical workflow.",
    price_kopecks=199000,
    currency="RUB",
)

CATALOG_ITEM_PRO = CatalogItem(
    id="catalog-item-pro",
    sku="MWP-PRO",
    name="Pro Workflow Package",
    description="Second deterministic catalog item for local validation.",
    price_kopecks=499000,
    currency="RUB",
)


class FakeCatalogRepository:
    def __init__(self, items: list[CatalogItem]) -> None:
        self._items = items

    async def list_active_items(self) -> list[CatalogItem]:
        return self._items

    async def find_active_item_by_id(self, item_id: str) -> CatalogItem | None:
        for item in self._items:
            if item.id == item_id:
                return item
        return None


def make_client(repository: FakeCatalogRepository | None = None) -> TestClient:
    app.dependency_overrides.clear()
    if repository is not None:
        app.dependency_overrides[get_catalog_repository] = lambda: repository
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

    assert response.json()["service"] == "catalog-service"


def test_correlation_id_is_returned() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={"X-Correlation-ID": "catalog-request-1"},
    )

    assert response.headers["X-Correlation-ID"] == "catalog-request-1"


def test_trace_headers_do_not_break_health_request() -> None:
    client = make_client()

    response = client.get(
        "/health",
        headers={
            "X-Correlation-ID": "catalog-request-2",
            "X-Debug-Trace-ID": "future-run",
            "X-Request-Source": "future-scenario",
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-ID"] == "catalog-request-2"


def test_list_catalog_items_returns_seeded_items() -> None:
    client = make_client(FakeCatalogRepository([CATALOG_ITEM_BASIC, CATALOG_ITEM_PRO]))

    response = client.get("/catalog/items")

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "id": "catalog-item-basic",
                "sku": "MWP-BASIC",
                "name": "Basic Workflow Package",
                "description": (
                    "Deterministic catalog item for the critical workflow."
                ),
                "price_kopecks": 199000,
                "currency": "RUB",
            },
            {
                "id": "catalog-item-pro",
                "sku": "MWP-PRO",
                "name": "Pro Workflow Package",
                "description": "Second deterministic catalog item for local validation.",
                "price_kopecks": 499000,
                "currency": "RUB",
            },
        ]
    }


def test_get_catalog_item_returns_seeded_item_by_id() -> None:
    client = make_client(FakeCatalogRepository([CATALOG_ITEM_BASIC, CATALOG_ITEM_PRO]))

    response = client.get("/catalog/items/catalog-item-basic")

    assert response.status_code == 200
    assert response.json() == {
        "id": "catalog-item-basic",
        "sku": "MWP-BASIC",
        "name": "Basic Workflow Package",
        "description": "Deterministic catalog item for the critical workflow.",
        "price_kopecks": 199000,
        "currency": "RUB",
    }


def test_get_catalog_item_returns_404_for_missing_item() -> None:
    client = make_client(FakeCatalogRepository([CATALOG_ITEM_BASIC]))

    response = client.get("/catalog/items/not-existing-item")

    assert response.status_code == 404
    assert response.json() == {"detail": "Catalog item not found"}
