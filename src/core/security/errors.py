from starlette import status

from src.core.errors import AppError


class TokenValidationError(AppError, ValueError):
    pass


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED

    def __init__(self, detail: str) -> None:
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"})


class AuthenticationUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
