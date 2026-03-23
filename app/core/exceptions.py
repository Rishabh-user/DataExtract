"""Custom exception classes for the application."""

from typing import Any, Optional


class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500, detail: Optional[Any] = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.message)


class FileNotSupportedException(AppException):
    def __init__(self, file_type: str):
        super().__init__(
            message=f"File type '{file_type}' is not supported.",
            status_code=400,
        )


class FileTooLargeException(AppException):
    def __init__(self, size_mb: float, max_mb: int):
        super().__init__(
            message=f"File size {size_mb:.1f}MB exceeds maximum {max_mb}MB.",
            status_code=413,
        )


class ExtractionException(AppException):
    def __init__(self, message: str, detail: Optional[Any] = None):
        super().__init__(message=message, status_code=422, detail=detail)


class DocumentNotFoundException(AppException):
    def __init__(self, document_id: int):
        super().__init__(
            message=f"Document with id {document_id} not found.",
            status_code=404,
        )


class AuthenticationException(AppException):
    def __init__(self, message: str = "Invalid or missing API key."):
        super().__init__(message=message, status_code=401)


class SearchException(AppException):
    def __init__(self, message: str = "Search operation failed."):
        super().__init__(message=message, status_code=500)
