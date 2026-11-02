from src.core.errors import NotFoundError


class ResultNotFoundError(NotFoundError):
    code = "result_not_found"
