"""Reading uploaded files with the size limit all uploads share."""

from fastapi import UploadFile
from src.core.errors import ValidationFailedError
from src.core.settings import settings


async def read_upload(file: UploadFile) -> bytes:
    """Read an uploaded file, or raise validation_failed when it is too large."""
    data = await file.read(settings.PROJECT_IMPORT_MAX_BYTES + 1)
    if len(data) > settings.PROJECT_IMPORT_MAX_BYTES:
        raise ValidationFailedError({"file": "File is too large"})
    return data
