import argparse
import json
import os
import sys
from pathlib import Path

import httpx

EXAMPLE = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "hackathon"
PROJECT_NAME = "Example project"
GAP = ("site", "reservoir", "thickness", "value")


def example_case() -> dict:
    content = json.loads((EXAMPLE / "case.json").read_text())
    content["name"] = "example_case"
    node = content
    for key in GAP[:-1]:
        node = node[key]
    del node[GAP[-1]]
    return content


def example_plant() -> dict:
    content = json.loads((EXAMPLE / "plant.json").read_text())
    content["name"] = "ExamplePlant"
    return content


def case_files() -> dict[str, bytes]:
    names = ["economics.json", "data/demand.csv"]
    return {name: (EXAMPLE / name).read_bytes() for name in names}


def sign_in(client: httpx.Client, email: str, password: str) -> None:
    response = client.post(
        "/api/v1/identity/authn/login", json={"email": email, "password": password}
    )
    response.raise_for_status()
    client.headers["authorization"] = f"Bearer {response.json()['access_token']}"


def find_project(client: httpx.Client) -> dict | None:
    response = client.get("/api/v1/workspace/projects", params={"search": PROJECT_NAME})
    response.raise_for_status()
    for project in response.json()["items"]:
        if project["name"] == PROJECT_NAME:
            return project
    return None


def seed_project(client: httpx.Client) -> str:
    response = client.post("/api/v1/workspace/projects", json={"name": PROJECT_NAME})
    response.raise_for_status()
    project = response.json()["id"]
    content = example_case()
    response = client.post(
        "/api/v1/design/case",
        json={"project": project, "base": None, "note": "Example", "content": content},
    )
    response.raise_for_status()
    version = response.json()["version"]
    for name, data in case_files().items():
        response = client.post(
            "/api/v1/design/case/files",
            data={"project": project, "base": str(version), "name": name},
            files={"file": (Path(name).name, data)},
        )
        response.raise_for_status()
        version = response.json()["version"]
    response = client.post(
        "/api/v1/plant/flowsheet",
        json={
            "project": project,
            "base": None,
            "note": "Example",
            "spec": example_plant(),
        },
    )
    response.raise_for_status()
    return project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8000")
    parser.add_argument("--email", default=os.environ.get("FIRST_ADMIN_EMAIL"))
    parser.add_argument("--password", default=os.environ.get("FIRST_ADMIN_PASSWORD"))
    args = parser.parse_args()
    with httpx.Client(base_url=args.url, timeout=60) as client:
        sign_in(client, args.email, args.password)
        existing = find_project(client)
        if existing is not None:
            print(f"example project exists: {existing['id']}")
            return 0
        print(f"example project created: {seed_project(client)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
