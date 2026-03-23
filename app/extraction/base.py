"""Base extractor interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class ExtractionResult:
    """Standardized extraction result returned by all extractors."""

    pages: list["PageContent"] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages": [p.to_dict() for p in self.pages],
            "metadata": self.metadata,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class PageContent:
    """Content extracted from a single page or section."""

    page_number: int
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_number": self.page_number,
            "content": self.content,
            "metadata": self.metadata,
        }


class BaseExtractor(ABC):
    """Abstract base class for all extractors."""

    SUPPORTED_EXTENSIONS: list[str] = []

    def can_handle(self, file_path: Path) -> bool:
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    @abstractmethod
    async def extract(self, file_path: Path) -> ExtractionResult:
        """Extract content from the given file."""
        ...
