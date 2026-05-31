from unittest.mock import Mock

import pytest

from app.services.hybrid_retriever_service import HybridRetrieverService


class TestHybridRetrieverService:
    def test_get_instance_returns_singleton(self, monkeypatch):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False

        mock_retriever = Mock(
            retrieve=lambda query, top_k=5: [],
            get_document_count=lambda: 0,
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service._get_hybrid_retriever_class",
            lambda: (Mock(RRF="rrf"), Mock(return_value=mock_retriever)),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            lambda **kwargs: Mock(chunks=[{"text": "doc", "source": "a.pdf", "page": 1}]),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.load_runtime_embedding_settings",
            lambda: {"model_id": "test-model", "embedding_dim": 384},
        )

        instance1 = HybridRetrieverService.get_instance()
        instance2 = HybridRetrieverService.get_instance()
        assert instance1 is instance2

    def test_get_instance_returns_none_when_no_documents(self, monkeypatch):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False

        monkeypatch.setattr(
            "app.services.hybrid_retriever_service._get_hybrid_retriever_class",
            lambda: (Mock(RRF="rrf"), Mock()),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            lambda **kwargs: Mock(chunks=[]),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.load_runtime_embedding_settings",
            lambda: {"model_id": "test-model", "embedding_dim": 384},
        )

        result = HybridRetrieverService.get_instance()
        assert result is None

    def test_refresh_rebuilds_index(self, monkeypatch):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False

        fake_chunks = [
            {"text": "doc1 text", "source": "a.pdf", "page": 1},
            {"text": "doc2 text", "source": "b.pdf", "page": 1},
        ]

        def _make_retriever(documents, model_name, fusion_method):
            return Mock(
                retrieve=lambda query, top_k: [
                    {"text": d["text"], "source": d["source"], "score": 0.9}
                    for d in documents[:top_k]
                ],
                get_document_count=lambda: len(fake_chunks),
            )

        monkeypatch.setattr(
            "app.services.hybrid_retriever_service._get_hybrid_retriever_class",
            lambda: (Mock(RRF="rrf"), _make_retriever),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            lambda **kwargs: Mock(chunks=fake_chunks),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.load_runtime_embedding_settings",
            lambda: {"model_id": "test-model", "embedding_dim": 384},
        )

        service = HybridRetrieverService.get_instance()
        assert service is not None
        assert service.get_document_count() == 2

    def test_search_returns_results(self, monkeypatch):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False

        fake_chunks = [
            {"text": "doc1 text", "source": "a.pdf", "page": 1},
            {"text": "doc2 text", "source": "b.pdf", "page": 2},
        ]

        def _make_retriever(documents, model_name, fusion_method):
            return Mock(
                retrieve=lambda query, top_k: [
                    {"text": "doc1 text", "source": "a.pdf", "score": 0.9}
                ],
                get_document_count=lambda: len(fake_chunks),
            )

        monkeypatch.setattr(
            "app.services.hybrid_retriever_service._get_hybrid_retriever_class",
            lambda: (Mock(RRF="rrf"), _make_retriever),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            lambda **kwargs: Mock(chunks=fake_chunks),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.load_runtime_embedding_settings",
            lambda: {"model_id": "test-model", "embedding_dim": 384},
        )

        service = HybridRetrieverService.get_instance()
        results = service.search("test query", top_k=5)
        assert len(results) == 1
        assert results[0]["text"] == "doc1 text"
        assert results[0]["score"] == 0.9

    def test_clear_resets_singleton(self):
        HybridRetrieverService._instance = Mock()
        HybridRetrieverService._initialized = True
        HybridRetrieverService.clear()
        assert HybridRetrieverService._instance is None
        assert HybridRetrieverService._initialized is False
