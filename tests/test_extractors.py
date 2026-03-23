"""Unit tests for extraction modules."""

import asyncio
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def tmp_csv(tmp_path: Path) -> Path:
    p = tmp_path / "test.csv"
    p.write_text("name,age,city\nAlice,30,NYC\nBob,25,LA\n", encoding="utf-8")
    return p


@pytest.mark.asyncio
async def test_csv_extractor(tmp_csv: Path):
    from app.extraction.csv_extractor import CSVExtractor

    extractor = CSVExtractor()
    assert extractor.can_handle(tmp_csv)
    result = await extractor.extract(tmp_csv)

    assert result.success
    assert len(result.pages) == 1
    assert "Alice" in result.pages[0].content
    assert result.pages[0].metadata["rows"] == 2
    assert result.pages[0].metadata["columns"] == 3


@pytest.fixture
def tmp_txt(tmp_path: Path) -> Path:
    p = tmp_path / "test.txt"
    p.write_text("hello world")
    return p


@pytest.mark.asyncio
async def test_unsupported_extension(tmp_txt: Path):
    from app.extraction.registry import get_extractor

    extractor = get_extractor(tmp_txt)
    assert extractor is None


@pytest.mark.asyncio
async def test_video_extractor_placeholder(tmp_path: Path):
    fake = tmp_path / "video.mp4"
    fake.write_bytes(b"\x00")

    from app.extraction.video_extractor import VideoExtractor

    extractor = VideoExtractor()
    assert extractor.can_handle(fake)
    result = await extractor.extract(fake)
    assert result.success
    assert result.metadata["status"] == "placeholder"


@pytest.mark.asyncio
async def test_extraction_result_to_dict():
    from app.extraction.base import ExtractionResult, PageContent

    result = ExtractionResult(
        pages=[PageContent(page_number=1, content="hello", metadata={"k": "v"})],
        metadata={"total_pages": 1},
    )
    d = result.to_dict()
    assert d["success"] is True
    assert d["pages"][0]["content"] == "hello"
