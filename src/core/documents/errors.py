from src.core.errors import NotFoundError


class DocumentNotFoundError(NotFoundError):
    code = "document_not_found"
