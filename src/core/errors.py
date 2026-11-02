import logging
from typing import Any

from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from starlette import status
from starlette.exceptions import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from fastapi import FastAPI, Request

logger = logging.getLogger("geomind.core.errors")

HTTP_ERROR_CODES = {
    status.HTTP_401_UNAUTHORIZED: "unauthorized",
    status.HTTP_403_FORBIDDEN: "forbidden",
    status.HTTP_404_NOT_FOUND: "not_found",
    status.HTTP_405_METHOD_NOT_ALLOWED: "not_found",
}


class AppError(Exception):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal"

    def __init__(
        self,
        message: str,
        headers: dict[str, str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.headers = headers
        self.details = details or {}


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "forbidden"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"


class ValidationFailedError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "validation_failed"

    def __init__(self, fields: dict[str, str]) -> None:
        super().__init__("Request validation failed", details={"fields": fields})


class CaseInvalidError(AppError):
    """A case document gemini refuses; ``details.problems`` is gemini's list."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "case_invalid"

    def __init__(self, problems: list[dict[str, Any]]) -> None:
        super().__init__("Case is invalid", details={"problems": problems})


class MissingInputsError(AppError):
    """A request that needs values nobody has given; each item is path and message."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "missing_inputs"

    def __init__(self, missing: list[dict[str, str]]) -> None:
        super().__init__("Inputs are missing", details={"missing": missing})


class NotImplementedYetError(AppError):
    """A route whose gemini or geomind part does not exist yet."""

    status_code = status.HTTP_501_NOT_IMPLEMENTED
    code = "not_implemented"

    def __init__(self, missing: str) -> None:
        super().__init__(
            "This is not available yet",
            details={"missing": missing},
        )


class HTTPFailureError(AppError):
    def __init__(self, error: HTTPException) -> None:
        super().__init__(str(error.detail), headers=error.headers)
        self.status_code = error.status_code
        self.code = HTTP_ERROR_CODES.get(error.status_code, "internal")


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any]


class ErrorResponse(BaseModel):
    error: ErrorBody


def error_response(error: AppError) -> Response:
    body = ErrorBody(code=error.code, message=error.message, details=error.details)
    return Response(
        status_code=error.status_code,
        content=ErrorResponse(error=body).model_dump_json(),
        media_type="application/json",
        headers=error.headers,
    )


def validation_field(location: tuple[str | int, ...]) -> str:
    """Name a failed field by its path, without the request part it arrived in."""
    path = location[1:] or location
    return ".".join(str(part) for part in path)


async def raise_validation_failed(
    _request: Request,
    error: RequestValidationError,
) -> None:
    fields = {validation_field(item["loc"]): item["msg"] for item in error.errors()}
    raise ValidationFailedError(fields)


async def raise_http_failure(_request: Request, error: HTTPException) -> None:
    raise HTTPFailureError(error)


def include_exception_handlers(app: FastAPI) -> None:
    """Send framework errors through ErrorMiddleware, so every body has one shape."""
    app.add_exception_handler(RequestValidationError, raise_validation_failed)
    app.add_exception_handler(HTTPException, raise_http_failure)


class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except AppError as error:
            return error_response(error)
        except Exception:
            logger.exception("%s %s failed", request.method, request.url.path)
            return error_response(AppError("Internal server error"))
