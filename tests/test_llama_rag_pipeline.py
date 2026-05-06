from unittest.mock import Mock
import pytest
from app.services.llama_rag_pipeline import LlamaRAGPipeline, LlamaRAGError


def _make_mock_node(text: str, source: str, page: int, score: float):
    node = Mock()
    node.node.text = text
    node.node.metadata = {"source": source, "page": page}
    node.score = score
    return node


def test_llama_rag_pipeline_creation():
    mock_index = Mock()
    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    assert pipeline is not None


def test_llama_rag_pipeline_retrieve_transforms_nodes():
    mock_index = Mock()
    node1 = _make_mock_node("chunk A", "doc.pdf", 1, 0.9)
    node2 = _make_mock_node("chunk B", "doc.pdf", 3, 0.7)

    mock_retriever = Mock()
    mock_retriever.retrieve.return_value = [node1, node2]
    mock_index.as_retriever.return_value = mock_retriever

    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    results = pipeline.retrieve("test query", top_k=2)

    assert len(results) == 2
    assert results[0]["rank"] == 1
    assert results[0]["text"] == "chunk A"
    assert results[0]["source"] == "doc.pdf"
    assert results[0]["page"] == 1
    assert results[0]["distance"] == pytest.approx(0.1)
    assert results[1]["rank"] == 2
    assert results[1]["text"] == "chunk B"
    assert results[1]["distance"] == pytest.approx(0.3)


def test_llama_rag_pipeline_retrieve_handles_none_score():
    mock_index = Mock()
    node = _make_mock_node("chunk", "doc.pdf", 1, None)

    mock_retriever = Mock()
    mock_retriever.retrieve.return_value = [node]
    mock_index.as_retriever.return_value = mock_retriever

    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    results = pipeline.retrieve("query")

    assert len(results) == 1
    assert results[0]["distance"] == 1.0  # score defaults to 0.0 when None, distance = 1 - 0


def test_llama_rag_pipeline_query_full_flow():
    mock_index = Mock()
    node = _make_mock_node("answer context", "lec.pdf", 5, 0.85)
    mock_query_engine = Mock()
    mock_response = Mock()
    mock_response.response = "generated answer"

    mock_index.as_query_engine.return_value = mock_query_engine
    mock_query_engine.query.return_value = mock_response

    mock_retriever = Mock()
    mock_retriever.retrieve.return_value = [node]
    mock_index.as_retriever.return_value = mock_retriever

    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    result = pipeline.query("test question")

    assert result["answer"] == "generated answer"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["text"] == "answer context"
    called_prompt = mock_query_engine.query.call_args[0][0]
    assert "answer context" in called_prompt
    assert "test question" in called_prompt


def test_llama_rag_pipeline_generate_answer_empty_context():
    mock_index = Mock()
    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    result = pipeline.generate_answer("query", [])
    assert "cannot answer" in result.lower()


def test_llama_rag_pipeline_retrieve_raises_on_error():
    mock_index = Mock()
    mock_retriever = Mock()
    mock_retriever.retrieve.side_effect = RuntimeError("network error")
    mock_index.as_retriever.return_value = mock_retriever

    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    with pytest.raises(LlamaRAGError, match="Retrieval failed"):
        pipeline.retrieve("query")


def test_llama_rag_pipeline_generate_raises_on_llm_error():
    mock_index = Mock()
    mock_query_engine = Mock()
    mock_query_engine.query.side_effect = RuntimeError("LLM timeout")
    mock_index.as_query_engine.return_value = mock_query_engine

    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    sources = [{"text": "ctx", "source": "s", "page": 1}]
    with pytest.raises(LlamaRAGError, match="Answer generation failed"):
        pipeline.generate_answer("query", sources)


def test_llama_rag_pipeline_build_context():
    sources = [
        {"text": "hello", "source": "a.pdf", "page": 1},
        {"text": "world", "source": "b.pdf", "page": None},
    ]
    result = LlamaRAGPipeline._build_context(sources)
    assert "[S1]" in result
    assert "hello" in result
    assert "[S2]" in result
    assert "world" in result
    assert "unknown" in result
