"""The committed openapi.json is what the application serves now."""

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "to_openapi.py"


def load_script():
    spec = importlib.util.spec_from_file_location("to_openapi", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_openapi_file_is_not_stale() -> None:
    committed = (ROOT / "openapi.json").read_text()

    assert committed == load_script().to_json(), (
        "openapi.json is stale; run .venv/bin/python scripts/to_openapi.py"
    )


def test_script_writes_the_document(tmp_path: Path, monkeypatch) -> None:
    module = load_script()
    monkeypatch.setattr(module, "OUTPUT", tmp_path / "openapi.json")

    module.main()

    assert (tmp_path / "openapi.json").read_text() == module.to_json()


def test_shared_schemas_have_plain_names() -> None:
    names = set(json.loads(load_script().to_json())["components"]["schemas"])

    assert {"Chat", "Run"} <= names
    assert not [name for name in names if name.endswith(("__Chat", "__Run"))]


def test_no_schema_name_carries_a_module_prefix() -> None:
    document = load_script().to_json()

    assert "src__" not in document
