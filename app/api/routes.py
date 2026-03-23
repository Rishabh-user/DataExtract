"""API route definitions.

Every data route (upload, view, search, filter, stats) now operates on the
project-specific database resolved from the API key.
"""

from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import (
    APIKeyResponse, DocumentResponse, DashboardStats, ErrorResponse,
    FilterResponse, GenerateKeyRequest, GenerateKeyResponse, LoginRequest,
    LoginResponse, RevokeKeyResponse, SearchResponse, SendEmailRequest,
    SendEmailResponse, UpdateKeyRequest, UploadResponse,
)
from app.database.models import APIKey, Project
from app.database.session import get_db
from app.database.project_session import get_project_db
from app.security.auth import (
    ALL_ACTIONS, ALL_FILE_TYPES,
    build_permissions, check_action, check_file_type,
    create_api_key, validate_api_key,
)
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.services.email_service import email_service
from app.services.extraction_service import ExtractionService

router = APIRouter(prefix="/api")


# ─── Helper: get a project DB session from the validated API key ─────────────

async def _project_session(api_key: APIKey) -> AsyncSession:
    """Open an async session for the project linked to the API key."""
    project = api_key.project
    return await get_project_db(project.db_url, project.slug)


# ─── Admin Login ──────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=LoginResponse,
             summary="Superadmin login — returns API token for the session")
async def admin_login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    if body.username != settings.ADMIN_USERNAME or body.password != settings.ADMIN_PASSWORD:
        raise AppException("Invalid username or password.", status_code=401)

    # Find or create the permanent superadmin key
    result = await db.execute(select(APIKey).where(APIKey.project_name == "__superadmin__"))
    record = result.scalar_one_or_none()

    if not record:
        record = await create_api_key(
            db=db, project_name="__superadmin__",
            actions=ALL_ACTIONS, file_types=["*"],
        )
        record.permissions = {**record.permissions, "is_superadmin": True}
        await db.flush()
    elif record.status == "revoked":
        record.status = "active"
        await db.flush()

    return LoginResponse(token=record.api_key, message="Login successful. Welcome, Superadmin.")


# ─── Upload ───────────────────────────────────────────────────────────────────

@router.post("/upload", response_model=UploadResponse,
             responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
             summary="Upload a document — data stored in the project's own database")
async def upload_document(
    file: UploadFile = File(...),
    source: Optional[str] = Form(default=None),
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    check_action(api_key, "upload")
    content = await file.read()
    from pathlib import Path
    ext = Path(file.filename or "unknown").suffix.lower()
    check_file_type(api_key, ext)

    # Get a session for THIS project's database
    project_db = await _project_session(api_key)
    try:
        service = ExtractionService(project_db)
        document = await service.upload_and_extract(
            file_name=file.filename or "unknown",
            file_content=content,
            source=source,
        )
        await project_db.commit()
        return UploadResponse(
            id=document.id,
            file_name=document.file_name,
            file_type=document.file_type,
            status=document.status,
            project_name=api_key.project_name,
            message=f"Document uploaded and extracted into project '{api_key.project_name}'.",
        )
    except Exception:
        await project_db.rollback()
        raise
    finally:
        await project_db.close()


# ─── Document ─────────────────────────────────────────────────────────────────

@router.get("/document/{document_id}", response_model=DocumentResponse,
            responses={404: {"model": ErrorResponse}},
            summary="Get extracted content for a document (from project DB)")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    check_action(api_key, "view")

    project_db = await _project_session(api_key)
    try:
        result = await ExtractionService(project_db).get_document(document_id)
        result["project_name"] = api_key.project_name
        return result
    finally:
        await project_db.close()


# ─── Search ───────────────────────────────────────────────────────────────────

@router.get("/search", response_model=SearchResponse,
            summary="Full-text search within THIS project's data")
async def search_documents(
    q: str = Query(..., min_length=1),
    file_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    check_action(api_key, "search")

    project_db = await _project_session(api_key)
    try:
        return await ExtractionService(project_db).search_documents(
            query=q, file_type=file_type, source=source, page=page, size=size
        )
    finally:
        await project_db.close()


# ─── Filter ───────────────────────────────────────────────────────────────────

@router.get("/filter", response_model=FilterResponse,
            summary="Filter documents within THIS project's data")
async def filter_documents(
    file_type: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date_from: Optional[str] = Query(default=None),
    date_to: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    check_action(api_key, "filter")

    project_db = await _project_session(api_key)
    try:
        return await ExtractionService(project_db).filter_documents(
            file_type=file_type, source=source, status=status,
            date_from=date_from, date_to=date_to,
            page=page, size=size,
        )
    finally:
        await project_db.close()


# ─── Stats ────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=DashboardStats,
            summary="Dashboard statistics for THIS project")
async def get_stats(
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    project_db = await _project_session(api_key)
    try:
        stats = await ExtractionService(project_db).get_stats()
        stats["project_name"] = api_key.project_name
        return stats
    finally:
        await project_db.close()


# ─── API Key Management ───────────────────────────────────────────────────────

@router.post("/auth/generate-key", response_model=GenerateKeyResponse,
             summary="Generate an API key for a project (creates project DB if new)")
async def generate_key(
    body: GenerateKeyRequest,
    db: AsyncSession = Depends(get_db),
):
    record = await create_api_key(
        db=db,
        project_name=body.project_name,
        actions=body.allowed_actions,
        file_types=body.allowed_file_types,
        db_url=body.db_url,
    )
    return GenerateKeyResponse(
        id=record.id,
        project_name=record.project_name,
        api_key=record.api_key,
        permissions=record.permissions,
        created_at=record.created_at.isoformat(),
        status=record.status,
        message=f"API key generated for project '{record.project_name}'. Store it securely.",
    )


@router.get("/auth/keys", response_model=list[APIKeyResponse],
            summary="List all API keys (masked)")
async def list_keys(
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    result = await db.execute(select(APIKey).order_by(APIKey.created_at.desc()))
    keys = result.scalars().all()
    return [
        APIKeyResponse(
            id=k.id,
            project_name=k.project_name,
            api_key=None,   # masked — never return full key after creation
            permissions=k.permissions,
            created_at=k.created_at.isoformat(),
            status=k.status,
        )
        for k in keys
    ]


@router.patch("/auth/keys/{key_id}", response_model=APIKeyResponse,
              summary="Update API key permissions or status")
async def update_key(
    key_id: int,
    body: UpdateKeyRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    record = result.scalar_one_or_none()
    if not record:
        raise AppException(f"Key {key_id} not found.", status_code=404)

    if body.status in ("active", "revoked"):
        record.status = body.status

    if body.allowed_actions is not None or body.allowed_file_types is not None:
        current = record.permissions or {}
        actions = body.allowed_actions or current.get("actions", ALL_ACTIONS)
        file_types = body.allowed_file_types or current.get("file_types", ["*"])
        record.permissions = build_permissions(actions, file_types)

    await db.flush()
    await db.refresh(record)
    return APIKeyResponse(
        id=record.id,
        project_name=record.project_name,
        api_key=None,
        permissions=record.permissions,
        created_at=record.created_at.isoformat(),
        status=record.status,
    )


@router.delete("/auth/keys/{key_id}", response_model=RevokeKeyResponse,
               summary="Revoke an API key")
async def revoke_key(
    key_id: int,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    result = await db.execute(select(APIKey).where(APIKey.id == key_id))
    record = result.scalar_one_or_none()
    if not record:
        raise AppException(f"Key {key_id} not found.", status_code=404)
    record.status = "revoked"
    await db.flush()
    return RevokeKeyResponse(id=key_id, message=f"Key {key_id} revoked successfully.")


# ─── Email ────────────────────────────────────────────────────────────────────

@router.post("/email/send", response_model=SendEmailResponse,
             summary="Send an email using a built-in template")
async def send_email(
    body: SendEmailRequest,
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    data: dict = {}
    if body.document_id:
        project_db = await _project_session(api_key)
        try:
            data["document"] = await ExtractionService(project_db).get_document(body.document_id)
            data["pages"] = data["document"].get("pages", [])
        except Exception:
            pass
        finally:
            await project_db.close()
    if body.project_name:
        data["project_name"] = body.project_name
    if body.api_key_preview:
        data["api_key_preview"] = body.api_key_preview

    result = await email_service.send(to=body.to, template=body.template, data=data)
    return SendEmailResponse(**result)


# ─── Admin DB Viewer ──────────────────────────────────────────────────────────

@router.get("/admin/db/{table_name}", summary="Browse a table in the project's database")
async def browse_table(
    table_name: str,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    allowed = {"documents", "extracted_data"}
    if table_name not in allowed:
        raise AppException(f"Table '{table_name}' not accessible.", status_code=400)

    from sqlalchemy import text

    project_db = await _project_session(api_key)
    try:
        count_result = await project_db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        total = count_result.scalar_one()

        offset = (page - 1) * size
        rows_result = await project_db.execute(
            text(f"SELECT * FROM {table_name} LIMIT :lim OFFSET :off"),
            {"lim": size, "off": offset},
        )
        columns = list(rows_result.keys())
        rows_data = [list(r) for r in rows_result.fetchall()]

        return {
            "table": table_name,
            "project": api_key.project_name,
            "columns": columns,
            "rows": rows_data,
            "total": total,
            "page": page,
            "size": size,
        }
    finally:
        await project_db.close()


# ─── Projects list (admin) ───────────────────────────────────────────────────

@router.get("/projects", summary="List all projects")
async def list_projects(
    db: AsyncSession = Depends(get_db),
    api_key: APIKey = Depends(validate_api_key),
):
    result = await db.execute(select(Project).order_by(Project.created_at.desc()))
    projects = result.scalars().all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "slug": p.slug,
            "db_url": p.db_url if "sqlite" in p.db_url else "[remote]",
            "created_at": p.created_at.isoformat(),
            "status": p.status,
            "api_keys_count": len(p.api_keys) if hasattr(p, "api_keys") else 0,
        }
        for p in projects
    ]
