from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from fastapi.testclient import TestClient

from src.celery import app as celery_app
from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.security.jwt import create_access_token, decode_access_token
from src.core.settings import settings
from src.fastapi import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/system/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_uses_application_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "swarmax-backend"


def test_openapi_has_identity_routes() -> None:
    with TestClient(app) as client:
        paths = client.get("/openapi.json").json()["paths"]

    assert "/api/v1/identity/authn/signup" in paths
    assert "/api/v1/identity/authn/signin" in paths
    assert "/api/v1/identity/authn/signout" in paths
    assert "/api/v1/identity/authn/forgot-password" in paths


def test_app_error_is_returned_as_json() -> None:
    repository = AsyncMock(spec=UserRepository)
    repository.get_by_email.return_value = object()
    redis = AsyncMock()
    redis.incr.return_value = 1
    app.dependency_overrides[get_user_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            client.app.state.redis = redis
            response = client.post(
                "/api/v1/identity/authn/signup",
                json={"email": "user@example.com", "password": "correct-password"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "conflict",
            "message": "Email is already registered",
            "details": {},
        }
    }


def test_protected_route_requires_token() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/identity/authn/signout")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_signout_revokes_valid_token() -> None:
    token = create_access_token(uuid4())
    claims = decode_access_token(token)
    redis = AsyncMock()
    redis.exists.return_value = 0
    redis.incr.return_value = 1

    with TestClient(app) as client:
        client.app.state.redis = redis
        response = client.post(
            "/api/v1/identity/authn/signout",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 204
    redis.exists.assert_awaited_once()
    redis.set.assert_awaited_once()
    assert redis.set.call_args.args[:2] == (
        f"revoked_access_token:{claims.token_id}",
        "1",
    )
    assert redis.set.call_args.kwargs["ex"] > 0


def test_cors_preflight() -> None:
    origin = settings.APP_CORS_ORIGINS[0]
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/system/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_delete_me_queues_account_deletion(monkeypatch) -> None:
    user_id = uuid4()
    token = create_access_token(user_id)
    redis = AsyncMock()
    redis.exists.return_value = 0
    redis.incr.return_value = 1
    send_task = MagicMock()
    monkeypatch.setattr(celery_app, "send_task", send_task)

    with TestClient(app) as client:
        client.app.state.redis = redis
        response = client.delete(
            "/api/v1/identity/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 202
    assert response.json() == {"message": "Account deletion has been scheduled"}
    send_task.assert_called_once_with(
        "identity.me.delete_account",
        args=[str(user_id)],
    )


def test_rate_limit_returns_too_many_requests() -> None:
    redis = AsyncMock()
    redis.incr.return_value = settings.RATE_LIMIT_REQUESTS + 1

    with TestClient(app) as client:
        client.app.state.redis = redis
        response = client.post(
            "/api/v1/identity/authn/forgot-password",
            json={"email": "user@example.com"},
        )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert int(response.headers["retry-after"]) > 0
