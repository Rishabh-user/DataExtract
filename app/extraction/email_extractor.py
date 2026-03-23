"""Email extraction for .eml and .msg files."""

import email
from email import policy
from pathlib import Path
from typing import Any

from app.core.logging import get_logger
from app.extraction.base import BaseExtractor, ExtractionResult, PageContent

logger = get_logger(__name__)


class EmailExtractor(BaseExtractor):
    SUPPORTED_EXTENSIONS = [".eml", ".msg"]

    async def extract(self, file_path: Path) -> ExtractionResult:
        try:
            if file_path.suffix.lower() == ".eml":
                return await self._extract_eml(file_path)
            elif file_path.suffix.lower() == ".msg":
                return await self._extract_msg(file_path)
            return ExtractionResult(success=False, error="Unsupported email format")
        except Exception as e:
            logger.error("Email extraction failed for %s: %s", file_path, e)
            return ExtractionResult(success=False, error=str(e))

    async def _extract_eml(self, file_path: Path) -> ExtractionResult:
        with open(file_path, "rb") as f:
            msg = email.message_from_binary_file(f, policy=policy.default)

        metadata: dict[str, Any] = {
            "subject": msg.get("subject", ""),
            "from": msg.get("from", ""),
            "to": msg.get("to", ""),
            "cc": msg.get("cc", ""),
            "date": msg.get("date", ""),
            "message_id": msg.get("message-id", ""),
        }

        body_parts: list[str] = []
        attachments: list[dict[str, str]] = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in disposition:
                    attachments.append({
                        "filename": part.get_filename() or "unknown",
                        "content_type": content_type,
                    })
                elif content_type == "text/plain":
                    body_parts.append(part.get_content())
                elif content_type == "text/html" and not body_parts:
                    body_parts.append(part.get_content())
        else:
            body_parts.append(msg.get_content())

        metadata["attachments"] = attachments
        metadata["attachments_count"] = len(attachments)

        content = "\n\n".join(body_parts)
        pages = [PageContent(page_number=1, content=content, metadata=metadata)]

        return ExtractionResult(pages=pages, metadata=metadata)

    async def _extract_msg(self, file_path: Path) -> ExtractionResult:
        import extract_msg

        msg = extract_msg.Message(str(file_path))

        metadata: dict[str, Any] = {
            "subject": msg.subject or "",
            "from": msg.sender or "",
            "to": msg.to or "",
            "cc": msg.cc or "",
            "date": msg.date or "",
        }

        attachments = []
        for attachment in msg.attachments:
            attachments.append({
                "filename": attachment.longFilename or attachment.shortFilename or "unknown",
                "size": len(attachment.data) if attachment.data else 0,
            })

        metadata["attachments"] = attachments
        metadata["attachments_count"] = len(attachments)

        content = msg.body or ""
        pages = [PageContent(page_number=1, content=content, metadata=metadata)]

        msg.close()
        return ExtractionResult(pages=pages, metadata=metadata)
