import os

import django
from unittest.mock import Mock

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from app.services.local_rag import retrieve_with_faiss


class TestLocalRagHybrid:
    def test_retrieve_with_faiss_uses_hybrid_service_when_available(self, monkeypatch):
        fake_results = [
            {"text": "result 1", "source": "a.pdf", "page": 1, "score": 0.95},
            {"text": "result 2", "source": "a.pdf", "page": 2, "score": 0.80},
        ]

        class FakeHybridService:
            @staticmethod
            def get_instance():
                return FakeHybridService()

            def search(self, query, top_k=5):
                return fake_results

        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService",
            FakeHybridService,
        )

        results = retrieve_with_faiss("test query", top_k=5)
        assert len(results) == 2
        assert results[0]["text"] == "result 1"
        assert results[0]["score"] == 0.95

    def test_retrieve_with_faiss_falls_back_to_dense_when_hybrid_unavailable(
        self, monkeypatch
    ):
        monkeypatch.setattr(
            "app.services.local_rag.HybridRetrieverService",
            type("HS", (), {"get_instance": staticmethod(lambda: None)}),
        )

        fake_results = [
            {"text": "dense result", "source": "b.pdf", "page": 1},
        ]

        monkeypatch.setattr(
            "app.services.local_rag.load_runtime_embedding_settings",
            lambda: {"model_id": "test", "embedding_dim": 384},
        )

        class FakeVectorStore:
            chunks = [{"text": "dense result", "source": "b.pdf", "page": 1}]
            search_with_metadata = classmethod(
                lambda cls, *a, **kw: [
                    {"text": "dense result", "source": "b.pdf", "page": 1}
                ]
            )

            @classmethod
            def get_cached(cls, **kw):
                return FakeVectorStore()

        monkeypatch.setattr(
            "app.services.local_rag.VectorStore",
            FakeVectorStore,
        )

        mock_embed = Mock()
        mock_embed.embed_query.return_value = [0.1] * 384
        monkeypatch.setattr(
            "app.services.local_rag.EmbeddingService",
            lambda **kw: mock_embed,
        )

        results = retrieve_with_faiss("test query", top_k=5)
        assert len(results) == 1
        assert results[0]["text"] == "dense result"
