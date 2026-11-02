from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from fastapi import FastAPI
from src.core.errors import (
    CaseInvalidError,
    ConflictError,
    ErrorMiddleware,
    MissingInputsError,
    NotImplementedYetError,
    include_exception_handlers,
)
from src.core.settings import settings
from src.fastapi import app as real_app


class Payload(BaseModel):
    name: str
    size: int


def error_app() -> FastAPI:
    app = FastAPI()
    include_exception_handlers(app)
    app.add_middleware(ErrorMiddleware)

    @app.get("/conflict")
    async def conflict() -> None:
        raise ConflictError("Already there", details={"id": 1})

    @app.get("/not-implemented")
    async def not_implemented() -> None:
        raise NotImplementedYetError("gm.evaluate.coverage")

    @app.get("/case-invalid")
    async def case_invalid() -> None:
        raise CaseInvalidError(
            [{"path": "time", "code": "invalid_value", "message": "x"}]
        )

    @app.get("/missing-inputs")
    async def missing_inputs() -> None:
        raise MissingInputsError(
            [{"path": "demand.heating.power", "message": "missing"}]
        )

    @app.get("/crash")
    async def crash() -> None:
        raise RuntimeError("secret-token")

    @app.post("/payload")
    async def payload(body: Payload) -> None:
        return None

    return app


def client_for(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_app_error_uses_contract_body() -> None:
    async with client_for(error_app()) as client:
        response = await client.get("/conflict")

    assert response.status_code == 409
    assert response.json() == {
        "error": {"code": "conflict", "message": "Already there", "details": {"id": 1}}
    }


async def test_not_implemented_names_what_is_missing() -> None:
    async with client_for(error_app()) as client:
        response = await client.get("/not-implemented")

    assert response.status_code == 501
    assert response.json()["error"] == {
        "code": "not_implemented",
        "message": "This is not available yet",
        "details": {"missing": "gm.evaluate.coverage"},
    }


async def test_case_invalid_carries_gemini_problems() -> None:
    async with client_for(error_app()) as client:
        response = await client.get("/case-invalid")

    error = response.json()["error"]
    assert (response.status_code, error["code"]) == (422, "case_invalid")
    assert error["details"]["problems"][0]["path"] == "time"


async def test_missing_inputs_lists_path_and_message() -> None:
    async with client_for(error_app()) as client:
        response = await client.get("/missing-inputs")

    error = response.json()["error"]
    assert (response.status_code, error["code"]) == (422, "missing_inputs")
    assert error["details"]["missing"] == [
        {"path": "demand.heating.power", "message": "missing"}
    ]


async def test_validation_error_names_each_field() -> None:
    async with client_for(error_app()) as client:
        response = await client.post("/payload", json={"size": "big"})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "validation_failed"
    assert set(error["details"]["fields"]) == {"name", "size"}


async def test_unknown_route_is_not_found() -> None:
    async with client_for(error_app()) as client:
        response = await client.get("/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


async def test_unhandled_error_hides_its_message() -> None:
    async with client_for(error_app()) as client:
        response = await client.get("/crash")

    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal"
    assert "secret-token" not in response.text


async def test_error_responses_carry_cors_headers() -> None:
    origin = settings.APP_CORS_ORIGINS[0]
    async with client_for(real_app) as client:
        response = await client.get(
            "/api/v1/identity/me",
            headers={"Origin": origin},
        )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert response.headers["access-control-allow-origin"] == origin
