"""Names of the objects the backend keeps in the bucket."""

from uuid import UUID


def layout_key(project_id: UUID) -> str:
    """Return the key of a project's flowsheet layout."""
    return f"plant/{project_id}/layout.json"
