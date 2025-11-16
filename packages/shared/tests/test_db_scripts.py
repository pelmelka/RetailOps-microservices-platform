import importlib.util
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def import_script(script_path: Path):
    spec = importlib.util.spec_from_file_location(script_path.stem, script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_seed_script_import_does_not_require_database_connection() -> None:
    module = import_script(REPOSITORY_ROOT / "scripts/db/seed_local_data.py")

    assert module.TEST_USER["id"] == "user-local-001"
    assert [item["id"] for item in module.CATALOG_ITEMS] == [
        "catalog-item-basic",
        "catalog-item-pro",
    ]


def test_bootstrap_script_import_does_not_run_commands() -> None:
    module = import_script(REPOSITORY_ROOT / "scripts/db/bootstrap_local_db.py")

    assert module.REPOSITORY_ROOT == REPOSITORY_ROOT
