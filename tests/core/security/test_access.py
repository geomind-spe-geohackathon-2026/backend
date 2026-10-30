from uuid import uuid4

import pytest

from src.core.clients.postgres.repositories.project import ProjectRepository
from src.core.security.access import require_project
from src.core.security.errors import ProjectNotFoundError
from tests.conftest import bearer

USERS = "/api/v1/identity/users"


async def test_admin_passes_admin_route(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin")

    response = await client.get(USERS, headers=bearer(admin))

    assert response.status_code == 200


async def test_member_is_forbidden_on_admin_route(client, make_user) -> None:
    member = await make_user()

    response = await client.get(USERS, headers=bearer(member))

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_token_of_inactive_user_is_refused(client, make_user) -> None:
    admin = await make_user("admin@example.com", role="admin", active=False)

    response = await client.get(USERS, headers=bearer(admin))

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


@pytest.fixture
async def project_setup(make_user, session):
    owner = await make_user("owner@example.com")
    repository = ProjectRepository(session)
    project = await repository.create("Doublet", owner.id)
    return owner, project, repository


async def test_owner_gets_their_project(project_setup) -> None:
    owner, project, repository = project_setup

    assert (await require_project(project.id, owner, repository)).id == project.id


async def test_admin_gets_any_project(project_setup, make_user) -> None:
    _, project, repository = project_setup
    admin = await make_user("admin@example.com", role="admin")

    assert (await require_project(project.id, admin, repository)).id == project.id


async def test_other_member_gets_the_missing_project_error(
    project_setup,
    make_user,
) -> None:
    _, project, repository = project_setup
    other = await make_user("other@example.com")

    with pytest.raises(ProjectNotFoundError):
        await require_project(project.id, other, repository)


async def test_missing_project_is_not_found(project_setup) -> None:
    owner, _, repository = project_setup

    with pytest.raises(ProjectNotFoundError):
        await require_project(uuid4(), owner, repository)
