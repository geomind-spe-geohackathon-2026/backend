"""What every writer of a project case version shares: keys, digest, file names."""

import hashlib
import json
import posixpath
from collections.abc import Awaitable, Callable
from typing import Any

from src.core.clients.postgres.repositories.version import content_digest

ECONOMICS = "economics"
FILE = "file"


def object_key(project_id: Any, data: bytes) -> str:
    """Return the object store key of a case file: one object per content."""
    return f"case/{project_id}/{hashlib.sha256(data).hexdigest()}"


def files_digest(content: dict[str, Any], files: dict[str, bytes]) -> str:
    """Hash a case document together with the bytes of its files."""
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    return content_digest({"content": content, "files": hashes})


def series_files(node: Any) -> list[str]:
    """Return the ``file`` names inside a case dict or list, in order."""
    if isinstance(node, list):
        return [name for item in node for name in series_files(item)]
    if not isinstance(node, dict):
        return []
    named = [node[FILE]] if isinstance(node.get(FILE), str) else []
    return named + [name for item in node.values() for name in series_files(item)]


def economics_files(name: str, data: bytes) -> list[str]:
    """Return the series files an economics file names, relative to its folder."""
    try:
        content = json.loads(data)
    except ValueError:
        return []
    folder = posixpath.dirname(name)
    return [
        posixpath.normpath(posixpath.join(folder, item))
        for item in series_files(content)
    ]


async def named_files(
    content: dict[str, Any], read: Callable[[str], Awaitable[bytes | None]]
) -> dict[str, bytes]:
    """Return ``{name: bytes}`` of every file a case names that ``read`` finds.

    A case names the ``file`` of each series and its ``economics`` file, and the
    economics file may name series files of its own.
    """
    economics = content.get(ECONOMICS)
    rest = {key: value for key, value in content.items() if key != ECONOMICS}
    queue = ([economics] if isinstance(economics, str) else []) + series_files(rest)
    files: dict[str, bytes] = {}
    while queue:
        name = queue.pop(0)
        data = None if name in files else await read(name)
        if data is None:
            continue
        files[name] = data
        if name == economics:
            queue += economics_files(name, data)
    return files
