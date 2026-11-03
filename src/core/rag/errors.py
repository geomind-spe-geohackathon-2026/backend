from src.core.errors import NotFoundError


class RagDocumentNotFoundError(NotFoundError):
    code = "rag_document_not_found"
