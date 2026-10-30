from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from src.core.clients.postgres.repositories.user import (
    UserRepository,
    get_user_repository,
)
from src.core.security.access import current_user
from src.core.security.jwt import create_token_pair, decode_access_token
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

    assert "/api/v1/identity/authn/login" in paths
    assert "/api/v1/identity/authn/refresh" in paths
    assert "/api/v1/identity/authn/logout" in paths
    assert "/api/v1/identity/authn/signup" not in paths
    assert "/api/v1/identity/authn/forgot-password" not in paths


def test_app_error_is_returned_as_json() -> None:
    repository = AsyncMock(spec=UserRepository)
    repository.get_by_email.return_value = None
    redis = AsyncMock()
    redis.incr.return_value = 1
    app.dependency_overrides[get_user_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            client.app.state.redis = redis
            response = client.post(
                "/api/v1/identity/authn/login",
                json={"email": "user@example.com", "password": "correct-password"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "Invalid email or password",
            "details": {},
        }
    }


def test_protected_route_requires_token() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/identity/authn/logout")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_logout_revokes_valid_token() -> None:
    token = create_token_pair(uuid4()).access_token
    claims = decode_access_token(token)
    redis = AsyncMock()
    redis.exists.return_value = 0
    redis.incr.return_value = 1

    app.dependency_overrides[current_user] = object
    try:
        with TestClient(app) as client:
            client.app.state.redis = redis
            response = client.post(
                "/api/v1/identity/authn/logout",
                headers={"Authorization": f"Bearer {token}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    redis.exists.assert_awaited_once()
    revoked = [call.args[0] for call in redis.set.await_args_list]
    assert revoked == [
        f"revoked_access_token:{claims.token_id}",
        f"revoked_access_token:{claims.refresh_token_id}",
    ]
    assert all(call.kwargs["ex"] > 0 for call in redis.set.await_args_list)


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


def test_rate_limit_returns_too_many_requests() -> None:
    redis = AsyncMock()
    redis.incr.return_value = settings.RATE_LIMIT_REQUESTS + 1

    with TestClient(app) as client:
        client.app.state.redis = redis
        response = client.post(
            "/api/v1/identity/authn/login",
            json={"email": "user@example.com", "password": "correct-password"},
        )

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "rate_limited"
    assert response.headers["x-ratelimit-remaining"] == "0"
    assert int(response.headers["retry-after"]) > 0
