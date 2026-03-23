"""CSV extraction using pandas."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, PageContent

logger = get_logger(__name__)


class CSVExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = [".csv"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        try:
            # Detect encoding
            encoding = self._detect_encoding(file_path)
            df = pd.read_csv(str(file_path), encoding=encoding)
            df = df.fillna("")

            metadata: dict[str, Any] = {
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": df.columns.tolist(),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "data_preview": df.head(10).to_dict(orient="records"),
                "encoding": encoding,
            }

            content_lines = [
                "\t".join(str(v) for v in row) for _, row in df.iterrows()
            ]
            content = "\n".join(content_lines)

            pages = [PageContent(page_number=1, content=content, metadata=metadata)]
            return ExtractionResult(pages=pages, metadata=metadata)

        except Exception as e:
            logger.error("CSV extraction failed for %s: %s", file_path, e)
            return ExtractionResult(success=False, error=str(e))

    @staticmethod
    def _detect_encoding(file_path: Path) -> str:
        """Try common encodings to find one that works."""
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(file_path, encoding=enc) as f:
                    f.read(4096)
                return enc
            except (UnicodeDecodeError, UnicodeError):
                continue
        return "utf-8"
