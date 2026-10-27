from pydantic import BaseModel
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from fastapi import Request


class AppError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        detail: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.headers = headers


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN


class ErrorResponse(BaseModel):
    detail: str


class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppError as error:
            body = ErrorResponse(detail=error.detail)
            return Response(
                status_code=error.status_code,
                content=body.model_dump_json(),
                media_type="application/json",
                headers=error.headers,
            )
