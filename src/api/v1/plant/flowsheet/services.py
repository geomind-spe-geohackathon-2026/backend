import json
from typing import Any
from uuid import UUID

from src.api.v1.plant.flowsheet import schemas
from src.core.clients.minio.blobs import BlobStore
from src.core.clients.postgres.models.plant_version import PlantVersion
from src.core.clients.postgres.models.project import Project
from src.core.clients.postgres.models.user import User
from src.core.clients.postgres.repositories.activity import ActivityRepository
from src.core.clients.postgres.repositories.plant_version import (
    PlantVersionRepository,
)
from src.core.clients.postgres.repositories.user import UserRepository
from src.core.gemini import plant
from src.core.gemini.errors import PlantNotFoundError
from src.core.pagination.page import Page
from src.core.versioning import (
    Version,
    check_base,
    describe_versions,
    latest_version,
)


def layout_key(project_id: UUID) -> str:
    return f"plant/{project_id}/layout.json"


async def read_layout(blobs: BlobStore, project_id: UUID) -> dict[str, Any]:
    """Return the project's saved node positions, empty when none were saved."""
    data = await blobs.get(layout_key(project_id))
    return json.loads(data) if data else {}


async def write_layout(
    blobs: BlobStore,
    project_id: UUID,
    layout: dict[str, Any],
) -> None:
    await blobs.put(layout_key(project_id), json.dumps(layout).encode())


def list_palette(category: str | None) -> list[schemas.Palette]:
    """List gemini's modules, all or one category."""
    cards = []
    for name in plant.module_names(category):
        description = plant.describe_class(name)
        cards.append(
            schemas.Palette(
                type=description["type"],
                title=description["type"],
                category=description["category"],
                summary=description["summary"],
            )
        )
    return cards


def list_templates() -> list[schemas.Template]:
    """List gemini's plant classes as templates."""
    templates = []
    for name in plant.template_names():
        card = plant.describe_template(name)
        templates.append(schemas.Template(name=name, title=name, **card))
    return templates


async def build_flowsheet(
    version: PlantVersion,
    blobs: BlobStore,
) -> schemas.Flowsheet:
    built = plant.from_dict(version.content)
    return schemas.Flowsheet(
        project=version.project_id,
        version=version.number,
        spec=version.content,
        layout=await read_layout(blobs, version.project_id),
        **plant.structure(built),
    )


async def get_flowsheet(
    project: Project,
    number: int | None,
    repository: PlantVersionRepository,
    blobs: BlobStore,
) -> schemas.Flowsheet:
    """Return the latest flowsheet of a project, or the numbered one."""
    if number is None:
        version = await latest_version(repository, project.id, PlantNotFoundError)
    else:
        version = await repository.version_by_number(project.id, number)
    if version is None:
        raise PlantNotFoundError("Plant version not found")
    return await build_flowsheet(version, blobs)


def spec_of(payload: schemas.FlowsheetCreate) -> dict[str, Any]:
    """Return the checked document: the given spec, or the template with values."""
    if payload.template is None:
        return plant.validate_content(payload.spec)
    built = plant.from_template(payload.template)
    for module, params in (payload.parameters or {}).items():
        plant.set_parameters(built, module, params, None)
    return plant.to_dict(built)


async def save_flowsheet(
    project: Project,
    payload: schemas.FlowsheetCreate,
    user: User,
    repository: PlantVersionRepository,
    activity: ActivityRepository,
    blobs: BlobStore,
) -> schemas.Flowsheet:
    """Save the next plant version, then its layout if one came with it."""
    check_base(await repository.latest_version(project.id), payload.base)
    content = spec_of(payload)
    version = await repository.save_version(project.id, content, payload.note, user.id)
    if payload.layout is not None:
        await write_layout(blobs, project.id, payload.layout)
    await activity.add(
        project.id,
        "user",
        user.name,
        f"Saved plant version {version.number}",
        "design/plant",
        str(version.number),
    )
    return await build_flowsheet(version, blobs)


async def save_layout(
    project: Project,
    payload: schemas.LayoutUpdate,
    repository: PlantVersionRepository,
    blobs: BlobStore,
) -> schemas.Flowsheet:
    """Replace the node positions of the latest version; no new version is made."""
    latest = await latest_version(repository, project.id, PlantNotFoundError)
    check_base(latest, payload.base)
    await write_layout(blobs, project.id, payload.layout)
    return await build_flowsheet(latest, blobs)


def validate_spec(spec: dict[str, Any]) -> schemas.SpecProblems:
    """Return gemini's problems for a plant document."""
    return schemas.SpecProblems(problems=plant.problems_of(spec))


async def list_versions(
    project: Project,
    repository: PlantVersionRepository,
    users: UserRepository,
) -> Page[Version]:
    """List the versions of a project, newest first."""
    rows = await repository.list_versions(project.id)
    versions = await describe_versions(rows, users)
    return Page(items=versions[::-1], next=None)
