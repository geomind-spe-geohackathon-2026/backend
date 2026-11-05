from src.core.errors import NotFoundError


class StudyNotFoundError(NotFoundError):
    code = "study_not_found"


class StructuresNotFoundError(NotFoundError):
    """The study is not an evolve study, or its result holds no structures."""

    code = "structures_not_found"
