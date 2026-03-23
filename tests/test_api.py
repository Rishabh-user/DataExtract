"""API endpoint tests (requires running database — for integration testing)."""

import pytest
from unittest.mock import AsyncMock, patch


def test_import_main():
    """Smoke test: app module can be imported."""
    from app.api import schemas
    assert schemas.UploadResponse is not None
    assert schemas.DocumentResponse is not None
    assert schemas.SearchResponse is not None


def test_schemas_validation():
    from app.api.schemas import FilterParams, SearchParams

    fp = FilterParams(file_type=".pdf", page=1, size=10)
    assert fp.file_type == ".pdf"

    sp = SearchParams(q="hello")
    assert sp.q == "hello"
    assert sp.page == 1


def test_error_response():
    from app.api.schemas import ErrorResponse

    err = ErrorResponse(error="Not found", detail={"id": 1})
    assert err.error == "Not found"
