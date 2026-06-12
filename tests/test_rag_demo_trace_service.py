import requests

import pytest


def _install_happy_path_mocks(monkeypatch: pytest.MonkeyPatch, trace_service):
    captured = {"source_filter": None, "generate_called": False}

    class FakeEmbeddingService:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed_query(self, query: str):
            return [0.1, 0.2, 0.3]

    class FakeVectorStore:
        chunks = [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
            },
            {
                "text": "Dense retrieval compares vector embeddings.",
                "source": "lecture-b.pdf",
                "page": 2,
            },
        ]

        def search_with_metadata(self, query_embedding, top_k: int):
            return [
                {
                    "text": "Retrieval augmented generation uses retrieved context.",
                    "source": "lecture-a.pdf",
                    "page": 1,
                    "distance": 0.2,
                },
                {
                    "text": "Dense retrieval compares vector embeddings.",
                    "source": "lecture-b.pdf",
                    "page": 2,
                    "distance": 0.8,
                },
            ][:top_k]

    monkeypatch.setattr(
        trace_service,
        "load_runtime_embedding_settings",
        lambda: {"model_id": "test-embedding", "embedding_dim": 3},
    )
    monkeypatch.setattr(
        trace_service,
        "load_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "test-llm",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )
    monkeypatch.setattr(
        trace_service.EmbeddingService,
        "__init__",
        lambda self, model_name: setattr(self, "model_name", model_name),
    )
    monkeypatch.setattr(
        trace_service.EmbeddingService,
        "embed_query",
        lambda self, query: [0.1, 0.2, 0.3],
    )
    monkeypatch.setattr(
        trace_service.VectorStore,
        "get_cached",
        lambda index_path, embedding_dim: FakeVectorStore(),
    )

    def fake_retrieve_with_faiss(query, top_k=5, source_filter=None):
        captured["source_filter"] = source_filter
        return [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
                "distance": 0.2,
                "score": 0.9,
            }
        ]

    def fake_generate(
        query,
        context,
        model=None,
        temperature=0.7,
        timeout_seconds=60,
        return_log=False,
        return_thinking=False,
    ):
        captured["generate_called"] = True
        return "RAG answers by grounding generation in retrieved context."

    monkeypatch.setattr(trace_service, "retrieve_with_faiss", fake_retrieve_with_faiss)
    monkeypatch.setattr(
        trace_service,
        "build_context_from_sources",
        lambda sources: "[S1] lecture-a.pdf\nRetrieval augmented generation uses retrieved context.",
    )
    monkeypatch.setattr(trace_service, "generate", fake_generate)

    return captured


def test_build_rag_demo_trace_returns_ordered_english_stages(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="What is RAG?",
        source_filter=None,
        top_k=3,
        include_answer=True,
    )

    stage_ids = [stage["id"] for stage in trace["stages"]]
    assert stage_ids == [
        "user_question",
        "query_processing",
        "embedding_generation",
        "bm25_retrieval",
        "dense_retrieval",
        "hybrid_ranking",
        "context_building",
        "llm_generation",
        "final_answer",
    ]
    assert trace["query"] == "What is RAG?"
    assert trace["retrieved_chunks"][0]["source"] == "lecture-a.pdf"
    assert trace["context_preview"].startswith("[S1]")
    assert trace["answer"].startswith("RAG answers")
    assert all(stage["title"] for stage in trace["stages"])
    assert all(stage["summary"] for stage in trace["stages"])


def test_build_rag_demo_trace_skips_generation_when_include_answer_false(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    captured = _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="Explain dense retrieval",
        source_filter=None,
        top_k=2,
        include_answer=False,
    )

    llm_stage = next(stage for stage in trace["stages"] if stage["id"] == "llm_generation")
    final_stage = next(stage for stage in trace["stages"] if stage["id"] == "final_answer")
    assert llm_stage["status"] == "skipped"
    assert final_stage["status"] == "skipped"
    assert trace["answer"] == ""
    assert captured["generate_called"] is False


def test_build_rag_demo_trace_passes_source_filter_to_hybrid_retrieval(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    captured = _install_happy_path_mocks(monkeypatch, trace_service)

    trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=["lecture-a.pdf"],
        top_k=4,
        include_answer=False,
    )

    assert captured["source_filter"] == ["lecture-a.pdf"]


def test_build_rag_demo_trace_preserves_retrieval_when_llm_times_out(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    def timeout_generate(*args, **kwargs):
        raise requests.exceptions.Timeout("model timed out")

    monkeypatch.setattr(trace_service, "generate", timeout_generate)

    trace = trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=None,
        top_k=3,
        include_answer=True,
    )

    llm_stage = next(stage for stage in trace["stages"] if stage["id"] == "llm_generation")
    final_stage = next(stage for stage in trace["stages"] if stage["id"] == "final_answer")
    assert llm_stage["status"] == "failed"
    assert "timed out" in llm_stage["summary"].lower()
    assert final_stage["status"] == "skipped"
    assert trace["retrieved_chunks"]
    assert trace["answer"] == ""
