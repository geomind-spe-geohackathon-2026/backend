from starlette import status

from src.core.errors import AppError


class PlantInvalidError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = "plant_invalid"
