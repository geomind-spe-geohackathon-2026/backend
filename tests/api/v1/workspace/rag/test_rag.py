from unittest.mock import patch
from uuid import UUID, uuid4

import pytest

from src.api.v1.workspace.rag import services
from src.core.clients.postgres.repositories.rag_document import RagDocumentRepository
from tests.conftest import bearer

DOCUMENTS = "/api/v1/workspace/rag"


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
    blobs,
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
    assert list(blobs.objects.values()) == [b"heat"]
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
    blobs,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    created, _ = await upload(client, owner, project)
    document_id = created.json()["id"]

    response = await client.delete(f"{DOCUMENTS}/{document_id}", headers=bearer(owner))

    assert response.status_code == 204
    assert blobs.objects == {}
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
    assert other.json()["error"]["code"] == "rag_document_not_found"
    assert missing.json()["error"]["code"] == "rag_document_not_found"


async def test_extraction_makes_a_text_document_searchable(
    client,
    make_user,
    make_project,
    blobs,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    created, _ = await upload(client, owner, project, data=b"hot brine")
    repository = RagDocumentRepository(session)

    await services.extract_document(UUID(created.json()["id"]), repository, blobs)

    document = await repository.get_by_id(UUID(created.json()["id"]))
    assert document.searchable == "ready"
    assert document.text == "hot brine"


async def test_extraction_marks_an_unreadable_file_failed(
    client,
    make_user,
    make_project,
    blobs,
    session,
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    created, _ = await upload(client, owner, project, name="scan.pdf", data=b"%PDF")
    repository = RagDocumentRepository(session)

    await services.extract_document(UUID(created.json()["id"]), repository, blobs)

    document = await repository.get_by_id(UUID(created.json()["id"]))
    assert document.searchable == "failed"
    assert document.text is None


async def test_extraction_of_a_deleted_document_does_nothing(session, blobs) -> None:
    await services.extract_document(uuid4(), RagDocumentRepository(session), blobs)


async def test_upload_refuses_a_type_that_cannot_be_read(
    client, make_user, make_project
) -> None:
    owner = await make_user()
    project = await make_project(owner)

    response, enqueue = await upload(client, owner, project, name="bad.exe", data=b"MZ")

    assert response.status_code == 422
    assert ".pdf" in response.json()["error"]["details"]["fields"]["file"]
    enqueue.assert_not_called()


async def test_formats_lists_the_suffixes_an_upload_may_have(client, make_user) -> None:
    user = await make_user()

    response = await client.get("/api/v1/workspace/rag/formats", headers=bearer(user))

    assert ".pdf" in response.json()
    assert ".txt" in response.json()


@pytest.fixture
def quiet():
    with patch.object(services, "enqueue_extraction"):
        yield


async def admin_of(make_user):
    return await make_user("admin@example.com", role="admin")


async def test_an_admin_adds_a_shared_knowledge_document_everyone_lists(
    client, make_user, make_project, quiet
) -> None:
    admin = await admin_of(make_user)
    member = await make_user()
    project = await make_project(member)
    await client.post(
        DOCUMENTS,
        data={"project": str(project.id)},
        files={"file": ("own.txt", b"own")},
        headers=bearer(member),
    )

    added = await client.post(
        DOCUMENTS, files={"file": ("standard.pdf", b"%PDF")}, headers=bearer(admin)
    )
    shared = await client.get(DOCUMENTS, headers=bearer(member))
    own = await client.get(
        DOCUMENTS, params={"project": str(project.id)}, headers=bearer(member)
    )

    assert added.status_code == 201, added.text
    assert added.json()["project"] is None
    assert [item["name"] for item in shared.json()["items"]] == ["standard.pdf"]
    assert [item["name"] for item in own.json()["items"]] == ["own.txt"]


async def test_only_an_admin_changes_the_shared_knowledge(
    client, make_user, quiet
) -> None:
    admin = await admin_of(make_user)
    member = await make_user()
    added = await client.post(
        DOCUMENTS, files={"file": ("standard.txt", b"x")}, headers=bearer(admin)
    )

    refused = await client.post(
        DOCUMENTS, files={"file": ("mine.txt", b"x")}, headers=bearer(member)
    )
    kept = await client.delete(
        f"{DOCUMENTS}/{added.json()['id']}", headers=bearer(member)
    )
    removed = await client.delete(
        f"{DOCUMENTS}/{added.json()['id']}", headers=bearer(admin)
    )

    assert refused.status_code == 403
    assert kept.status_code == 403
    assert removed.status_code == 204


async def test_a_file_is_shown_inline_and_safely(
    client, make_user, make_project
) -> None:
    owner = await make_user()
    stranger = await make_user("other@example.com")
    project = await make_project(owner)
    uploaded, _ = await upload(
        client, owner, project, "page.html", b"<script>x</script>"
    )
    assert uploaded.status_code == 422
    pdf, _ = await upload(client, owner, project, "brief.pdf", b"%PDF-1.4")
    path = f"{DOCUMENTS}/{pdf.json()['id']}"

    shown = await client.get(f"{path}/file", headers=bearer(owner))
    hidden = await client.get(f"{path}/file", headers=bearer(stranger))

    assert shown.status_code == 200
    assert shown.content == b"%PDF-1.4"
    assert shown.headers["content-type"] == "application/pdf"
    assert shown.headers["content-disposition"].startswith("inline;")
    assert shown.headers["x-content-type-options"] == "nosniff"
    assert shown.headers["content-security-policy"] == "sandbox"
    assert hidden.status_code == 404
    assert hidden.json()["error"]["code"] == "rag_document_not_found"


async def test_a_text_file_is_plain_text_and_its_read_text_is_given(
    client, session, make_user, make_project
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    data = b"<b>id,value</b>\npump,1"
    response, _ = await upload(client, owner, project, "costs.csv", data)
    document_id = response.json()["id"]
    repository = RagDocumentRepository(session)
    await repository.set_text(await repository.get_by_id(UUID(document_id)), "pump,1")

    shown = await client.get(f"{DOCUMENTS}/{document_id}/file", headers=bearer(owner))
    text = await client.get(f"{DOCUMENTS}/{document_id}/text", headers=bearer(owner))

    assert shown.headers["content-type"] == "text/plain; charset=utf-8"
    assert shown.content == data
    assert text.json() == {
        "id": document_id,
        "name": "costs.csv",
        "searchable": "ready",
        "text": "pump,1",
    }


async def test_everyone_may_view_a_shared_knowledge_file(
    client, make_user, quiet
) -> None:
    admin = await admin_of(make_user)
    member = await make_user()
    added = await client.post(
        DOCUMENTS, files={"file": ("standard.txt", b"norm")}, headers=bearer(admin)
    )

    shown = await client.get(
        f"{DOCUMENTS}/{added.json()['id']}/file", headers=bearer(member)
    )

    assert shown.content == b"norm"
