from pathlib import Path
from typing import Optional
from unittest.mock import Mock

import numpy as np
import pytest

from app.services.pdf_indexing import (
    PDFIndexingError,
    index_pdf_directory,
    index_pdf_file,
)


class _DummyEmbeddingService:
    def __init__(self, model_name="dummy-model"):
        self.model_name = model_name

    def embed_texts(self, texts):
        return np.array(
            [
                [0.1, 0.2, 0.3],
                [0.4, 0.5, 0.6],
            ]
        )


class _DummyIndex:
    def __init__(self, d, ntotal=0):
        self.d = d
        self.ntotal = ntotal


class _DummyVectorStore:
    def __init__(self, index_path, embedding_dim=384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.index = _DummyIndex(d=embedding_dim, ntotal=0)
        self.chunks = []

    def clear(self):
        self.index.ntotal = 0
        self.chunks = []

    def add_embeddings(self, embeddings, chunks):
        self.index.ntotal += len(chunks)
        self.chunks.extend(chunks)

    def save(self):
        return None

    def get_total_chunks(self):
        return len(self.chunks)

    @classmethod
    def set_cached(cls, store):
        pass


def test_index_pdf_file_success(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.services.pdf_indexing.read_pdf_text", lambda _: "mock text"
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.chunk_pdf_with_metadata",
        lambda pdf_path, chunk_size=500, source_name=None: [
            {"text": "chunk-1", "source": source_name or "dummy.pdf", "page": 1},
            {"text": "chunk-2", "source": source_name or "dummy.pdf", "page": 2},
        ],
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        _DummyEmbeddingService,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        _DummyVectorStore,
    )

    result = index_pdf_file("dummy.pdf", chunk_size=500)

    assert result["chunks_created"] == 2
    assert result["total_chunks_in_index"] == 2
    assert result["total_chars"] == len("mock text")


def test_index_pdf_file_strips_pdf_path(monkeypatch: pytest.MonkeyPatch):
    received = {"path": None, "source_name": None}

    def _fake_read_pdf_text(path: str) -> str:
        received["path"] = path
        return "mock text"

    monkeypatch.setattr("app.services.pdf_indexing.read_pdf_text", _fake_read_pdf_text)

    def _fake_chunk_pdf_with_metadata(pdf_path: str, chunk_size=500, source_name=None):
        received["source_name"] = source_name
        return [
            {"text": "chunk-1", "source": source_name or "dummy.pdf", "page": 1},
            {"text": "chunk-2", "source": source_name or "dummy.pdf", "page": 2},
        ]

    monkeypatch.setattr(
        "app.services.pdf_indexing.chunk_pdf_with_metadata",
        _fake_chunk_pdf_with_metadata,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        _DummyEmbeddingService,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        _DummyVectorStore,
    )

    index_pdf_file("  dummy.pdf  ", chunk_size=500)

    assert received["path"] == "dummy.pdf"
    assert received["source_name"] == "dummy.pdf"


def test_index_pdf_file_raises_on_empty_chunks(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "app.services.pdf_indexing.read_pdf_text", lambda _: "mock text"
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.chunk_pdf_with_metadata",
        lambda pdf_path, chunk_size=500, source_name=None: [],
    )

    with pytest.raises(PDFIndexingError, match="No chunks created from text"):
        index_pdf_file("dummy.pdf", chunk_size=500)


def test_index_pdf_file_raises_on_dimension_mismatch(
    monkeypatch: pytest.MonkeyPatch,
):
    class _MismatchVectorStore(_DummyVectorStore):
        def __init__(self, index_path, embedding_dim=384):
            super().__init__(index_path=index_path, embedding_dim=embedding_dim)
            self.index = _DummyIndex(d=999, ntotal=1)

    monkeypatch.setattr(
        "app.services.pdf_indexing.read_pdf_text", lambda _: "mock text"
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.chunk_pdf_with_metadata",
        lambda pdf_path, chunk_size=500, source_name=None: [
            {"text": "chunk-1", "source": source_name or "dummy.pdf", "page": 1},
            {"text": "chunk-2", "source": source_name or "dummy.pdf", "page": 2},
        ],
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        _DummyEmbeddingService,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        _MismatchVectorStore,
    )

    with pytest.raises(PDFIndexingError, match="Embedding dimension mismatch"):
        index_pdf_file("dummy.pdf", chunk_size=500)


def test_index_pdf_directory_full_rebuild(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4")
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4")

    calls = []

    def _fake_index_pdf_file(
        pdf_path: str,
        chunk_size: int = 500,
        index_path: Optional[str] = None,
        model_name: Optional[str] = None,
        clear_existing: bool = False,
    ):
        calls.append(
            (Path(pdf_path).name, clear_existing, chunk_size, index_path, model_name)
        )
        return {
            "total_chars": 10,
            "chunks_created": 2,
            "total_chunks_in_index": len(calls) * 2,
        }

    monkeypatch.setattr(
        "app.services.pdf_indexing.index_pdf_file", _fake_index_pdf_file
    )

    result = index_pdf_directory(
        data_source_dir=str(tmp_path),
        chunk_size=256,
        index_path="data/faiss_index",
        model_name="test-model",
        clear_existing=True,
    )

    assert calls[0][:2] == ("a.pdf", True)
    assert calls[1][:2] == ("b.pdf", False)
    assert calls[0][2:] == (256, "data/faiss_index", "test-model")
    assert calls[1][2:] == (256, "data/faiss_index", "test-model")
    assert result["processed_pdfs"] == 2
    assert result["chunks_created"] == 4
    assert result["total_chunks_in_index"] == 4


def test_index_pdf_directory_raises_on_empty_dir(tmp_path: Path):
    with pytest.raises(PDFIndexingError, match="No PDF files found"):
        index_pdf_directory(str(tmp_path))


def test_index_calls_hybrid_refresh(monkeypatch):
    import app.services.hybrid_retriever_service as hrs
    from app.services.pdf_indexing import index_pdf_file
    import tempfile
    import os

    refresh_called = False

    def _mock_refresh():
        nonlocal refresh_called
        refresh_called = True

    monkeypatch.setattr(hrs.HybridRetrieverService, "refresh", staticmethod(_mock_refresh))

    # Mock get_pdf_parser to return a mock parser
    mock_parser = {
        "name": "mock",
        "read_text": lambda path: "mock extracted text",
        "read_pages": lambda path: [],
        "chunk_with_metadata": lambda pdf_path, chunk_size=500, source_name=None: [
            {"text": "test chunk", "source": source_name or "test.pdf", "page": 1},
        ],
    }
    monkeypatch.setattr(
        "app.services.pdf_indexing.get_pdf_parser",
        lambda: mock_parser,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        lambda **kw: Mock(embed_texts=lambda texts: np.array([[0.1] * 384])),
    )
    # VectorStore needs to be a class that can be instantiated and have methods called
    mock_store_instance = Mock(
        add_embeddings=lambda e, c: None,
        save=lambda: None,
        get_total_chunks=lambda: 1,
        index=Mock(ntotal=0, d=384),
    )
    mock_store_class = Mock(
        return_value=mock_store_instance,
    )
    mock_store_class.get_cached = lambda **kw: mock_store_instance
    mock_store_class.set_cached = lambda store: None

    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        mock_store_class,
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.load_runtime_embedding_settings",
        lambda: {"model_id": "test-model", "embedding_dim": 384},
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.settings",
        Mock(FAISS_INDEX_PATH="/tmp/test_index", PDF_PARSER="pypdf"),
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test content")
        pdf_path = f.name

    try:
        index_pdf_file(pdf_path, clear_existing=True)
        assert refresh_called, "HybridRetrieverService.refresh() should be called"
    finally:
        os.unlink(pdf_path)
