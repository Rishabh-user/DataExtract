"""Excel extraction using pandas and openpyxl."""

from pathlib import Path
from typing import Any

import pandas as pd

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, PageContent

logger = get_logger(__name__)


class ExcelExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = [".xlsx", ".xls"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        try:
            engine = "openpyxl" if file_path.suffix == ".xlsx" else "xlrd"
            sheets = pd.read_excel(str(file_path), sheet_name=None, engine=engine)

            pages: list[PageContent] = []
            metadata: dict[str, Any] = {
                "total_sheets": len(sheets),
                "sheet_names": list(sheets.keys()),
            }

            for idx, (sheet_name, df) in enumerate(sheets.items(), start=1):
                # Clean NaN values for JSON serialization
                df = df.fillna("")

                content_lines = [
                    "\t".join(str(v) for v in row) for _, row in df.iterrows()
                ]
                content = "\n".join(content_lines)

                page_meta: dict[str, Any] = {
                    "sheet_name": sheet_name,
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": df.columns.tolist(),
                    "data_preview": df.head(5).to_dict(orient="records"),
                }

                pages.append(
                    PageContent(page_number=idx, content=content, metadata=page_meta)
                )

            return ExtractionResult(pages=pages, metadata=metadata)

        except Exception as e:
            logger.error("Excel extraction failed for %s: %s", file_path, e)
            return ExtractionResult(success=False, error=str(e))
