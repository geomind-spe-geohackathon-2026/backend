"""The routes of the frontend, project-relative, for checking activity links."""

FRONTEND_ROUTES = {
    "overview": False,
    "assistant/chat": True,
    "assistant/runs": True,
    "design/case": False,
    "design/plant": False,
    "design/study": False,
    "design/results": True,
    "design/report": False,
    "documents": False,
    "settings": False,
}


def route_exists(route: str | None, link_id: str | None) -> bool:
    """Tell whether the frontend has the route and takes the id, if any."""
    if route not in FRONTEND_ROUTES:
        return False
    return link_id is None or FRONTEND_ROUTES[route]
