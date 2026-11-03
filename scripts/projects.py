"""Move whole projects between databases: rows and objects, under their own ids."""

import argparse
import asyncio
import base64
import json
import tarfile
from collections import defaultdict
from collections.abc import Iterable
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import Column, LargeBinary, Select, Table, Uuid, func, insert, select
from sqlalchemy.ext.asyncio import AsyncConnection

from src.core.clients.minio.blobs import BlobStore
from src.core.clients.minio.client import create_minio_client
from src.core.clients.postgres import models  # noqa: F401
from src.core.clients.postgres.client import (
    Base,
    UtcDateTime,
    create_postgres_client,
)
from src.core.settings import settings

BUNDLE_FORMAT = 1
USERS = "users"
SHARED_TABLES = frozenset({USERS, "mcp_servers"})
"""Tables no project owns; an MCP server's secret never leaves this server."""
PROJECTS = "projects"
MANIFEST = "manifest.json"
TABLE_FOLDER = "tables/"
OBJECT_FOLDER = "objects/"
KEY_COLUMN = "object_key"
PROJECT_PREFIXES = ("case/{id}/", "projects/{id}/", "plant/{id}/")


class TransferError(Exception):
    """A bundle that cannot be written or imported as asked."""


class Blobs(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, data: bytes) -> None: ...

    async def keys(self, prefix: str) -> list[str]: ...


def project_tables() -> list[Table]:
    """Return every table a project owns rows of, parents first."""
    return [
        table
        for table in Base.metadata.sorted_tables
        if table.name not in SHARED_TABLES
    ]


def rows_of_table(table: Table, ids: list[UUID]) -> Select[Any]:
    """Select a table's rows that belong to the projects, or refuse an unknown table."""
    chats = Base.metadata.tables["chats"]
    runs = Base.metadata.tables["runs"]
    if table.name == PROJECTS:
        return select(table).where(table.c.id.in_(ids))
    if "project_id" in table.c:
        return select(table).where(table.c.project_id.in_(ids))
    if "chat_id" in table.c:
        chosen = select(chats.c.id).where(chats.c.project_id.in_(ids))
        return select(table).where(table.c.chat_id.in_(chosen))
    if "run_id" in table.c:
        chosen = select(runs.c.id).where(runs.c.project_id.in_(ids))
        return select(table).where(table.c.run_id.in_(chosen))
    raise TransferError(f"No rule says which project a {table.name} row belongs to")


def to_plain(value: Any) -> Any:
    """Write a column value in JSON."""
    if isinstance(value, bytes):
        return base64.b64encode(value).decode()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def from_plain(column: Column[Any], value: Any) -> Any:
    """Read a column value back from JSON, by the column's type."""
    if value is None:
        return None
    if isinstance(column.type, LargeBinary):
        return base64.b64decode(value)
    if isinstance(column.type, Uuid):
        return UUID(value)
    if isinstance(column.type, UtcDateTime):
        return datetime.fromisoformat(value)
    return value


async def read_rows(
    connection: AsyncConnection, ids: list[UUID]
) -> dict[str, list[dict[str, Any]]]:
    """Return the rows of the projects, by table, as JSON values."""
    found: dict[str, list[dict[str, Any]]] = {}
    for table in project_tables():
        result = await connection.execute(rows_of_table(table, ids))
        found[table.name] = [
            {key: to_plain(value) for key, value in row.items()}
            for row in result.mappings()
        ]
    return found


async def object_keys(blobs: Blobs, rows: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Return the keys the rows name and every key under the projects' prefixes."""
    named = {
        row[KEY_COLUMN]
        for items in rows.values()
        for row in items
        if row.get(KEY_COLUMN)
    }
    for project in rows[PROJECTS]:
        for prefix in PROJECT_PREFIXES:
            named.update(await blobs.keys(prefix.format(id=project["id"])))
    return sorted(named)


def add_member(bundle: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    bundle.addfile(info, BytesIO(data))


def to_lines(rows: list[dict[str, Any]]) -> bytes:
    return "".join(f"{json.dumps(row)}\n" for row in rows).encode()


async def export_bundle(
    connection: AsyncConnection, blobs: Blobs, ids: list[UUID], path: Path
) -> dict[str, Any]:
    """Write the projects to a tar file and return its manifest."""
    rows = await read_rows(connection, ids)
    absent = {str(item) for item in ids} - {row["id"] for row in rows[PROJECTS]}
    if absent:
        raise TransferError(f"No such project: {', '.join(sorted(absent))}")
    keys = await object_keys(blobs, rows)
    contents = {key: await blobs.get(key) for key in keys}
    manifest = {
        "format": BUNDLE_FORMAT,
        "projects": [{"id": row["id"], "name": row["name"]} for row in rows[PROJECTS]],
        "counts": {name: len(items) for name, items in rows.items()},
        "objects": [key for key, data in contents.items() if data is not None],
        "missing_objects": [key for key, data in contents.items() if data is None],
    }
    with tarfile.open(path, "w") as bundle:
        add_member(bundle, MANIFEST, json.dumps(manifest, indent=1).encode())
        for name, items in rows.items():
            add_member(bundle, f"{TABLE_FOLDER}{name}.jsonl", to_lines(items))
        for key, data in contents.items():
            if data is not None:
                add_member(bundle, f"{OBJECT_FOLDER}{key}", data)
    return manifest


def read_member(bundle: tarfile.TarFile, name: str) -> bytes:
    member = bundle.extractfile(name)
    if member is None:
        raise TransferError(f"The bundle has no {name}")
    return member.read()


def read_bundle(
    path: Path,
) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]], dict[str, bytes]]:
    """Return a bundle's manifest, rows by table and objects, checked against it."""
    with tarfile.open(path, "r") as bundle:
        manifest = json.loads(read_member(bundle, MANIFEST))
        if manifest["format"] != BUNDLE_FORMAT:
            raise TransferError(f"Unknown bundle format {manifest['format']}")
        rows = {
            name: [
                json.loads(line)
                for line in read_member(bundle, f"{TABLE_FOLDER}{name}.jsonl")
                .decode()
                .splitlines()
            ]
            for name in manifest["counts"]
        }
        objects = {
            key: read_member(bundle, f"{OBJECT_FOLDER}{key}")
            for key in manifest["objects"]
        }
    known = {table.name for table in project_tables()}
    if set(rows) != known:
        raise TransferError(f"Tables differ: {sorted(set(rows) ^ known)}")
    return manifest, rows, objects


async def existing_ids(
    connection: AsyncConnection, rows: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Count the bundle's ids that the database already has, by table."""
    clashes: dict[str, int] = {}
    for table in project_tables():
        ids = [UUID(row["id"]) for row in rows[table.name]]
        if not ids:
            continue
        query = select(func.count()).select_from(table).where(table.c.id.in_(ids))
        found = await connection.scalar(query)
        if found:
            clashes[table.name] = found
    return clashes


def user_columns(table: Table) -> list[Column[Any]]:
    """Return the columns of a table that point at a user."""
    return [
        column
        for column in table.c
        if any(key.column.table.name == USERS for key in column.foreign_keys)
    ]


def restored(table: Table, row: dict[str, Any], owner: UUID) -> dict[str, Any]:
    """Return a row's stored values with its users replaced by the owner."""
    values = {
        name: from_plain(table.c[name], value)
        for name, value in row.items()
        if value is not None
    }
    for column in user_columns(table):
        if column.name in values:
            values[column.name] = owner
    return values


async def insert_rows(
    connection: AsyncConnection, table: Table, rows: Iterable[dict[str, Any]]
) -> None:
    """Insert rows grouped by the columns they fill, so a null stays a SQL null."""
    groups: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[tuple(sorted(row))].append(row)
    for items in groups.values():
        await connection.execute(insert(table), items)


async def owner_id(connection: AsyncConnection, email: str) -> UUID:
    users = Base.metadata.tables[USERS]
    found = await connection.scalar(select(users.c.id).where(users.c.email == email))
    if found is None:
        raise TransferError(f"No user has the email {email}")
    return found


async def import_bundle(
    connection: AsyncConnection, blobs: Blobs, path: Path, owner_email: str
) -> dict[str, Any]:
    """Add a bundle's projects under an existing owner; refuse any id already there."""
    manifest, rows, objects = read_bundle(path)
    owner = await owner_id(connection, owner_email)
    clashes = await existing_ids(connection, rows)
    if clashes:
        raise TransferError(f"Ids already in the database: {clashes}")
    for table in project_tables():
        items = [restored(table, row, owner) for row in rows[table.name]]
        await insert_rows(connection, table, items)
    for key, data in objects.items():
        await blobs.put(key, data)
    return manifest


def blob_store() -> BlobStore:
    return BlobStore(create_minio_client(), settings.MINIO_BUCKET_NAME)


async def run(arguments: argparse.Namespace) -> dict[str, Any]:
    engine = create_postgres_client()
    try:
        async with engine.begin() as connection:
            if arguments.command == "export":
                ids = [UUID(item) for item in arguments.project]
                return await export_bundle(
                    connection, blob_store(), ids, Path(arguments.out)
                )
            return await import_bundle(
                connection, blob_store(), Path(arguments.bundle), arguments.owner
            )
    finally:
        await engine.dispose()


def parser() -> argparse.ArgumentParser:
    found = argparse.ArgumentParser(description=__doc__)
    commands = found.add_subparsers(dest="command", required=True)
    export = commands.add_parser("export", help="write projects to a tar file")
    export.add_argument("--project", action="append", required=True)
    export.add_argument("--out", required=True)
    add = commands.add_parser("import", help="add a tar file's projects")
    add.add_argument("bundle")
    add.add_argument("--owner", required=True)
    return found


def main() -> None:
    manifest = asyncio.run(run(parser().parse_args()))
    summary = {
        "projects": manifest["projects"],
        "counts": manifest["counts"],
        "objects": len(manifest["objects"]),
        "missing_objects": manifest["missing_objects"],
    }
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
