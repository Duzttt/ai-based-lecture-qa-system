"""
Tests for the citation-aware RAG pipeline.

These tests verify that:
1. The LLM prompt is correctly formatted for JSON output
2. The response parser validates JSON structure
3. The response format includes sentences and sources
"""

import json
import pytest
from unittest.mock import Mock, patch, MagicMock

from app.services.citation_rag import (
    CitationRAGPipeline,
    CitationRAGError,
    query_with_citations,
)


class TestCitationRAGPipelineInitialization:
    """Test CitationRAGPipeline initialization."""

    def test_default_initialization(self):
        """Test pipeline initializes with default settings."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                assert pipeline.model is not None
                assert pipeline.base_url is not None
                assert pipeline.timeout_seconds is not None

    def test_custom_model_initialization(self):
        """Test pipeline initializes with custom model."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline(model="qwen3.5:4b")
                
                assert pipeline.model == "qwen3.5:4b"


class TestCitationPromptBuilding:
    """Test citation prompt building."""

    def test_build_citation_prompt_structure(self):
        """Test that prompt includes required elements."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                chunks = [
                    {"chunk_id": 1, "text": "Agents operate autonomously.", "source": "L1.pdf", "page": 24},
                    {"chunk_id": 2, "text": "They can reason and choose actions.", "source": "L2.pdf", "page": 3},
                ]
                
                prompt = pipeline._build_citation_prompt("What do agents do?", chunks)
                
                # Check prompt contains required elements
                assert "JSON" in prompt
                assert "sentences" in prompt
                assert "citations" in prompt
                assert "[1]" in prompt
                assert "[2]" in prompt
                assert "Agents operate autonomously" in prompt
                assert "They can reason and choose actions" in prompt

    def test_build_citation_prompt_includes_rules(self):
        """Test that prompt includes citation rules."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                chunks = [{"chunk_id": 1, "text": "Test text", "source": "test.pdf", "page": 1}]
                prompt = pipeline._build_citation_prompt("Test?", chunks)
                
                # Check rules are included
                assert "Each sentence MUST have a" in prompt
                assert "citations" in prompt
                assert "empty array" in prompt


class TestResponseParsing:
    """Test LLM response parsing."""

    def test_parse_valid_json_response(self):
        """Test parsing valid JSON response."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                raw_response = json.dumps({
                    "sentences": [
                        {"text": "First sentence.", "citations": [1]},
                        {"text": "Second sentence.", "citations": [1, 2]},
                        {"text": "Third sentence.", "citations": []},
                    ]
                })
                
                parsed = pipeline._parse_llm_response(raw_response)
                
                assert "sentences" in parsed
                assert len(parsed["sentences"]) == 3
                assert parsed["sentences"][0]["citations"] == [1]
                assert parsed["sentences"][2]["citations"] == []

    def test_parse_json_with_markdown_blocks(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                raw_response = '''```json
{
  "sentences": [
    {"text": "Test.", "citations": [1]}
  ]
}
```'''
                
                parsed = pipeline._parse_llm_response(raw_response)
                
                assert len(parsed["sentences"]) == 1

    def test_parse_invalid_json_raises_error(self):
        """Test that invalid JSON raises CitationRAGError."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                with pytest.raises(CitationRAGError, match="Failed to parse"):
                    pipeline._parse_llm_response("not valid json")

    def test_parse_missing_sentences_raises_error(self):
        """Test that missing 'sentences' field raises error."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                raw_response = json.dumps({"answer": "test"})
                
                with pytest.raises(CitationRAGError, match="must contain 'sentences'"):
                    pipeline._parse_llm_response(raw_response)

    def test_parse_invalid_citations_type_raises_error(self):
        """Test that non-array citations raises error."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                raw_response = json.dumps({
                    "sentences": [
                        {"text": "Test.", "citations": "1"}  # Should be array
                    ]
                })
                
                with pytest.raises(CitationRAGError, match="citations must be an array"):
                    pipeline._parse_llm_response(raw_response)


class TestResponseFormatting:
    """Test response formatting with sources."""

    def test_build_response_with_sources(self):
        """Test building response with source metadata."""
        with patch('app.services.citation_rag.EmbeddingService'):
            with patch('app.services.citation_rag.VectorStore'):
                pipeline = CitationRAGPipeline()
                
                sentences_data = {
                    "sentences": [
                        {"text": "Test.", "citations": [1, 2]},
                    ]
                }
                
                chunks = [
                    {"chunk_id": 1, "source": "L1.pdf", "page": 24, "text": "Text 1"},
                    {"chunk_id": 2, "source": "L2.pdf", "page": 3, "text": "Text 2"},
                ]
                
                result = pipeline._build_response_with_sources(sentences_data, chunks)
                
                assert "sentences" in result
                assert "sources" in result
                assert "1" in result["sources"]
                assert "2" in result["sources"]
                assert result["sources"]["1"]["file"] == "L1.pdf"
                assert result["sources"]["1"]["page"] == 24
                assert result["sources"]["2"]["file"] == "L2.pdf"


class TestQueryMethod:
    """Test the main query method."""

    def test_query_returns_structured_response(self):
        """Test that query returns properly structured response."""
        with patch('app.services.citation_rag.EmbeddingService') as mock_embedding:
            with patch('app.services.citation_rag.VectorStore') as mock_vector_store:
                # Mock embedding service
                mock_embedding_instance = Mock()
                mock_embedding_instance.embed_query.return_value = [0.1] * 384
                mock_embedding.return_value = mock_embedding_instance
                
                # Mock vector store
                mock_store_instance = Mock()
                mock_store_instance.search_with_metadata.return_value = [
                    {"text": "Test chunk 1", "source": "L1.pdf", "page": 24},
                    {"text": "Test chunk 2", "source": "L2.pdf", "page": 3},
                ]
                mock_vector_store.get_cached.return_value = mock_store_instance
                
                pipeline = CitationRAGPipeline()
                
                # Mock the LLM generation
                with patch.object(pipeline, '_generate_with_qwen') as mock_generate:
                    mock_generate.return_value = json.dumps({
                        "sentences": [
                            {"text": "Answer sentence 1.", "citations": [1]},
                            {"text": "Answer sentence 2.", "citations": [1, 2]},
                        ]
                    })
                    
                    result = pipeline.query("Test question?", top_k=2)
                    
                    assert "sentences" in result
                    assert "sources" in result
                    assert len(result["sentences"]) == 2
                    assert "1" in result["sources"]
                    assert "2" in result["sources"]

    def test_query_empty_results_returns_fallback(self):
        """Test that empty retrieval returns fallback message."""
        with patch('app.services.citation_rag.EmbeddingService') as mock_embedding:
            with patch('app.services.citation_rag.VectorStore') as mock_vector_store:
                mock_embedding_instance = Mock()
                mock_embedding_instance.embed_query.return_value = [0.1] * 384
                mock_embedding.return_value = mock_embedding_instance
                
                mock_store_instance = Mock()
                mock_store_instance.search_with_metadata.return_value = []
                mock_vector_store.get_cached.return_value = mock_store_instance
                
                pipeline = CitationRAGPipeline()
                
                result = pipeline.query("Test question?")
                
                assert "sentences" in result
                assert len(result["sentences"]) == 1
                assert "No relevant information found" in result["sentences"][0]["text"]
                assert result["sources"] == {}


class TestQueryWithCitationsFunction:
    """Test the convenience function."""

    def test_query_with_citations_calls_pipeline(self):
        """Test that convenience function calls pipeline correctly."""
        with patch('app.services.citation_rag.CitationRAGPipeline') as mock_pipeline_class:
            mock_pipeline = Mock()
            mock_pipeline.query.return_value = {
                "sentences": [{"text": "Test.", "citations": [1]}],
                "sources": {"1": {"file": "test.pdf", "page": 1}},
            }
            mock_pipeline_class.return_value = mock_pipeline
            
            result = query_with_citations("Test?", top_k=1, model="qwen2.5:3b")
            
            mock_pipeline_class.assert_called_once_with(model="qwen2.5:3b")
            mock_pipeline.query.assert_called_once_with(
                "Test?",
                top_k=1,
                source_filter=None,
            )
            assert "sentences" in result


class TestCitationRAGError:
    """Test custom exception."""

    def test_citation_rag_error_creation(self):
        """Test creating CitationRAGError."""
        error = CitationRAGError("Test error message")
        assert str(error) == "Test error message"
