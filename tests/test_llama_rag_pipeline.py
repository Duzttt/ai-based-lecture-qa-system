from unittest.mock import Mock
from app.services.llama_rag_pipeline import LlamaRAGPipeline


def test_llama_rag_pipeline_creation():
    """测试LlamaRAGPipeline创建"""
    mock_index = Mock()
    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    assert pipeline is not None


def test_llama_rag_pipeline_query():
    """测试查询功能"""
    mock_index = Mock()
    mock_query_engine = Mock()
    mock_response = Mock()
    mock_response.response = "测试回答"
    mock_response.source_nodes = []

    mock_index.as_query_engine.return_value = mock_query_engine
    mock_query_engine.query.return_value = mock_response

    mock_retriever = Mock()
    mock_retriever.retrieve.return_value = []
    mock_index.as_retriever.return_value = mock_retriever

    pipeline = LlamaRAGPipeline(mock_index, provider="local")
    result = pipeline.query("测试问题")

    assert "answer" in result
    assert "sources" in result
    assert result["answer"] == "测试回答"
