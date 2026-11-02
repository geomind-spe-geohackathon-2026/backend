from src.core.errors import NotFoundError


class StudyNotFoundError(NotFoundError):
    code = "study_not_found"
