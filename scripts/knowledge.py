"""Add a file to the shared Knowledge from the command line, such as the cost catalogue.

``python -m src.scripts.knowledge add <file> --by <admin email>`` stores the file, reads
its text at once and makes it searchable for every project's agents. A shared document
of the same name is replaced, so running it again with a newer catalogue is safe.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from src.api.v1.workspace.rag.services import KNOWLEDGE_FOLDER
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.minio.client import create_minio_client
from src.core.clients.postgres import models  # noqa: F401
from src.core.clients.postgres.client import create_postgres_client
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.rag.extract import extract_text, is_supported
from src.core.settings import settings


class KnowledgeError(Exception):
    """A file that cannot be added as asked."""


async def add_file(
    documents: RagDocumentRepository,
    blobs: Any,
    path: Path,
    author_id: Any,
) -> dict[str, Any]:
    """Store a file as a shared Knowledge document, replacing one of the same name."""
    if not is_supported(path.name):
        raise KnowledgeError(f"{path.name}: this file type cannot be read")
    data = path.read_bytes()
    replaced = [
        row for row in await documents.newest_by_name(None) if row.name == path.name
    ]
    key = f"{KNOWLEDGE_FOLDER}/{path.stem}-{len(data)}/{path.name}"
    await blobs.put(key, data)
    document = await documents.create(None, path.name, len(data), key, author_id)
    await documents.set_text(document, extract_text(path.name, data))
    for row in replaced:
        await documents.delete(row.id)
        if row.object_key != key:
            await blobs.delete(row.object_key)
    return {
        "id": str(document.id),
        "name": document.name,
        "searchable": document.searchable,
        "replaced": len(replaced),
    }


async def run(arguments: argparse.Namespace) -> dict[str, Any]:
    engine = create_postgres_client()
    try:
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with factory() as session:
            author = await UserRepository(session).get_by_email(arguments.by)
            if author is None or author.role != "admin":
                raise KnowledgeError(
                    f"{arguments.by}: expected an administrator's email"
                )
            blobs = BlobStore(create_minio_client(), settings.MINIO_BUCKET_NAME)
            return await add_file(
                RagDocumentRepository(session), blobs, Path(arguments.file), author.id
            )
    finally:
        await engine.dispose()


def parser() -> argparse.ArgumentParser:
    found = argparse.ArgumentParser(description=__doc__)
    commands = found.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="add or replace a shared Knowledge file")
    add.add_argument("file")
    add.add_argument("--by", required=True, help="the email of an administrator")
    return found


def main() -> None:
    print(json.dumps(asyncio.run(run(parser().parse_args())), indent=1))


if __name__ == "__main__":
    main()
