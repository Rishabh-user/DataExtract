"""Pydantic schemas for all API request/response models."""

from typing import Any, Optional

from pydantic import BaseModel, Field

ALL_ACTIONS = ["upload", "search", "filter", "view"]
ALL_FILE_TYPES = [
    ".pdf", ".xlsx", ".xls", ".docx", ".doc",
    ".eml", ".msg", ".csv", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
]


# ─── Upload ───────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    status: str
    project_name: str
    message: str


# ─── Document ─────────────────────────────────────────────────────────────────

class PageSchema(BaseModel):
    id: int
    page_number: Optional[int]
    content: str
    metadata: Optional[dict[str, Any]]
    created_at: str


class DocumentResponse(BaseModel):
    id: int
    file_name: str
    file_type: str
    source: Optional[str]
    upload_date: str
    status: str
    file_size_bytes: Optional[int]
    project_name: Optional[str] = None
    pages: list[PageSchema]


# ─── Filter ───────────────────────────────────────────────────────────────────

class DocumentSummary(BaseModel):
    id: int
    file_name: str
    file_type: str
    source: Optional[str]
    upload_date: str
    status: str
    file_size_bytes: Optional[int]


class FilterResponse(BaseModel):
    page: int
    size: int
    total: int
    results: list[DocumentSummary]


# ─── Search ───────────────────────────────────────────────────────────────────

class SearchHit(BaseModel):
    document_id: int
    file_name: str
    file_type: str
    source: Optional[str]
    page_number: Optional[int]
    content_snippet: str
    score: Optional[float]


class SearchResponse(BaseModel):
    query: str
    total: int
    page: int
    size: int
    results: list[SearchHit]


# ─── API Key ──────────────────────────────────────────────────────────────────

class GenerateKeyRequest(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=255)
    allowed_actions: list[str] = Field(
        default=ALL_ACTIONS,
        description="Actions this key can perform: upload, search, filter, view",
    )
    allowed_file_types: list[str] = Field(
        default=["*"],
        description="File types allowed for upload. Use ['*'] for all.",
    )
    db_url: Optional[str] = Field(
        default=None,
        description=(
            "Optional: custom database URL for this project. "
            "Use for remote databases, e.g. postgresql+asyncpg://user:pass@host:5432/db. "
            "If omitted, a local SQLite database is created automatically."
        ),
    )


class KeyPermissions(BaseModel):
    actions: list[str]
    file_types: list[str]


class APIKeyResponse(BaseModel):
    id: int
    project_name: str
    api_key: Optional[str] = None     # only returned on creation
    permissions: Optional[dict[str, Any]]
    created_at: str
    status: str


class GenerateKeyResponse(APIKeyResponse):
    api_key: str
    message: str


class RevokeKeyResponse(BaseModel):
    id: int
    message: str


class UpdateKeyRequest(BaseModel):
    allowed_actions: Optional[list[str]] = None
    allowed_file_types: Optional[list[str]] = None
    status: Optional[str] = None      # "active" or "revoked"


# ─── Stats ────────────────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    project_name: Optional[str] = None
    total_documents: int
    completed: int
    failed: int
    pending: int
    total_pages_extracted: int
    active_keys: int
    file_type_breakdown: dict[str, int]


# ─── Email ────────────────────────────────────────────────────────────────────

class SendEmailRequest(BaseModel):
    to: str = Field(..., description="Recipient email address")
    template: str = Field(..., description="Template name: extraction_summary | api_key_created | welcome")
    document_id: Optional[int] = None
    project_name: Optional[str] = None
    api_key_preview: Optional[str] = None


class SendEmailResponse(BaseModel):
    success: bool
    message: str
    backend: str


# ─── Admin DB ─────────────────────────────────────────────────────────────────

class TableRow(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    total: int


# ─── Admin Login ──────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., description="Admin username")
    password: str = Field(..., description="Admin password")


class LoginResponse(BaseModel):
    token: str        # the superadmin API key stored in localStorage
    message: str


# ─── Error ────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
