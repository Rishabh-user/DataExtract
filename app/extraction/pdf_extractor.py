"""PDF extraction using pdfplumber, PyMuPDF, and Tesseract OCR.

Extraction strategy:
  1. Try pdfplumber for fast, layout-aware digital text extraction.
  2. For each page with little/no text, try PyMuPDF as a second digital parser.
  3. Pages still lacking text are treated as scanned — rendered to images via
     PyMuPDF and OCR'd with Tesseract (two-pass preprocessing pipeline).

This per-page approach handles mixed PDFs (some pages digital, some scanned)
and gracefully falls back when optional libraries are unavailable.
"""

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, PageContent

logger = get_logger(__name__)
settings = get_settings()

# Tesseract configs
# PSM 3 = fully automatic page segmentation (detects text blocks + orientations)
_TESS_CONFIG = "--oem 3 --psm 3"
# PSM 6 = uniform block (used for rotated pass where the full image is one orientation)
_TESS_CONFIG_BLOCK = "--oem 3 --psm 6"
# Minimum short-edge pixel size before upscaling (Tesseract needs ~300 DPI)
_MIN_EDGE = 1000
# OCR confidence threshold below which we try a second preprocessing pass
_CONF_THRESHOLD = 60.0
# Per-page text length threshold: pages below this are considered scanned
_PAGE_TEXT_THRESHOLD = 50
# PyMuPDF render scale — 3× (≈216 DPI) works well for engineering drawings
_RENDER_SCALE = 3


class PDFExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = [".pdf"]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def extract(self, file_path: Path) -> ExtractionResult:
        try:
            # Stage 1 — pdfplumber (best for digital PDFs with text layer)
            pages, metadata = await self._extract_with_pdfplumber(file_path)

            # Identify pages that got little/no text (likely scanned)
            sparse_indices = [
                i for i, p in enumerate(pages)
                if len(p.content.strip()) < _PAGE_TEXT_THRESHOLD
            ]

            # Stage 2 — Try PyMuPDF on sparse pages (different parser)
            if sparse_indices:
                pages, sparse_indices = await self._pymupdf_fallback(
                    file_path, pages, sparse_indices, metadata
                )

            # Stage 3 — OCR remaining sparse pages (scanned content)
            if sparse_indices:
                pages = await self._ocr_sparse_pages(
                    file_path, pages, sparse_indices, metadata
                )

            # Optional: table extraction with camelot (safe no-op if not installed)
            tables = await self._extract_tables(file_path)
            if tables:
                metadata["tables"] = tables

            return ExtractionResult(pages=pages, metadata=metadata)

        except Exception as e:
            logger.error("PDF extraction failed for %s: %s", file_path, e, exc_info=True)
            return ExtractionResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Stage 1 — pdfplumber
    # ------------------------------------------------------------------

    async def _extract_with_pdfplumber(
        self, file_path: Path
    ) -> tuple[list[PageContent], dict[str, Any]]:
        import pdfplumber

        pages: list[PageContent] = []
        metadata: dict[str, Any] = {}

        with pdfplumber.open(str(file_path)) as pdf:
            metadata["total_pages"] = len(pdf.pages)
            metadata["pdf_metadata"] = pdf.metadata or {}

            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""
                page_meta: dict[str, Any] = {
                    "width": page.width,
                    "height": page.height,
                    "extraction_method": "digital",
                }

                page_tables = page.extract_tables()
                if page_tables:
                    page_meta["tables_count"] = len(page_tables)
                    page_meta["tables"] = [
                        [row for row in table if any(cell for cell in row)]
                        for table in page_tables
                    ]

                pages.append(PageContent(page_number=i, content=text, metadata=page_meta))

        return pages, metadata

    # ------------------------------------------------------------------
    # Stage 2 — PyMuPDF fallback for sparse pages
    # ------------------------------------------------------------------

    async def _pymupdf_fallback(
        self,
        file_path: Path,
        pages: list[PageContent],
        sparse_indices: list[int],
        metadata: dict[str, Any],
    ) -> tuple[list[PageContent], list[int]]:
        """Try PyMuPDF text extraction on pages that pdfplumber couldn't handle."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.info("PyMuPDF not installed, skipping Stage 2 digital fallback")
            return pages, sparse_indices

        logger.info(
            "pdfplumber returned minimal text on %d page(s), trying PyMuPDF",
            len(sparse_indices),
        )
        doc = fitz.open(str(file_path))
        still_sparse: list[int] = []

        for idx in sparse_indices:
            page = doc[idx]
            text = page.get_text("text")
            if len(text.strip()) >= _PAGE_TEXT_THRESHOLD:
                pages[idx] = PageContent(
                    page_number=idx + 1,
                    content=text,
                    metadata={
                        "width": page.rect.width,
                        "height": page.rect.height,
                        "images_count": len(page.get_images()),
                        "extraction_method": "digital",
                    },
                )
            else:
                still_sparse.append(idx)

        doc.close()
        return pages, still_sparse

    # ------------------------------------------------------------------
    # Stage 3 — OCR for scanned pages
    # ------------------------------------------------------------------

    async def _ocr_sparse_pages(
        self,
        file_path: Path,
        pages: list[PageContent],
        sparse_indices: list[int],
        metadata: dict[str, Any],
    ) -> list[PageContent]:
        """Render sparse (scanned) pages to images and OCR them with Tesseract."""
        try:
            import fitz
        except ImportError:
            logger.error("PyMuPDF is required for OCR on scanned PDFs — pip install PyMuPDF")
            return pages

        try:
            import pytesseract
        except ImportError:
            logger.error("pytesseract is required for OCR on scanned PDFs — pip install pytesseract")
            return pages

        from PIL import Image

        if settings.TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

        logger.info(
            "Running OCR on %d scanned page(s) at %d× scale",
            len(sparse_indices), _RENDER_SCALE,
        )

        doc = fitz.open(str(file_path))
        total_conf = 0.0
        ocr_count = 0

        for idx in sparse_indices:
            page = doc[idx]
            page_num = idx + 1

            # Render page at configured scale (3× ≈ 216 DPI)
            mat = fitz.Matrix(_RENDER_SCALE, _RENDER_SCALE)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Upscale if the rendered image is still too small for Tesseract
            img = self._normalise_image(img)

            # --- Horizontal OCR (PSM 3 auto-segmentation) ---
            text1, conf1, _ = self._run_ocr(img, pytesseract)
            best_text, best_conf = text1, conf1

            # Preprocessing pass if confidence is low
            if conf1 < _CONF_THRESHOLD:
                img2 = self._preprocess_for_ocr(img)
                text2, conf2, _ = self._run_ocr(img2, pytesseract)
                if conf2 > conf1:
                    best_text, best_conf = text2, conf2
                    logger.debug(
                        "Page %d: preprocessing improved confidence %.1f → %.1f",
                        page_num, conf1, conf2,
                    )

            # --- Vertical text pass (90° CW rotation) ---
            # Engineering drawings often have pipe labels, equipment tags,
            # and notes oriented vertically. Rotate and OCR to capture them.
            vertical_text = self._extract_vertical_text(img, best_text, pytesseract)
            if vertical_text:
                best_text = best_text.strip() + "\n\n--- Vertical / Rotated Text ---\n" + vertical_text
                logger.debug(
                    "Page %d: captured %d chars of vertical text",
                    page_num, len(vertical_text),
                )

            total_conf += best_conf
            ocr_count += 1

            pages[idx] = PageContent(
                page_number=page_num,
                content=best_text.strip(),
                metadata={
                    "width": pix.width,
                    "height": pix.height,
                    "extraction_method": "ocr",
                    "ocr_confidence": round(best_conf, 2),
                    "has_vertical_text": bool(vertical_text),
                },
            )
            logger.debug(
                "Page %d OCR complete — confidence %.1f, chars %d",
                page_num, best_conf, len(best_text),
            )

        doc.close()

        # Update metadata with OCR info
        if ocr_count > 0:
            avg_conf = round(total_conf / ocr_count, 2)
            metadata["is_scanned"] = True
            metadata["ocr_engine"] = "tesseract"
            metadata["ocr_pages"] = ocr_count
            metadata["avg_ocr_confidence"] = avg_conf
            logger.info(
                "Scanned PDF OCR complete — %d page(s), avg confidence %.1f",
                ocr_count, avg_conf,
            )

        return pages

    # ------------------------------------------------------------------
    # Optional — camelot table extraction
    # ------------------------------------------------------------------

    async def _extract_tables(self, file_path: Path) -> list[dict[str, Any]]:
        try:
            import camelot

            tables = camelot.read_pdf(str(file_path), pages="all", flavor="lattice")
            result = []
            for table in tables:
                result.append({
                    "page": table.page,
                    "accuracy": table.accuracy,
                    "data": table.df.values.tolist(),
                    "columns": table.df.columns.tolist(),
                })
            return result
        except Exception as e:
            logger.debug("Camelot table extraction skipped: %s", e)
            return []

    # ------------------------------------------------------------------
    # Vertical text extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_vertical_text(img, horizontal_text: str, pytesseract) -> str:
        """Rotate image 90° CW and OCR to capture vertical text (pipe labels, etc.).

        Extracts recognisable engineering identifiers (pipe numbers, equipment
        tags, drawing references) that appear only in the rotated pass — these
        are the vertical labels on P&ID / GA drawings.
        """
        import re

        # Rotate 90° clockwise — vertical text becomes horizontal
        img_cw = img.rotate(-90, expand=True)
        text_cw = pytesseract.image_to_string(img_cw, config=_TESS_CONFIG_BLOCK)

        # Patterns for common engineering identifiers found on drawings:
        # Pipe labels:   16"-A8M2-22-SW-8040-V, 1"-A8M2-22-SW-8059-V
        # Equipment IDs: 22-BA-8102, 22-GA-8012, E-F17020
        # Drawing refs:  20171-SPOG-62400-MA-DW-0007
        _ID_PATTERN = re.compile(
            r'\d{1,3}["\u2033]?-[A-Z0-9]{2,}-\d{2}-[A-Z]{2}-\d{3,}-[A-Z]'  # pipe labels
            r'|\d{2}-[A-Z]{2}-\d{4,}'                                        # equipment IDs
            r'|[A-Z]{1,2}-[A-Z]\d{4,}'                                       # tag refs (E-F17020)
            r'|\d{5}-[A-Z]{2,}-\d{5}-[A-Z]{2}-[A-Z]{2}-\d{4}'               # drawing refs
        )

        # Collect all identifiers from the horizontal pass (for dedup)
        h_ids: set[str] = set()
        for match in _ID_PATTERN.finditer(horizontal_text):
            h_ids.add(match.group().upper())

        # Extract new identifiers from the rotated pass
        new_ids: list[str] = []
        seen: set[str] = set()
        for match in _ID_PATTERN.finditer(text_cw):
            ident = match.group().upper()
            if ident not in h_ids and ident not in seen:
                new_ids.append(ident)
                seen.add(ident)

        return "\n".join(new_ids)

    # ------------------------------------------------------------------
    # OCR helper staticmethods (same pipeline as ImageExtractor)
    # ------------------------------------------------------------------

    @staticmethod
    def _normalise_image(img):
        """Upscale image if short edge is below the minimum for good OCR accuracy."""
        from PIL import Image

        w, h = img.size
        short_edge = min(w, h)
        if short_edge < _MIN_EDGE:
            scale = _MIN_EDGE / short_edge
            new_w, new_h = int(w * scale), int(h * scale)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            logger.debug("Upscaled %dx%d → %dx%d for OCR", w, h, new_w, new_h)
        return img

    @staticmethod
    def _preprocess_for_ocr(pil_img):
        """Grayscale + denoise + adaptive threshold — improves noisy / low-contrast scans."""
        import cv2
        import numpy as np
        from PIL import Image

        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10,
        )
        return Image.fromarray(thresh)

    @staticmethod
    def _run_ocr(img, pytesseract, config: str = _TESS_CONFIG) -> tuple[str, float, dict]:
        """Run Tesseract on a PIL image. Returns (text, avg_confidence, data_dict)."""
        text = pytesseract.image_to_string(img, config=config)
        data = pytesseract.image_to_data(
            img, config=config, output_type=pytesseract.Output.DICT
        )
        confs = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0.0
        return text, avg_conf, data
