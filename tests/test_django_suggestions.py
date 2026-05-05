import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from django_app.views.suggestions import _clear_document_cache, _get_document_text


@pytest.fixture(autouse=True)
def clear_cache():
    _clear_document_cache()


def test_get_document_text_cache_hit():
    import django_app.views.suggestions as views_module

    views_module._cache_valid = True
    views_module._document_text_cache = {"test.pdf": "cached text"}

    assert _get_document_text("test.pdf") == "cached text"


def test_get_document_text_vector_store(monkeypatch):
    from unittest.mock import MagicMock

    # Mock settings
    class MockSettings:
        FAISS_INDEX_PATH = "mock/path"

    monkeypatch.setattr(
        "django_app.views.suggestions.settings", MockSettings(), raising=False
    )

    # Mock load_runtime_embedding_settings
    monkeypatch.setattr(
        "django_app.views.suggestions.load_runtime_embedding_settings",
        lambda: {"embedding_dim": 384},
        raising=False,
    )

    # Mock VectorStore
    mock_vs = MagicMock()
    mock_vs.chunks = [
        {"source": "test.pdf", "page": 1, "text": "page 1 text"},
        {"source": "test.pdf", "page": 0, "text": "page 0 text"},
        {"source": "other.pdf", "page": 0, "text": "other text"},
    ]

    class MockVectorStore:
        @staticmethod
        def get_cached(index_path, embedding_dim):
            return mock_vs

    monkeypatch.setattr(
        "django_app.views.suggestions.VectorStore", MockVectorStore, raising=False
    )

    import app.config

    monkeypatch.setattr(app.config, "settings", MockSettings(), raising=False)

    import app.services.runtime_embedding

    monkeypatch.setattr(
        app.services.runtime_embedding,
        "load_runtime_embedding_settings",
        lambda: {"embedding_dim": 384},
        raising=False,
    )

    import app.services.vector_store

    monkeypatch.setattr(
        app.services.vector_store, "VectorStore", MockVectorStore, raising=False
    )

    text = _get_document_text("test.pdf")
    assert text == "page 0 text page 1 text"


def test_get_document_text_partial_match(monkeypatch):
    from unittest.mock import MagicMock
    import app.config
    import app.services.runtime_embedding
    import app.services.vector_store

    class MockSettings:
        FAISS_INDEX_PATH = "mock/path"

    monkeypatch.setattr(app.config, "settings", MockSettings(), raising=False)

    monkeypatch.setattr(
        app.services.runtime_embedding,
        "load_runtime_embedding_settings",
        lambda: {"embedding_dim": 384},
        raising=False,
    )

    mock_vs = MagicMock()
    mock_vs.chunks = [
        {"source": "/path/to/long/test.pdf", "page": 0, "text": "long text"},
    ]

    class MockVectorStore:
        @staticmethod
        def get_cached(index_path, embedding_dim):
            return mock_vs

    monkeypatch.setattr(
        app.services.vector_store, "VectorStore", MockVectorStore, raising=False
    )

    text = _get_document_text("test.pdf")
    assert text == "long text"


def test_get_document_text_not_found(monkeypatch):
    from unittest.mock import MagicMock
    import app.config
    import app.services.runtime_embedding
    import app.services.vector_store

    class MockSettings:
        FAISS_INDEX_PATH = "mock/path"

    monkeypatch.setattr(app.config, "settings", MockSettings(), raising=False)

    monkeypatch.setattr(
        app.services.runtime_embedding,
        "load_runtime_embedding_settings",
        lambda: {"embedding_dim": 384},
        raising=False,
    )

    mock_vs = MagicMock()
    mock_vs.chunks = []

    class MockVectorStore:
        @staticmethod
        def get_cached(index_path, embedding_dim):
            return mock_vs

    monkeypatch.setattr(
        app.services.vector_store, "VectorStore", MockVectorStore, raising=False
    )

    text = _get_document_text("missing.pdf")
    assert text is None


def test_get_document_text_exception(monkeypatch):
    import app.services.runtime_embedding

    def mock_load():
        raise Exception("Failed")

    monkeypatch.setattr(
        app.services.runtime_embedding,
        "load_runtime_embedding_settings",
        mock_load,
        raising=False,
    )

    text = _get_document_text("test.pdf")
    assert text is None


def test_get_document_text_media_path_txt(tmp_path, monkeypatch):
    from django.conf import settings as django_settings

    # Create mock media root and file
    media_root = tmp_path / "media"
    data_source = media_root / "data_source"
    data_source.mkdir(parents=True)

    test_file = data_source / "test.txt"
    test_file.write_text("hello from file")

    monkeypatch.setattr(django_settings, "MEDIA_ROOT", str(media_root))

    text = _get_document_text("test.txt")
    assert text == "hello from file"


def test_get_document_text_media_path_pdf(tmp_path, monkeypatch):
    import os
    from django.conf import settings as django_settings

    # Create mock media root and file
    media_root = tmp_path / "media"
    data_source = media_root / "data_source"
    data_source.mkdir(parents=True)

    # test_file = data_source / "test.pdf"

    # Fake fitz (PyMuPDF) module
    class MockPage:
        def get_text(self):
            return "hello from pdf"

    class MockDoc:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            pass

        def __iter__(self):
            return iter([MockPage()])

    class MockFitz:
        @staticmethod
        def open(path):
            return MockDoc()

    # Mock os.path.exists and open to pretend file exists
    monkeypatch.setattr(os.path, "exists", lambda p: True)

    import sys

    sys.modules["fitz"] = MockFitz

    monkeypatch.setattr(django_settings, "MEDIA_ROOT", str(media_root))

    text = _get_document_text("test.pdf")
    assert text == "hello from pdf"

    # Clean up
    del sys.modules["fitz"]
