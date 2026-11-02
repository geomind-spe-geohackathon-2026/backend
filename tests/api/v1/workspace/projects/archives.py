import json
from io import BytesIO
from zipfile import ZipFile

from tests.plants import example_plant

PROJECT_FILE = json.dumps(
    {"format": 1, "name": "Imported", "exported": "2026-10-30T12:00:00+00:00"}
)


def version_file(number: int = 1, content: object = None) -> str:
    return json.dumps(
        {
            "number": number,
            "note": "Design",
            "created": "2026-10-30T12:00:00+00:00",
            "content": example_plant() if content is None else content,
        }
    )


def archive_of(files: dict[str, str]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    return buffer.getvalue()
