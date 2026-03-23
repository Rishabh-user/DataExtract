"""Orchestrates file upload, extraction, storage, and indexing."""

import asyncio
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import (
    DocumentNotFoundException,
    ExtractionException,
    FileNotSupportedException,
    FileTooLargeException,
)
from app.core.logging import get_logger
from app.database.elasticsearch import es_client
from app.database.models import Document, ExtractedData
from app.extraction.registry import get_extractor

logger = get_logger(__name__)
settings = get_settings()


class ExtractionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Upload & Extract ─────────────────────────────────────────────────────

    async def upload_and_extract(
        self,
        file_name: str,
        file_content: bytes,
        source: Optional[str] = None,
    ) -> Document:
        file_path = Path(file_name)
        ext = file_path.suffix.lower()

        extractor = get_extractor(file_path)
        if extractor is None:
            raise FileNotSupportedException(ext)

        size_mb = len(file_content) / (1024 * 1024)
        if size_mb > settings.MAX_FILE_SIZE_MB:
            raise FileTooLargeException(size_mb, settings.MAX_FILE_SIZE_MB)

        # Save to disk
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        saved_path = upload_dir / f"{timestamp}_{file_path.name}"
        saved_path.write_bytes(file_content)

        document = Document(
            file_name=file_name,
            file_type=ext,
            source=source,
            upload_date=datetime.utcnow(),
            file_path=str(saved_path),
            file_size_bytes=len(file_content),
            status="pending",
        )
        self.db.add(document)
        await self.db.flush()
        await self.db.refresh(document)

        document.status = "processing"
        await self.db.flush()

        try:
            result = await asyncio.wait_for(
                extractor.extract(saved_path),
                timeout=settings.EXTRACTION_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            document.status = "failed"
            await self.db.flush()
            raise ExtractionException(f"Extraction timed out after {settings.EXTRACTION_TIMEOUT_SECONDS}s")
        except Exception as e:
            document.status = "failed"
            await self.db.flush()
            raise ExtractionException(str(e))

        if not result.success:
            document.status = "failed"
            await self.db.flush()
            raise ExtractionException(result.error or "Unknown extraction error")

        for page in result.pages:
            self.db.add(ExtractedData(
                document_id=document.id,
                page_number=page.page_number,
                content=page.content,
                extra_metadata=page.metadata,
                created_at=datetime.utcnow(),
            ))
            await es_client.index_document(
                doc_id=f"{document.id}_{page.page_number}",
                body={
                    "document_id": document.id,
                    "file_name": document.file_name,
                    "file_type": document.file_type,
                    "source": document.source or "",
                    "page_number": page.page_number,
                    "content": page.content,
                    "metadata": page.metadata,
                    "upload_date": document.upload_date.isoformat(),
                    "created_at": datetime.utcnow().isoformat(),
                },
            )

        document.status = "completed"
        await self.db.flush()
        await self.db.refresh(document)
        logger.info("Extraction completed: doc %s (%s)", document.id, file_name)
        return document

    # ─── Get Document ─────────────────────────────────────────────────────────

    async def get_document(self, document_id: int) -> dict[str, Any]:
        result = await self.db.execute(select(Document).where(Document.id == document_id))
        document = result.scalar_one_or_none()
        if not document:
            raise DocumentNotFoundException(document_id)

        data_result = await self.db.execute(
            select(ExtractedData)
            .where(ExtractedData.document_id == document_id)
            .order_by(ExtractedData.page_number)
        )
        extracted = data_result.scalars().all()

        return {
            "id": document.id,
            "file_name": document.file_name,
            "file_type": document.file_type,
            "source": document.source,
            "upload_date": document.upload_date.isoformat(),
            "status": document.status,
            "file_size_bytes": document.file_size_bytes,
            "pages": [
                {
                    "id": e.id,
                    "page_number": e.page_number,
                    "content": e.content,
                    "metadata": e.extra_metadata,
                    "created_at": e.created_at.isoformat(),
                }
                for e in extracted
            ],
        }

    # ─── Filter ───────────────────────────────────────────────────────────────

    async def filter_documents(
        self,
        file_type: Optional[str] = None,
        source: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        query = select(Document)

        if file_type:
            query = query.where(Document.file_type == file_type)
        if source:
            query = query.where(Document.source == source)
        if status:
            query = query.where(Document.status == status)
        if date_from:
            query = query.where(Document.upload_date >= datetime.fromisoformat(date_from))
        if date_to:
            query = query.where(Document.upload_date <= datetime.fromisoformat(date_to))

        # total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_q)).scalar_one()

        query = query.order_by(Document.upload_date.desc()).offset((page - 1) * size).limit(size)
        documents = (await self.db.execute(query)).scalars().all()

        return {
            "page": page,
            "size": size,
            "total": total,
            "results": [
                {
                    "id": d.id,
                    "file_name": d.file_name,
                    "file_type": d.file_type,
                    "source": d.source,
                    "upload_date": d.upload_date.isoformat(),
                    "status": d.status,
                    "file_size_bytes": d.file_size_bytes,
                }
                for d in documents
            ],
        }

    # ─── Search ───────────────────────────────────────────────────────────────

    async def search_documents(
        self,
        query: str,
        file_type: Optional[str] = None,
        source: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> dict[str, Any]:
        if es_client.available:
            try:
                return await self._search_elasticsearch(query, file_type, source, page, size)
            except Exception as e:
                logger.warning("ES search failed, falling back to DB: %s", e)
        return await self._search_database(query, file_type, source, page, size)

    async def _search_elasticsearch(self, query, file_type, source, page, size):
        es_result = await es_client.search(query=query, file_type=file_type, source=source, page=page, size=size)
        hits = es_result.get("hits", {})
        total = hits.get("total", {}).get("value", 0)
        results = []
        for hit in hits.get("hits", []):
            src = hit["_source"]
            results.append({
                "document_id": src.get("document_id"),
                "file_name": src.get("file_name"),
                "file_type": src.get("file_type"),
                "source": src.get("source"),
                "page_number": src.get("page_number"),
                "content_snippet": hit.get("highlight", {}).get("content", [src.get("content", "")[:200]])[0],
                "score": hit.get("_score"),
            })
        return {"query": query, "total": total, "page": page, "size": size, "results": results}

    async def _search_database(self, query, file_type, source, page, size):
        like = f"%{query}%"
        stmt = (
            select(ExtractedData, Document)
            .join(Document, ExtractedData.document_id == Document.id)
            .where(or_(ExtractedData.content.ilike(like), Document.file_name.ilike(like)))
        )
        if file_type:
            stmt = stmt.where(Document.file_type == file_type)
        if source:
            stmt = stmt.where(Document.source == source)

        total_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.db.execute(total_stmt)).scalar_one()

        stmt = stmt.offset((page - 1) * size).limit(size)
        rows = (await self.db.execute(stmt)).all()

        results = [{
            "document_id": doc.id,
            "file_name": doc.file_name,
            "file_type": doc.file_type,
            "source": doc.source,
            "page_number": extracted.page_number,
            "content_snippet": extracted.content[:200] if extracted.content else "",
            "score": None,
        } for extracted, doc in rows]

        return {"query": query, "total": total, "page": page, "size": size, "results": results}

    # ─── Dashboard Stats ──────────────────────────────────────────────────────

    async def get_stats(self) -> dict[str, Any]:
        """Return stats for the current project database."""
        total = (await self.db.execute(select(func.count(Document.id)))).scalar_one()
        completed = (await self.db.execute(select(func.count(Document.id)).where(Document.status == "completed"))).scalar_one()
        failed = (await self.db.execute(select(func.count(Document.id)).where(Document.status == "failed"))).scalar_one()
        pending = (await self.db.execute(select(func.count(Document.id)).where(Document.status == "pending"))).scalar_one()
        total_pages = (await self.db.execute(select(func.count(ExtractedData.id)))).scalar_one()

        # File type breakdown
        breakdown_rows = (await self.db.execute(
            select(Document.file_type, func.count(Document.id).label("cnt"))
            .group_by(Document.file_type)
        )).all()
        breakdown = {row[0]: row[1] for row in breakdown_rows}

        return {
            "total_documents": total,
            "completed": completed,
            "failed": failed,
            "pending": pending,
            "total_pages_extracted": total_pages,
            "active_keys": 0,  # populated by the route from main DB
            "file_type_breakdown": breakdown,
        }
