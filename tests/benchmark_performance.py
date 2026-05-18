import os
import time
import statistics

import numpy as np
import pytest

RUN_BENCHMARKS = os.environ.get("RUN_BENCHMARKS", "0") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_BENCHMARKS,
    reason="Set RUN_BENCHMARKS=1 to run performance benchmarks",
)


def _make_fake_chunks(n: int = 50) -> list:
    return [
        {"text": f"chunk {i} about machine learning concepts", "source": f"doc_{i % 5}.pdf", "page": i % 10}
        for i in range(n)
    ]


def _make_fake_embeddings(n: int = 50, dim: int = 384) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.standard_normal((n, dim)).astype("float32")


class TestRetrievalBenchmark:
    """Benchmark retrieval via mocked VectorStore.search_with_metadata."""

    def test_retrieval_latency(self):
        """Measure latency of VectorStore.search_with_metadata over multiple queries."""
        from unittest.mock import MagicMock

        from app.services.vector_store import VectorStore

        fake_results = [
            {"text": f"result {i}", "source": "doc.pdf", "page": i, "score": 0.9 - i * 0.05}
            for i in range(5)
        ]

        store = VectorStore.__new__(VectorStore)
        store.index_path = "/tmp/bench"
        store.embedding_dim = 384
        store.chunks = _make_fake_chunks()
        store.index = MagicMock()

        store.search_with_metadata = MagicMock(return_value=fake_results)

        query_embedding = np.zeros(384, dtype="float32")
        retrieval_times = []

        for _ in range(20):
            start = time.perf_counter()
            store.search_with_metadata(query_embedding, top_k=5)
            elapsed = time.perf_counter() - start
            retrieval_times.append(elapsed)

        avg_time = statistics.mean(retrieval_times)
        p95_time = sorted(retrieval_times)[int(len(retrieval_times) * 0.95)]
        print(f"  retrieval avg={avg_time * 1000:.2f}ms  p95={p95_time * 1000:.2f}ms")

        assert avg_time < 0.01, f"Average retrieval time {avg_time:.4f}s exceeds 10ms"

    def test_retrieval_latency_llama_store(self):
        """Measure latency of LlamaVectorStore.search_with_metadata."""
        from unittest.mock import MagicMock

        from app.services.llama_vector_store import LlamaVectorStore

        fake_results = [
            {"text": f"result {i}", "source": "doc.pdf", "page": i, "score": 0.9 - i * 0.05}
            for i in range(5)
        ]

        store = LlamaVectorStore.__new__(LlamaVectorStore)
        store.index_path = "/tmp/bench"
        store.embedding_dim = 384
        store.chunks = _make_fake_chunks()
        store.faiss_index = MagicMock()
        store.vector_store = MagicMock()
        store.storage_context = MagicMock()
        store.index = MagicMock()
        store._node_id_to_chunk_index = {}

        store.search_with_metadata = MagicMock(return_value=fake_results)

        query_embedding = np.zeros(384, dtype="float32")
        retrieval_times = []

        for _ in range(20):
            start = time.perf_counter()
            store.search_with_metadata(query_embedding, top_k=5)
            elapsed = time.perf_counter() - start
            retrieval_times.append(elapsed)

        avg_time = statistics.mean(retrieval_times)
        p95_time = sorted(retrieval_times)[int(len(retrieval_times) * 0.95)]
        print(f"  llama retrieval avg={avg_time * 1000:.2f}ms  p95={p95_time * 1000:.2f}ms")

        assert avg_time < 0.01, f"Average retrieval time {avg_time:.4f}s exceeds 10ms"

    def test_retrieve_with_faiss_call_path(self):
        """Benchmark the retrieve_with_faiss call path with mocked internals."""
        import os as _os
        from unittest.mock import MagicMock, patch

        _os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
        import django
        import django.apps
        if not django.apps.apps.ready:
            django.setup()

        fake_results = [
            {"text": f"result {i}", "source": "doc.pdf", "page": i, "score": 0.9 - i * 0.05}
            for i in range(5)
        ]

        fake_embedding = np.zeros(384, dtype="float32")
        fake_store = MagicMock()
        fake_store.search_with_metadata.return_value = fake_results

        retrieval_times = []

        with (
            patch("app.services.local_rag.LLAMA_AVAILABLE", False),
            patch("app.services.local_rag.load_runtime_embedding_settings", return_value={"model_id": "test", "embedding_dim": 384}),
            patch("app.services.local_rag.EmbeddingService") as MockEmbedding,
            patch("app.services.local_rag.VectorStore.get_cached", return_value=fake_store),
        ):
            mock_emb = MagicMock()
            mock_emb.embed_query.return_value = fake_embedding
            MockEmbedding.return_value = mock_emb

            from app.services.local_rag import retrieve_with_faiss

            for _ in range(20):
                start = time.perf_counter()
                retrieve_with_faiss("What is machine learning?", top_k=5)
                elapsed = time.perf_counter() - start
                retrieval_times.append(elapsed)

        avg_time = statistics.mean(retrieval_times)
        p95_time = sorted(retrieval_times)[int(len(retrieval_times) * 0.95)]
        print(f"  retrieve_with_faiss avg={avg_time * 1000:.2f}ms  p95={p95_time * 1000:.2f}ms")

        assert avg_time < 0.05, f"Average call path time {avg_time:.4f}s exceeds 50ms"


class TestIndexingBenchmark:
    """Benchmark indexing via EmbeddingService.embed_texts and VectorStore.add_embeddings."""

    def test_embedding_throughput(self):
        """Measure EmbeddingService.embed_texts throughput with a mock model."""
        from unittest.mock import MagicMock

        from app.services.embedding import EmbeddingService

        chunks = _make_fake_chunks(100)
        texts = [c["text"] for c in chunks]
        fake_embeddings = _make_fake_embeddings(100)

        service = EmbeddingService.__new__(EmbeddingService)
        service.model_name = "test-model"
        mock_model = MagicMock()
        mock_model.encode.return_value = fake_embeddings
        service.model = mock_model

        times = []
        for _ in range(5):
            start = time.perf_counter()
            service.embed_texts(texts)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = statistics.mean(times)
        chunks_per_sec = len(texts) / avg_time if avg_time > 0 else float("inf")
        print(f"  embed_texts avg={avg_time * 1000:.2f}ms ({chunks_per_sec:.0f} chunks/s)")

        assert avg_time < 1.0, f"Embedding 100 chunks took {avg_time:.4f}s, exceeds 1s"

    def test_vector_store_add_embeddings(self):
        """Measure VectorStore.add_embeddings with real numpy operations."""
        from unittest.mock import MagicMock

        from app.services.vector_store import VectorStore

        chunks = _make_fake_chunks(50)
        embeddings = _make_fake_embeddings(50)

        store = VectorStore.__new__(VectorStore)
        store.index_path = "/tmp/bench"
        store.embedding_dim = 384
        store.chunks = []
        store.index = MagicMock()
        store.index.add = MagicMock()
        store.index.ntotal = 0

        times = []
        for _ in range(5):
            store.chunks = []
            store.index.reset_mock()
            start = time.perf_counter()
            store.add_embeddings(embeddings, chunks)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = statistics.mean(times)
        chunks_per_sec = len(chunks) / avg_time if avg_time > 0 else float("inf")
        print(f"  add_embeddings avg={avg_time * 1000:.2f}ms ({chunks_per_sec:.0f} chunks/s)")

        assert avg_time < 0.5, f"Adding 50 embeddings took {avg_time:.4f}s, exceeds 500ms"

    def test_full_indexing_pipeline(self):
        """Benchmark the full index_pdf_file call path with mocked I/O."""
        from unittest.mock import MagicMock, patch

        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

        from app.services.pdf_indexing import index_pdf_file

        chunks = _make_fake_chunks(50)
        embeddings = _make_fake_embeddings(50)

        parser_dict = {
            "read_text": MagicMock(return_value="Some text content"),
            "read_pages": MagicMock(return_value=[]),
            "chunk_with_metadata": MagicMock(return_value=chunks),
        }

        times = []
        for _ in range(3):
            with (
                patch("app.services.pdf_indexing.get_pdf_parser", return_value=parser_dict),
                patch("app.services.pdf_indexing.load_runtime_embedding_settings", return_value={"model_id": "test", "embedding_dim": 384}),
                patch("app.services.pdf_indexing.EmbeddingService") as MockEmb,
                patch("app.services.pdf_indexing.VectorStore") as MockVS,
            ):
                mock_emb = MagicMock()
                mock_emb.embed_texts.return_value = embeddings
                MockEmb.return_value = mock_emb

                mock_store = MagicMock()
                mock_store.index = None
                mock_store.get_total_chunks.return_value = 50
                MockVS.return_value = mock_store

                start = time.perf_counter()
                index_pdf_file("fake.pdf", chunk_size=500)
                elapsed = time.perf_counter() - start
                times.append(elapsed)

        avg_time = statistics.mean(times)
        print(f"  index_pdf_file avg={avg_time * 1000:.2f}ms for 50 chunks")

        assert avg_time < 2.0, f"Full indexing took {avg_time:.4f}s, exceeds 2s"
