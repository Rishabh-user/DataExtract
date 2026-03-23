"""Video extraction placeholder for future support."""

from pathlib import Path

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, PageContent

logger = get_logger(__name__)


class VideoExtractor(BaseExtractor):
    """Placeholder extractor for video files. Not yet implemented."""

    SUPPORTED_EXTENSIONS = [".mp4", ".avi", ".mov"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        logger.info("Video extraction requested for %s — not yet implemented.", file_path)
        return ExtractionResult(
            pages=[
                PageContent(
                    page_number=1,
                    content="",
                    metadata={"notice": "Video extraction is not yet implemented."},
                )
            ],
            metadata={"status": "placeholder", "file_name": file_path.name},
            success=True,
            error=None,
        )
