import pytest


class TestPDFChunking:
    def test_read_pdf_text_returns_string(self):
        from app.services.pdf_chunking import split_text_into_chunks

        text = "This is a test sentence. Another sentence here. And one more."
        chunks = split_text_into_chunks(text, chunk_size=50)
        assert isinstance(chunks, list)
        assert len(chunks) > 0

    def test_split_text_empty_returns_empty_list(self):
        from app.services.pdf_chunking import split_text_into_chunks

        chunks = split_text_into_chunks("")
        assert chunks == []


class TestEmbeddingService:
    def test_embedding_service_can_be_instantiated(self):
        from app.services.embedding import EmbeddingService

        service = EmbeddingService(model_name="sentence-transformers/all-MiniLM-L6-v2")
        assert service is not None
        assert service.model_name == "sentence-transformers/all-MiniLM-L6-v2"


class TestVectorStore:
    def test_vector_store_can_be_instantiated(self):
        from app.services.vector_store import VectorStore

        store = VectorStore(index_path="data/faiss_index", embedding_dim=384)
        assert store is not None
        assert store.embedding_dim == 384


class TestRAGPipeline:
    def test_rag_pipeline_can_be_instantiated(self):
        from app.services.embedding import EmbeddingService
        from app.services.rag_pipeline import RAGPipeline
        from app.services.vector_store import VectorStore

        embedding_service = EmbeddingService()
        vector_store = VectorStore(index_path="data/faiss_index", embedding_dim=384)
        rag = RAGPipeline(
            embedding_service=embedding_service,
            vector_store=vector_store,
        )
        assert rag is not None
