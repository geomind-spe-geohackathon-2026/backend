"""The header every gemini document carries, which a schema alone does not fix."""

from typing import Any

import gemini as gm

from src.core.gemini import case


def case_schema() -> dict[str, Any]:
    """Return gemini's case schema with the kind a case document must carry."""
    schema = case.schema()
    kind = {**schema["properties"]["kind"], "const": gm.Case.__name__.lower()}
    return {**schema, "properties": {**schema["properties"], "kind": kind}}
