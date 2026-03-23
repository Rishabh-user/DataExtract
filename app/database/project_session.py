"""Dynamic per-project database session management.

Each project gets its OWN isolated database — either:
  - Local SQLite   (default):  databases/<slug>.db
  - Remote Postgres:  postgresql+asyncpg://user:pass@host:5432/project_db
  - Remote MySQL:     mysql+aiomysql://user:pass@host:3306/project_db

This module handles:
  - Creating / initialising a project database (tables)
  - Returning an async session scoped to that project
  - Caching engines so we don't recreate them on every request
"""

import re
from pathlib import Path

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.database.models import ProjectBase

logger = get_logger(__name__)
settings = get_settings()

# Directory where local SQLite project databases are stored
DATABASES_DIR = Path("databases")

# Cache: slug → (engine, session_factory)
_engine_cache: dict[str, tuple[AsyncEngine, async_sessionmaker]] = {}


def slugify(name: str) -> str:
    """Convert a project name to a safe filesystem / DB slug."""
    slug = re.sub(r"[^\w\s-]", "", name.lower().strip())
    slug = re.sub(r"[\s_-]+", "_", slug)
    return slug or "default"


def get_default_db_url(slug: str) -> str:
    """Return a local SQLite URL for a project (default when no remote DB specified)."""
    DATABASES_DIR.mkdir(parents=True, exist_ok=True)
    db_path = str(DATABASES_DIR / f"{slug}.db")
    return f"sqlite+aiosqlite:///{db_path}"


def _get_or_create_engine(db_url: str, slug: str) -> tuple[AsyncEngine, async_sessionmaker]:
    """Return a cached (engine, session_factory) or create a new one."""
    if slug in _engine_cache:
        return _engine_cache[slug]

    is_sqlite = db_url.startswith("sqlite")

    engine_kwargs: dict = {
        "echo": settings.DEBUG,
    }

    if is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL / MySQL — use connection pooling
        engine_kwargs["pool_size"] = 10
        engine_kwargs["max_overflow"] = 5
        engine_kwargs["pool_pre_ping"] = True

    engine = create_async_engine(db_url, **engine_kwargs)
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    _engine_cache[slug] = (engine, factory)
    logger.debug("Created engine for project '%s' → %s", slug, _mask_url(db_url))
    return engine, factory


async def init_project_db(db_url: str, slug: str) -> None:
    """Create all tables in a project database (idempotent)."""
    engine, _ = _get_or_create_engine(db_url, slug)
    async with engine.begin() as conn:
        await conn.run_sync(ProjectBase.metadata.create_all)
    logger.info("Initialised project database: %s (%s)", slug, _mask_url(db_url))


async def get_project_db(db_url: str, slug: str) -> AsyncSession:
    """Return an async session for the given project database.

    The caller is responsible for committing / rolling back / closing.
    """
    _, factory = _get_or_create_engine(db_url, slug)
    return factory()


async def dispose_all_engines() -> None:
    """Dispose all cached engines (call on app shutdown)."""
    for slug, (engine, _) in _engine_cache.items():
        await engine.dispose()
        logger.debug("Disposed engine for project '%s'", slug)
    _engine_cache.clear()


def _mask_url(url: str) -> str:
    """Mask password in database URL for logging."""
    if "://" in url and "@" in url:
        # postgresql+asyncpg://user:PASSWORD@host:5432/db  →  ...user:***@host...
        before_at = url.split("@")[0]
        after_at = url.split("@", 1)[1]
        if ":" in before_at.split("://")[1]:
            scheme_user = before_at.rsplit(":", 1)[0]
            return f"{scheme_user}:***@{after_at}"
    return url
