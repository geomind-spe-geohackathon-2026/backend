"""Write the application's OpenAPI document to ``openapi.json`` at the repo root.

Run it from the repo root: ``.venv/bin/python scripts/to_openapi.py``. The frontend
generates its types from the file. A test fails when the committed file is stale.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "openapi.json"


def to_json() -> str:
    """Return the OpenAPI document of the application as stable JSON text."""
    sys.path.insert(0, str(ROOT))
    from src.fastapi import app

    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    OUTPUT.write_text(to_json())


if __name__ == "__main__":
    main()
