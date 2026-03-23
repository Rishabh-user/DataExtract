"""Extractor registry — maps file extensions to extractor instances."""

from pathlib import Path
from typing import Optional

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor
from app.extraction.csv_extractor import CSVExtractor
from app.extraction.doc_extractor import DocExtractor
from app.extraction.email_extractor import EmailExtractor
from app.extraction.excel_extractor import ExcelExtractor
from app.extraction.image_extractor import ImageExtractor
from app.extraction.pdf_extractor import PDFExtractor
from app.extraction.ppt_extractor import PPTExtractor
from app.extraction.video_extractor import VideoExtractor

logger = get_logger(__name__)

_EXTRACTORS: list[BaseExtractor] = [
    PDFExtractor(),
    ExcelExtractor(),
    DocExtractor(),
    EmailExtractor(),
    CSVExtractor(),
    PPTExtractor(),
    ImageExtractor(),
    VideoExtractor(),
]


def get_extractor(file_path: Path) -> Optional[BaseExtractor]:
    """Return the appropriate extractor for the given file, or None."""
    for extractor in _EXTRACTORS:
        if extractor.can_handle(file_path):
            return extractor
    logger.warning("No extractor registered for extension: %s", file_path.suffix)
    return None


def supported_extensions() -> list[str]:
    """Return all file extensions supported by registered extractors."""
    exts: list[str] = []
    for extractor in _EXTRACTORS:
        exts.extend(extractor.SUPPORTED_EXTENSIONS)
    return exts
