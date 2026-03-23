"""SQLAlchemy ORM models for the application.

Main DB  (extraction.db):  Project, APIKey   — admin / auth data
Project DB (databases/<slug>.db):  Document, ExtractedData — per-project data
"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ─── Main database (admin / auth) ────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base for the central admin database (projects + api_keys)."""
    pass


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    # Database URL for this project's isolated storage.
    # Local:  sqlite+aiosqlite:///databases/my_project.db
    # Remote: postgresql+asyncpg://user:pass@remote-server:5432/my_project_db
    db_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    api_keys: Mapped[list["APIKey"]] = relationship(
        "APIKey", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', slug='{self.slug}')>"


class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    permissions: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="api_keys")

    def __repr__(self) -> str:
        return f"<APIKey(id={self.id}, project='{self.project_name}', status='{self.status}')>"


# ─── Project database (per-project data isolation) ───────────────────────────

class ProjectBase(DeclarativeBase):
    """Base for per-project databases (documents + extracted_data)."""
    pass


class Document(ProjectBase):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    upload_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)

    extracted_data: Mapped[list["ExtractedData"]] = relationship(
        "ExtractedData", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document(id={self.id}, file_name='{self.file_name}', status='{self.status}')>"


class ExtractedData(ProjectBase):
    __tablename__ = "extracted_data"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    extra_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        "metadata", JSON, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    document: Mapped["Document"] = relationship("Document", back_populates="extracted_data")

    def __repr__(self) -> str:
        return f"<ExtractedData(id={self.id}, document_id={self.document_id}, page={self.page_number})>"
