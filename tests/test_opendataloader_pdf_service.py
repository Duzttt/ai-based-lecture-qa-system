import pytest
from app.services.opendataloader_pdf_service import (
    OpenDataLoaderPDFError,
    read_pdf_text_opendataloader,
    read_pdf_pages_opendataloader,
    chunk_pdf_with_metadata_opendataloader,
    is_opendataloader_available,
)


def test_is_opendataloader_available_returns_bool():
    result = is_opendataloader_available()
    assert isinstance(result, bool)


def test_read_pdf_text_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_pdf_text_opendataloader("/nonexistent/file.pdf")


def test_read_pdf_pages_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_pdf_pages_opendataloader("/nonexistent/file.pdf")


def test_chunk_pdf_file_not_found():
    with pytest.raises(FileNotFoundError):
        chunk_pdf_with_metadata_opendataloader("/nonexistent/file.pdf")
