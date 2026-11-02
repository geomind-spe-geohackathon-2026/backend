from unittest.mock import patch
from uuid import UUID, uuid4

from src.api.v1.workspace.documents import services
from src.core.clients.postgres.repositories.document import DocumentRepository
from tests.conftest import bearer

DOCUMENTS = "/api/v1/workspace/documents"


async def upload(client, user, project, name: str = "notes.txt", data: bytes = b"heat"):
    with patch.object(services, "enqueue_extraction") as enqueue:
        response = await client.post(
            DOCUMENTS,
            data={"project": str(project.id)},
            files={"file": (name, data, "text/plain")},
            headers=bearer(user),
        )
    return response, enqueue


async def test_upload_stores_the_file_and_queues_extraction(
    client,
    make_user,
    make_project,
    minio,
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response, enqueue = await upload(client, owner, project, "..\\dir/notes.txt")

    assert response.status_code == 201
    body = response.json()
    assert set(body) == {"id", "project", "name", "size", "searchable", "created"}
    assert body["name"] == "notes.txt"
    assert body["size"] == 4
    assert body["searchable"] == "pending"
    assert list(minio.objects.values()) == [b"heat"]
    enqueue.assert_called_once_with(UUID(body["id"]))


async def test_list_shows_the_project_documents(
    client,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    await upload(client, owner, project)

    response = await client.get(
        DOCUMENTS, params={"project": str(project.id)}, headers=bearer(owner)
    )

    assert [item["name"] for item in response.json()["items"]] == ["notes.txt"]
    assert response.json()["next"] is None


async def test_stranger_sees_a_missing_project(client, make_user, make_project) -> None:
    owner = await make_user()
    stranger = await make_user("other@example.com")
    project = await make_project(owner)

    listed = await client.get(
        DOCUMENTS, params={"project": str(project.id)}, headers=bearer(stranger)
    )
    uploaded, enqueue = await upload(client, stranger, project)

    assert listed.json()["error"]["code"] == "project_not_found"
    assert uploaded.status_code == 404
    enqueue.assert_not_called()


async def test_upload_needs_a_file_name(client, make_user, make_project) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response, _ = await upload(client, owner, project, name="dir/..")

    assert response.status_code == 422


async def test_delete_removes_row_and_bytes(
    client,
    make_user,
    make_project,
    minio,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    created, _ = await upload(client, owner, project)
    document_id = created.json()["id"]

    response = await client.delete(f"{DOCUMENTS}/{document_id}", headers=bearer(owner))

    assert response.status_code == 204
    assert minio.objects == {}
    listed = await client.get(
        DOCUMENTS, params={"project": str(project.id)}, headers=bearer(owner)
    )
    assert listed.json()["items"] == []


async def test_delete_hides_documents_of_other_projects(
    client,
    make_user,
    make_project,
) -> None:
    owner = await make_user()
    stranger = await make_user("other@example.com")
    project = await make_project(owner)
    created, _ = await upload(client, owner, project)

    other = await client.delete(
        f"{DOCUMENTS}/{created.json()['id']}", headers=bearer(stranger)
    )
    missing = await client.delete(f"{DOCUMENTS}/{uuid4()}", headers=bearer(owner))

    assert other.status_code == 404
    assert other.json()["error"]["code"] == "document_not_found"
    assert missing.json()["error"]["code"] == "document_not_found"


async def test_extraction_makes_a_text_document_searchable(
    client,
    make_user,
    make_project,
    minio,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    created, _ = await upload(client, owner, project, data=b"hot brine")
    repository = DocumentRepository(session)

    await services.extract_document(UUID(created.json()["id"]), repository, minio)

    document = await repository.get_by_id(UUID(created.json()["id"]))
    assert document.searchable == "ready"
    assert document.text == "hot brine"


async def test_extraction_marks_an_unreadable_file_failed(
    client,
    make_user,
    make_project,
    minio,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    created, _ = await upload(client, owner, project, name="scan.pdf", data=b"%PDF")
    repository = DocumentRepository(session)

    await services.extract_document(UUID(created.json()["id"]), repository, minio)

    document = await repository.get_by_id(UUID(created.json()["id"]))
    assert document.searchable == "failed"
    assert document.text is None


async def test_extraction_of_a_deleted_document_does_nothing(session, minio) -> None:
    await services.extract_document(uuid4(), DocumentRepository(session), minio)
