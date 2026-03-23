"""Application configuration using Pydantic settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "Universal Data Extraction Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database — SQLite for local dev, set DATABASE_URL for Postgres
    DATABASE_URL: str = "sqlite+aiosqlite:///./extraction.db"

    # Elasticsearch (optional)
    ELASTICSEARCH_HOST: str = "localhost"
    ELASTICSEARCH_PORT: int = 9200
    ELASTICSEARCH_SCHEME: str = "http"
    ELASTICSEARCH_USER: Optional[str] = None
    ELASTICSEARCH_PASSWORD: Optional[str] = None
    ELASTICSEARCH_INDEX: str = "extracted_documents"
    ELASTICSEARCH_ENABLED: bool = False

    @property
    def ELASTICSEARCH_URL(self) -> str:
        if self.ELASTICSEARCH_USER and self.ELASTICSEARCH_PASSWORD:
            return (
                f"{self.ELASTICSEARCH_SCHEME}://{self.ELASTICSEARCH_USER}:"
                f"{self.ELASTICSEARCH_PASSWORD}@{self.ELASTICSEARCH_HOST}:"
                f"{self.ELASTICSEARCH_PORT}"
            )
        return f"{self.ELASTICSEARCH_SCHEME}://{self.ELASTICSEARCH_HOST}:{self.ELASTICSEARCH_PORT}"

    # File Storage
    UPLOAD_DIR: str = "uploads"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_EXTENSIONS: list[str] = [
        ".pdf", ".xlsx", ".xls", ".docx", ".doc",
        ".eml", ".msg", ".csv", ".pptx", ".ppt",
        ".png", ".jpg", ".jpeg", ".tiff", ".bmp",
        ".mp4", ".avi", ".mov",
    ]

    # OCR
    TESSERACT_CMD: Optional[str] = None

    # Processing
    MAX_WORKERS: int = 4
    EXTRACTION_TIMEOUT_SECONDS: int = 300

    # Email
    EMAIL_BACKEND: str = "dummy"          # "dummy" or "smtp"
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_USE_TLS: bool = True
    EMAIL_USERNAME: Optional[str] = None
    EMAIL_PASSWORD: Optional[str] = None
    EMAIL_FROM: str = "noreply@dataextract.local"
    EMAIL_FROM_NAME: str = "DataExtract Platform"

    # Admin credentials (for /login page)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = "admin123"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
