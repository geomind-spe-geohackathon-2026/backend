from tests.conftest import bearer


async def test_a_project_counts_its_chats_and_runs(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    project = await make_project(owner)
    chat = await make_chat(project, owner)
    await make_chat(project, owner)
    await make_run(chat, owner)

    response = await client.get(
        f"/api/v1/workspace/projects/{project.id}", headers=bearer(owner)
    )

    assert (response.json()["chats"], response.json()["runs"]) == (2, 1)
