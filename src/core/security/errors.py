from starlette import status

from src.core.errors import AppError, NotFoundError


class TokenValidationError(AppError, ValueError):
    pass


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthorized"

    def __init__(self, message: str) -> None:
        super().__init__(message, headers={"WWW-Authenticate": "Bearer"})


class AuthenticationUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE


class ProjectNotFoundError(NotFoundError):
    code = "project_not_found"
