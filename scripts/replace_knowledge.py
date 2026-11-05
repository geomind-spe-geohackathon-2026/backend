"""Replace global Knowledge documents on a running API with newer files of the same name.

Each file is uploaded to the global Knowledge (no project) as the admin, then the older document
of the same name is deleted; the script waits until every document is searchable and prints
their names, states and ids. Credentials are read from the env file, never printed.

    .venv/bin/python -m scripts.replace_knowledge --api https://api.geomind.team/api/v1 \\
        --env .env ../geomind/data/knowledge/cost-sources.csv ../geomind/data/knowledge/cost-sources.md
"""

import argparse
import json
import time
from pathlib import Path

from scripts.seed_qa_projects import Api, credentials

TYPES = {".csv": "text/csv", ".md": "text/markdown"}
WAIT_S = 600
POLL_S = 10


def documents(api: Api) -> list[dict]:
    """Return the global Knowledge documents."""
    return api.call("GET", "/workspace/rag", params={"limit": 200})["items"]


def replace(api: Api, path: Path) -> None:
    """Upload the file, then delete the older global document of the same name."""
    older = [item["id"] for item in documents(api) if item["name"] == path.name]
    with open(path, "rb") as handle:
        kind = TYPES.get(path.suffix, "application/octet-stream")
        new = api.call("POST", "/workspace/rag", files={"file": (path.name, handle, kind)})
    for identifier in older:
        if identifier != new["id"]:
            api.call("DELETE", f"/workspace/rag/{identifier}")
    print(json.dumps({"uploaded": path.name, "id": new["id"], "deleted": older}), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True, help="the API base, e.g. https://api.geomind.team/api/v1")
    parser.add_argument("--env", required=True, type=Path, help="the env file with FIRST_ADMIN_*")
    parser.add_argument("files", nargs="+", type=Path, help="the files to upload")
    arguments = parser.parse_args()
    for path in arguments.files:
        if not path.is_file():
            raise SystemExit(f"{path}: no such file")
    api = Api(arguments.api, *credentials(arguments.env))
    for path in arguments.files:
        replace(api, path)
    deadline = time.monotonic() + WAIT_S
    while time.monotonic() < deadline:
        found = documents(api)
        if all(item.get("searchable") != "pending" for item in found):
            break
        time.sleep(POLL_S)
    for item in found:
        print(json.dumps({"name": item["name"], "searchable": item.get("searchable"), "id": item["id"]}))


if __name__ == "__main__":
    main()
