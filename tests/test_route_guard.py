"""Every route needs a signed-in user, unless its path is explicitly public."""

from collections.abc import Iterable, Iterator
from typing import Any

from fastapi.dependencies.models import Dependant
from fastapi.routing import iter_route_contexts

from fastapi import Depends, FastAPI
from src.core.security.access import CurrentUser, current_user
from src.core.security.paths import PUBLIC_PATHS
from src.fastapi import app

PUBLIC_API_PATHS = {
    "/api/v1/identity/authn/login",
    "/api/v1/identity/authn/refresh",
    "/api/v1/system/health",
}


def dependency_calls(dependant: Dependant) -> Iterator[object]:
    for dependency in dependant.dependencies:
        yield dependency.call
        yield from dependency_calls(dependency)


def api_routes(routes: Iterable[object]) -> list[Any]:
    """List every API route, including those of included routers."""
    return list(iter_route_contexts(routes))


def unguarded_routes(routes: Iterable[object]) -> list[str]:
    """Name every route that neither needs a user nor is public."""
    found = []
    for route in api_routes(routes):
        if route.path in PUBLIC_PATHS:
            continue
        if current_user not in dependency_calls(route.dependant):
            methods = ",".join(sorted(route.methods))
            found.append(f"{methods} {route.path}")
    return found


def test_every_route_needs_a_user_or_is_public() -> None:
    assert unguarded_routes(app.routes) == []


def test_guard_sees_every_documented_route() -> None:
    checked = {route.path for route in api_routes(app.routes)}

    assert checked >= set(app.openapi()["paths"])
    assert "/api/v1/workspace/projects/{project_id}" in checked


def test_public_api_paths_are_exactly_these() -> None:
    public = {path for path in PUBLIC_PATHS if path.startswith("/api/")}

    assert public == PUBLIC_API_PATHS


def test_guard_names_an_unprotected_route() -> None:
    probe = FastAPI()

    @probe.get("/api/v1/open")
    async def open_route() -> None:
        return None

    assert "GET /api/v1/open" in unguarded_routes(probe.routes)


def test_guard_sees_a_nested_dependency() -> None:
    probe = FastAPI()

    def nested(user: CurrentUser) -> object:
        return user

    @probe.get("/api/v1/closed", dependencies=[Depends(nested)])
    async def closed_route() -> None:
        return None

    assert "GET /api/v1/closed" not in unguarded_routes(probe.routes)
