"""Image OCR extraction using pytesseract, OpenCV, and Pillow.

Pipeline:
  1. Composite RGBA transparency onto white background.
  2. Upscale small images to ~300 DPI-equivalent for better OCR accuracy.
  3. Run OCR on the clean colour image first (best for digital screenshots/scans).
  4. If confidence is low, run a second pass with denoised grayscale preprocessing.
  5. Return whichever pass produced higher confidence.
"""

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, PageContent

logger = get_logger(__name__)
settings = get_settings()

# Tesseract config: OEM 3 = LSTM engine, PSM 6 = uniform block of text
_TESS_CONFIG = "--oem 3 --psm 6"
# Minimum short-edge size before we upscale
_MIN_EDGE = 1000
# Confidence threshold below which we try a second preprocessing pass
_CONF_THRESHOLD = 60.0


class ImageExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def extract(self, file_path: Path) -> ExtractionResult:
        try:
            import pytesseract

            if settings.TESSERACT_CMD:
                pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

            from PIL import Image

            # Load and normalise the image once
            img = self._load_normalised(file_path)

            # --- Pass 1: clean image (best for crisp digital text) ---
            text1, conf1, data1 = self._run_ocr(img, pytesseract)

            best_text, best_conf, best_data = text1, conf1, data1

            # --- Pass 2: denoised grayscale (helps for photos/scans) ---
            if conf1 < _CONF_THRESHOLD:
                img2 = self._preprocess_for_ocr(img)
                text2, conf2, data2 = self._run_ocr(img2, pytesseract)
                if conf2 > conf1:
                    best_text, best_conf, best_data = text2, conf2, data2
                    logger.debug("Pass-2 preprocessing improved confidence %.1f → %.1f", conf1, conf2)

            word_count = len([w for w in best_data["text"] if str(w).strip()])

            # Collect original file metadata
            with Image.open(str(file_path)) as orig:
                file_meta: dict[str, Any] = {
                    "width": orig.width,
                    "height": orig.height,
                    "format": orig.format or file_path.suffix.lstrip(".").upper(),
                    "mode": orig.mode,
                }

            metadata: dict[str, Any] = {
                **file_meta,
                "ocr_confidence": round(best_conf, 2),
                "word_count": word_count,
                "ocr_engine": "tesseract",
            }

            pages = [PageContent(page_number=1, content=best_text.strip(), metadata=metadata)]
            return ExtractionResult(pages=pages, metadata=metadata)

        except FileNotFoundError:
            return ExtractionResult(success=False, error=f"Image file not found: {file_path}")
        except Exception as e:
            logger.error("Image OCR extraction failed for %s: %s", file_path, e, exc_info=True)
            return ExtractionResult(success=False, error=str(e))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _load_normalised(file_path: Path):
        """Load any image format and return a clean RGB PIL image."""
        from PIL import Image

        img = Image.open(str(file_path))

        # Flatten transparency onto white background
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                background.paste(img, mask=img.split()[-1])  # use alpha channel as mask
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Upscale if the image is too small — Tesseract needs ~300 DPI
        w, h = img.size
        short_edge = min(w, h)
        if short_edge < _MIN_EDGE:
            scale = _MIN_EDGE / short_edge
            new_w = int(w * scale)
            new_h = int(h * scale)
            from PIL import Image as PILImage
            img = img.resize((new_w, new_h), PILImage.LANCZOS)
            logger.debug("Upscaled image %dx%d → %dx%d for better OCR", w, h, new_w, new_h)

        return img

    @staticmethod
    def _preprocess_for_ocr(pil_img):
        """Grayscale + adaptive threshold — improves noisy / low-contrast images."""
        import cv2
        import numpy as np
        from PIL import Image

        img_np = np.array(pil_img)
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)

        # Denoise
        denoised = cv2.fastNlMeansDenoising(gray, h=10)

        # Adaptive threshold preserves local contrast better than Otsu
        thresh = cv2.adaptiveThreshold(
            denoised, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=31,
            C=10,
        )

        return Image.fromarray(thresh)

    @staticmethod
    def _run_ocr(img, pytesseract) -> tuple[str, float, dict]:
        """Run Tesseract on a PIL image, return (text, avg_confidence, data_dict)."""
        text = pytesseract.image_to_string(img, config=_TESS_CONFIG)
        data = pytesseract.image_to_data(img, config=_TESS_CONFIG, output_type=pytesseract.Output.DICT)

        confs = [int(c) for c in data["conf"] if str(c).lstrip("-").isdigit() and int(c) > 0]
        avg_conf = sum(confs) / len(confs) if confs else 0.0

        return text, avg_conf, data
