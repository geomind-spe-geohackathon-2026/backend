"""Seed the QA3 projects on a running API, each with the stages before its own already done.

The QA sessions each test one stage of the pipeline; this script prepares a project per stage
through the public API, as the admin, with the same calls the web app makes (no database
writes). Inputs are only the competition files, the team's assumptions file
(``documents/project/quality-assurance/inputs/assumptions.md``, values the competition files do
not give, each with its source) and gemini's sample built from them
(``gemini/examples/hackathon_2026``).

    QA3 case        the PDF, the two daily CSVs and assumptions.md uploaded, nothing else
    QA3 plant       + the case of the sample (case.json with its demand and economics files)
    QA3 simulation  + the plants HackathonPlant and HeatingAbsorptionCoolingPlant (versions 1, 2)
    QA3 study       + a whole-year `run` study of each plant, done (one result each)
    QA3 report      + a ranked `run` study of each plant (objective lcts, metric co2), done

A page study runs one plant version, so "one study over both plants" is two studies here.

Run from the backend folder (credentials are read from the env file, never printed):

    .venv/bin/python -m scripts.seed_qa_projects --api https://api.geomind.team/api/v1 \\
        --env .env --sample ../gemini/examples/hackathon_2026 \\
        --assumptions ../documents/project/quality-assurance/inputs/assumptions.md
"""

import argparse
import json
import time
from pathlib import Path
from typing import Any

import httpx

PLANTS = ("HackathonPlant", "HeatingAbsorptionCoolingPlant")
STAGES = ("case", "plant", "simulation", "study", "report")
DOCUMENTS = (
    "GEMINI_Hackathon_Challenge_Requirements.pdf",
    "GEMINI_Heating_Demand_Daily_2027.csv",
    "GEMINI_Cooling_Demand_Daily_2027.csv",
)
STUDY_WAIT_S = 1800
POLL_S = 10


def credentials(env_file: Path) -> tuple[str, str]:
    """Return the admin's email and password from the env file; missing is an error."""
    values = {}
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    email, password = values.get("FIRST_ADMIN_EMAIL"), values.get("FIRST_ADMIN_PASSWORD")
    if not email or not password:
        raise SystemExit(f"{env_file}: FIRST_ADMIN_EMAIL and FIRST_ADMIN_PASSWORD are needed")
    return email, password


class Api:
    """The API as one signed-in user."""

    def __init__(self, base: str, email: str, password: str) -> None:
        self.http = httpx.Client(base_url=base, timeout=120)
        token = self.call("POST", "/identity/authn/login", json={"email": email, "password": password})
        self.http.headers["Authorization"] = f"Bearer {token['access_token']}"

    def call(self, method: str, path: str, **kwargs: Any) -> Any:
        response = self.http.request(method, path, **kwargs)
        if response.status_code >= 400:
            raise SystemExit(f"{method} {path}: {response.status_code} {response.text[:500]}")
        return response.json() if response.content else None


def upload_documents(api: Api, project: str, sample: Path, assumptions: Path) -> None:
    """Upload the three competition files and the assumptions file to the project."""
    paths = [sample / name for name in DOCUMENTS] + [assumptions]
    for path in paths:
        with open(path, "rb") as handle:
            api.call("POST", "/workspace/rag", data={"project": project}, files={"file": (path.name, handle)})


def set_case(api: Api, project: str, sample: Path) -> int:
    """Save the sample case, then the files it names; return the latest case version."""
    content = json.loads((sample / "case.json").read_text())
    api.call("POST", "/design/case", json={"project": project, "base": None, "note": "Sample case (QA3 seed)", "content": content})
    version = 1
    files = [("data/demand.csv", sample / "data" / "demand.csv")]
    economics = content.get("economics")
    if isinstance(economics, str):
        files.append((economics, sample / economics))
    for name, path in files:
        with open(path, "rb") as handle:
            api.call(
                "POST",
                "/design/case/files",
                data={"project": project, "base": str(version), "name": name},
                files={"file": (Path(name).name, handle)},
            )
        version += 1
    return version


def store_plants(api: Api, project: str, sample: Path) -> dict[str, int]:
    """Save each sample plant as the next plant version; return ``{plant: version}``."""
    versions, base = {}, None
    for name in PLANTS:
        spec = json.loads((sample / "plants" / f"{name}.json").read_text())
        api.call("POST", "/plant/flowsheet", json={"project": project, "base": base, "note": f"{name} (QA3 seed)", "spec": spec})
        base = 1 if base is None else base + 1
        versions[name] = base
    return versions


def run_study(api: Api, project: str, name: str, settings: dict[str, Any], version: int) -> dict[str, Any]:
    """Create a `run` study of one plant version and wait until it ends; return it."""
    body = {"project": project, "kind": "run", "name": name, "settings": settings, "plant_version": version}
    study = api.call("POST", "/design/study", json=body)
    deadline = time.monotonic() + STUDY_WAIT_S
    while study["status"] in ("queued", "running") and time.monotonic() < deadline:
        time.sleep(POLL_S)
        study = api.call("GET", f"/design/study/{study['id']}")
    if study["status"] != "done":
        raise SystemExit(f"study {name}: {study['status']} {study.get('error') or study.get('missing')}")
    return study


def seed(api: Api, sample: Path, assumptions: Path, prefix: str) -> dict[str, dict[str, Any]]:
    made = {}
    for depth, stage in enumerate(STAGES):
        project = api.call("POST", "/workspace/projects", json={"name": f"{prefix} {stage}"})["id"]
        holds: dict[str, Any] = {"documents": [*DOCUMENTS, assumptions.name]}
        upload_documents(api, project, sample, assumptions)
        if depth >= 1:
            holds["case_version"] = set_case(api, project, sample)
        if depth >= 2:
            holds["plant_versions"] = store_plants(api, project, sample)
        if depth >= 3:
            holds["simulations"] = {
                name: run_study(api, project, f"simulation {name}", {}, version)["result"]
                for name, version in holds["plant_versions"].items()
            }
        if depth >= 4:
            ranked = {"objective": "lcts", "metrics": ["co2"]}
            holds["studies"] = {
                name: run_study(api, project, f"economics {name}", ranked, version)["result"]
                for name, version in holds["plant_versions"].items()
            }
        made[f"{prefix} {stage}"] = {"project": project, **holds}
        print(json.dumps({f"{prefix} {stage}": made[f"{prefix} {stage}"]}), flush=True)
    return made


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--api", required=True, help="the API base, e.g. https://api.geomind.team/api/v1")
    parser.add_argument("--env", required=True, type=Path, help="the env file with FIRST_ADMIN_*")
    parser.add_argument("--sample", required=True, type=Path, help="gemini/examples/hackathon_2026")
    parser.add_argument("--assumptions", required=True, type=Path, help="the assumptions.md to upload with the competition files")
    parser.add_argument("--prefix", default="QA3", help="the project name prefix")
    arguments = parser.parse_args()
    email, password = credentials(arguments.env)
    if not arguments.assumptions.is_file():
        raise SystemExit(f"{arguments.assumptions}: no such file")
    seed(Api(arguments.api, email, password), arguments.sample, arguments.assumptions, arguments.prefix)


if __name__ == "__main__":
    main()
