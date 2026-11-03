"""Stand-ins for the parts of geomind the backend uses before geomind ships them."""

from types import SimpleNamespace

import geomind as gd


class MemoryRefusal(gd.errors.GeomindError):
    def __init__(self, message: str, path: str) -> None:
        super().__init__(message)
        self.path = path


def check_knowledge(entry: dict) -> dict:
    missing = [
        key
        for key in ("id", "item", "value", "title", "publisher", "year", "status")
        if not entry.get(key)
    ]
    if not (entry.get("page") or entry.get("link")):
        missing.append("page or link")
    if entry.get("status") == "placeholder":
        raise MemoryRefusal(
            "write_memory: a placeholder comes only from a catalogue", "entry"
        )
    if missing:
        raise MemoryRefusal(f"write_memory: lacks {', '.join(missing)}", "entry")
    return entry


def catalogue_entries(rows: list[dict], origin: str) -> list[dict]:
    entries = []
    for row in rows:
        entry = {
            "id": row["id"],
            "item": row.get("item"),
            "value": row.get("value"),
            "unit": row.get("unit"),
            "title": row.get("source"),
            "publisher": row.get("publisher"),
            "year": row.get("year"),
            "page": row.get("page"),
            "status": row.get("status"),
            "origin": origin,
        }
        entries.append(check_knowledge(entry))
    return entries


MEMORY = SimpleNamespace(
    check_knowledge=check_knowledge,
    catalogue_entries=catalogue_entries,
    SECTIONS=("knowledge", "experience"),
)


class ConnectorError(gd.errors.GeomindError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.code = code


def mcp_with(tools: list[dict] | None = None, error: str | None = None, seen=None):
    def list_tools(server: dict) -> list[dict]:
        if seen is not None:
            seen.append(server)
        if error is not None:
            raise ConnectorError("the server refused the sign-in", error)
        return tools or []

    return SimpleNamespace(list_tools=list_tools, ConnectorError=ConnectorError)
