import json
from uuid import uuid4

from starlette.testclient import TestClient

from src.core.clients.postgres.repositories.run_event import RunEventRepository
from src.core.clients.redis.models.revoked_access_token import RevokedAccessToken
from src.core.clients.redis.repositories.revoked_access_token import (
    RevokedAccessTokenRepository,
)
from src.core.security.jwt import create_token_pair, decode_access_token
from src.fastapi import app
from tests.api.v1.assistant.conftest import run_url
from tests.api.v1.assistant.recorded import play


def stream_url(run_id) -> str:
    return run_url(run_id, "/stream")


def token_of(user) -> str:
    return create_token_pair(user.id).access_token


def closing_code(run_id, hello: dict) -> int:
    with TestClient(app).websocket_connect(stream_url(run_id)) as socket:
        socket.send_text(json.dumps(hello))
        return socket.receive()["code"]


async def store(session, run, events) -> None:
    repository = RunEventRepository(session)
    for event in events:
        await repository.add(
            run.id, event.sequence, event.type, event.is_public, event.to_dict()
        )


async def test_socket_sends_what_the_sse_stream_sends_and_closes(
    client, session, make_user, make_project, make_chat, make_run
) -> None:
    user = await make_user()
    project = await make_project(user)
    chat = await make_chat(project, user)
    run = await make_run(chat, user, status="done")
    await store(session, run, await play(run.id))

    with TestClient(app).websocket_connect(stream_url(run.id)) as socket:
        socket.send_text(json.dumps({"token": token_of(user), "after": 20}))
        frames = []
        while True:
            message = socket.receive()
            if message["type"] == "websocket.close":
                break
            frames.append(json.loads(message["text"]))

    assert message["code"] == 1000
    assert frames[0]["id"] > 20
    assert frames[-1]["event"] == "run.finished"
    assert frames[-1]["data"]["parent"] is None
    assert [frame["id"] for frame in frames] == sorted(frame["id"] for frame in frames)


async def test_a_bad_token_is_refused_with_its_own_code(
    client, make_user, make_project, make_chat, make_run
) -> None:
    user = await make_user()
    run = await make_run(await make_chat(await make_project(user), user), user)
    assert closing_code(run.id, {"token": "not-a-token"}) == 4401


async def test_a_revoked_token_is_refused(
    client, redis, make_user, make_project, make_chat, make_run
) -> None:
    user = await make_user()
    run = await make_run(await make_chat(await make_project(user), user), user)
    token = token_of(user)
    claims = decode_access_token(token)
    await RevokedAccessTokenRepository(redis).revoke(
        RevokedAccessToken(claims.token_id, claims.expires_at)
    )
    assert closing_code(run.id, {"token": token}) == 4401


async def test_an_inactive_user_is_refused(
    client, make_user, make_project, make_chat, make_run
) -> None:
    user = await make_user(active=False)
    run = await make_run(await make_chat(await make_project(user), user), user)
    assert closing_code(run.id, {"token": token_of(user)}) == 4401


async def test_a_run_of_someone_else_looks_missing(
    client, make_user, make_project, make_chat, make_run
) -> None:
    owner = await make_user()
    other = await make_user("other@example.com")
    run = await make_run(await make_chat(await make_project(owner), owner), owner)
    assert closing_code(run.id, {"token": token_of(other)}) == 4404
    assert closing_code(uuid4(), {"token": token_of(other)}) == 4404
