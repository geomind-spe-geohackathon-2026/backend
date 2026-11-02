"""Errors for what gemini refuses or cannot find."""

from starlette import status

from src.core.errors import AppError, NotFoundError


class PlantInvalidError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "plant_invalid"


class PlantNotFoundError(NotFoundError):
    code = "plant_not_found"


class PlantModuleNotFoundError(NotFoundError):
    code = "module_not_found"


class CaseNotFoundError(NotFoundError):
    code = "case_not_found"


class CaseFileNotFoundError(NotFoundError):
    code = "case_file_not_found"
