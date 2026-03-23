"""API Key authentication and permission enforcement.

Each API key is linked to a Project.  When validated, the key's Project is
eagerly loaded so that routes can resolve the project's isolated database.
"""

import secrets
from datetime import datetime
from typing import Optional

from fastapi import Depends, Security
from fastapi.security import APIKeyHeader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppException, AuthenticationException
from app.core.logging import get_logger
from app.database.models import APIKey, Project
from app.database.session import get_db
from app.database.project_session import (
    get_default_db_url,
    init_project_db,
    slugify,
)

logger = get_logger(__name__)

API_KEY_HEADER = APIKeyHeader(name="x-api-key", auto_error=False)

# All available actions and file types
ALL_ACTIONS = ["upload", "search", "filter", "view"]
ALL_FILE_TYPES = [
    ".pdf", ".xlsx", ".xls", ".docx", ".doc",
    ".eml", ".msg", ".csv", ".pptx", ".ppt",
    ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
]


class PermissionDeniedException(AppException):
    def __init__(self, message: str = "Permission denied."):
        super().__init__(message=message, status_code=403)


def generate_api_key() -> str:
    return secrets.token_hex(32)


def build_permissions(actions: list[str], file_types: list[str]) -> dict:
    """Normalise and validate a permissions payload."""
    valid_actions = [a for a in actions if a in ALL_ACTIONS] or ALL_ACTIONS
    valid_types = file_types if file_types else ["*"]
    return {"actions": valid_actions, "file_types": valid_types}


def check_action(api_key: APIKey, action: str) -> None:
    """Raise 403 if the key does not have the requested action."""
    perms = api_key.permissions or {}
    allowed = perms.get("actions", ALL_ACTIONS)
    if action not in allowed:
        raise PermissionDeniedException(
            f"This API key does not have '{action}' permission."
        )


def check_file_type(api_key: APIKey, file_type: str) -> None:
    """Raise 403 if the key does not allow the given file type for upload."""
    perms = api_key.permissions or {}
    allowed_types = perms.get("file_types", ["*"])
    if "*" in allowed_types:
        return
    if file_type.lower() not in [t.lower() for t in allowed_types]:
        raise PermissionDeniedException(
            f"This API key does not allow uploading '{file_type}' files. "
            f"Allowed types: {', '.join(allowed_types)}"
        )


async def validate_api_key(
    api_key: Optional[str] = Security(API_KEY_HEADER),
    db: AsyncSession = Depends(get_db),
) -> APIKey:
    """Validate the x-api-key header and return the APIKey with its Project loaded."""
    if not api_key:
        raise AuthenticationException("Missing x-api-key header.")

    result = await db.execute(
        select(APIKey)
        .options(selectinload(APIKey.project))
        .where(APIKey.api_key == api_key, APIKey.status == "active")
    )
    key_record = result.scalar_one_or_none()

    if not key_record:
        logger.warning("Invalid API key attempt: %s...", api_key[:8])
        raise AuthenticationException("Invalid or revoked API key.")

    if not key_record.project or key_record.project.status != "active":
        raise AuthenticationException("The project for this API key is inactive.")

    return key_record


async def get_or_create_project(
    db: AsyncSession,
    project_name: str,
    db_url: Optional[str] = None,
) -> Project:
    """Find an existing project by name or create a new one with its database."""
    slug = slugify(project_name)

    result = await db.execute(select(Project).where(Project.slug == slug))
    project = result.scalar_one_or_none()

    if project:
        return project

    # Create new project with its own database
    project_db_url = db_url or get_default_db_url(slug)
    project = Project(
        name=project_name,
        slug=slug,
        db_url=project_db_url,
        created_at=datetime.utcnow(),
        status="active",
    )
    db.add(project)
    await db.flush()
    await db.refresh(project)

    # Initialise the project's database (create tables)
    await init_project_db(project.db_url, project.slug)
    logger.info("Created new project '%s' with database: %s", project_name, project_db_url)

    return project


async def create_api_key(
    db: AsyncSession,
    project_name: str,
    actions: Optional[list[str]] = None,
    file_types: Optional[list[str]] = None,
    db_url: Optional[str] = None,
) -> APIKey:
    """Create an API key linked to a project (creates project if needed)."""
    project = await get_or_create_project(db, project_name, db_url)

    key = generate_api_key()
    permissions = build_permissions(
        actions or ALL_ACTIONS,
        file_types or ["*"],
    )
    record = APIKey(
        project_id=project.id,
        project_name=project_name,
        api_key=key,
        permissions=permissions,
        created_at=datetime.utcnow(),
        status="active",
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    return record
