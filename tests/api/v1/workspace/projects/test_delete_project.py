from src.core.clients.postgres.repositories.case_file import CaseFileRepository
from src.core.clients.postgres.repositories.case_version import CaseVersionRepository
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from tests.cases import example_case
from tests.conftest import bearer

PROJECTS = "/api/v1/workspace/projects"


async def test_owner_deletes_project(client, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)
    headers = bearer(owner)

    response = await client.delete(f"{PROJECTS}/{project.id}", headers=headers)

    assert response.status_code == 204
    gone = await client.get(f"{PROJECTS}/{project.id}", headers=headers)
    assert gone.status_code == 404


async def test_other_member_cannot_delete(client, make_user, make_project) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    project = await make_project(owner)

    response = await client.delete(
        f"{PROJECTS}/{project.id}",
        headers=bearer(other),
    )

    assert response.status_code == 404
    still_there = await client.get(f"{PROJECTS}/{project.id}", headers=bearer(owner))
    assert still_there.status_code == 200


async def test_delete_removes_the_projects_stored_bytes_and_only_those(
    client, make_user, make_project, session, blobs
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    other = await make_project(owner)
    version = await CaseVersionRepository(session).save_version(
        project.id, example_case(), "Case", owner.id
    )
    await CaseFileRepository(session).add(
        project.id, version.id, "demand.csv", 1, f"case/{project.id}/abc"
    )
    await RagDocumentRepository(session).create(
        project.id,
        "notes.txt",
        1,
        f"projects/{project.id}/documents/x/notes.txt",
        owner.id,
    )
    for key in (
        f"case/{project.id}/abc",
        f"projects/{project.id}/documents/x/notes.txt",
        f"plant/{project.id}/layout.json",
        f"plant/{other.id}/layout.json",
    ):
        await blobs.put(key, b"x")

    response = await client.delete(f"{PROJECTS}/{project.id}", headers=bearer(owner))

    assert response.status_code == 204
    assert list(blobs.objects) == [f"plant/{other.id}/layout.json"]
