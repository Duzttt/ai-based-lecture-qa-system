"""
Tests for the citation-aware RAG pipeline (now in local_rag.py).

These tests verify that:
1. The LLM prompt is correctly formatted for JSON output
2. The response parser validates JSON structure
3. The response format includes sentences and sources
"""

import json
import pytest
from unittest.mock import Mock, patch

from app.services.local_rag import (
    CitationRAGError,
    _build_citation_prompt,
    _build_citation_response,
    _parse_citation_response,
    query_with_citations,
)


class TestCitationPromptBuilding:
    def test_build_citation_prompt_structure(self):
        chunks = [
            {"chunk_id": 1, "text": "Agents operate autonomously.", "source": "L1.pdf", "page": 24},
            {"chunk_id": 2, "text": "They can reason and choose actions.", "source": "L2.pdf", "page": 3},
        ]
        prompt = _build_citation_prompt("What do agents do?", chunks)

        assert "JSON" in prompt
        assert "sentences" in prompt
        assert "citations" in prompt
        assert "[1]" in prompt
        assert "[2]" in prompt
        assert "Agents operate autonomously" in prompt
        assert "They can reason and choose actions" in prompt

    def test_build_citation_prompt_includes_rules(self):
        chunks = [{"chunk_id": 1, "text": "Test text", "source": "test.pdf", "page": 1}]
        prompt = _build_citation_prompt("Test?", chunks)

        assert "Each sentence MUST have a" in prompt
        assert "citations" in prompt
        assert "empty array" in prompt


class TestResponseParsing:
    def test_parse_valid_json_response(self):
        raw_response = json.dumps({
            "sentences": [
                {"text": "First sentence.", "citations": [1]},
                {"text": "Second sentence.", "citations": [1, 2]},
                {"text": "Third sentence.", "citations": []},
            ]
        })
        parsed = _parse_citation_response(raw_response)

        assert "sentences" in parsed
        assert len(parsed["sentences"]) == 3
        assert parsed["sentences"][0]["citations"] == [1]
        assert parsed["sentences"][2]["citations"] == []

    def test_parse_json_with_markdown_blocks(self):
        raw_response = '''```json
{
  "sentences": [
    {"text": "Test.", "citations": [1]}
  ]
}
```'''
        parsed = _parse_citation_response(raw_response)
        assert len(parsed["sentences"]) == 1

    def test_parse_invalid_json_raises_error(self):
        with pytest.raises(CitationRAGError, match="Failed to parse"):
            _parse_citation_response("not valid json")

    def test_parse_missing_sentences_raises_error(self):
        raw_response = json.dumps({"answer": "test"})
        with pytest.raises(CitationRAGError, match="sentences"):
            _parse_citation_response(raw_response)

    def test_parse_invalid_citations_type_raises_error(self):
        raw_response = json.dumps({
            "sentences": [
                {"text": "Test.", "citations": "1"}
            ]
        })
        with pytest.raises(CitationRAGError, match="citations must be an array"):
            _parse_citation_response(raw_response)


class TestResponseFormatting:
    def test_build_response_with_sources(self):
        sentences_data = {
            "sentences": [
                {"text": "Test.", "citations": [1, 2]},
            ]
        }
        chunks = [
            {"chunk_id": 1, "source": "L1.pdf", "page": 24, "text": "Text 1"},
            {"chunk_id": 2, "source": "L2.pdf", "page": 3, "text": "Text 2"},
        ]
        result = _build_citation_response(sentences_data, chunks)

        assert "sentences" in result
        assert "sources" in result
        assert "1" in result["sources"]
        assert "2" in result["sources"]
        assert result["sources"]["1"]["file"] == "L1.pdf"
        assert result["sources"]["1"]["page"] == 24
        assert result["sources"]["2"]["file"] == "L2.pdf"


class TestQueryWithCitations:
    @patch("app.services.local_rag.VectorStore")
    @patch("app.services.local_rag.EmbeddingService")
    def test_query_with_citations_calls_pipeline(self, mock_embedding_cls, mock_vs_cls):
        mock_embedding = Mock()
        mock_embedding.embed_query.return_value = [0.1] * 384
        mock_embedding_cls.return_value = mock_embedding

        mock_store = Mock()
        mock_store.search_with_metadata.return_value = [
            {"text": "Test chunk 1", "source": "L1.pdf", "page": 24, "chunk_id": 1},
        ]
        mock_vs_cls.get_cached.return_value = mock_store

        with patch("app.services.local_rag._generate_citation_with_qwen") as mock_gen:
            mock_gen.return_value = json.dumps({
                "sentences": [{"text": "Answer.", "citations": [1]}]
            })
            result = query_with_citations("Test?", top_k=1)

            assert "sentences" in result
            assert "sources" in result

    @patch("app.services.local_rag.VectorStore")
    @patch("app.services.local_rag.EmbeddingService")
    def test_query_empty_results_returns_fallback(self, mock_embedding_cls, mock_vs_cls):
        mock_embedding = Mock()
        mock_embedding.embed_query.return_value = [0.1] * 384
        mock_embedding_cls.return_value = mock_embedding

        mock_store = Mock()
        mock_store.search_with_metadata.return_value = []
        mock_vs_cls.get_cached.return_value = mock_store

        result = query_with_citations("Test?")

        assert "sentences" in result
        assert len(result["sentences"]) == 1
        assert "No relevant information found" in result["sentences"][0]["text"]
        assert result["sources"] == {}


class TestCitationRAGError:
    def test_citation_rag_error_creation(self):
        error = CitationRAGError("Test error message")
        assert str(error) == "Test error message"
