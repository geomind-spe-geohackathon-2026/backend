"""The routes of the frontend, project-relative, for checking activity links.

A case or plant version row links to its number and a study row to its id (QA-102); the
frontend opens History on that version, and the study.
"""

FRONTEND_ROUTES = {
    "overview": False,
    "assistant/chat": True,
    "assistant/runs": True,
    "design/case": True,
    "design/plant": True,
    "design/study": True,
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
