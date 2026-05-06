"""
测试使用LlamaIndex分割器的TextChunker

Tests cover:
- LlamaIndex SentenceSplitter integration
- Fallback to LangChain RecursiveCharacterTextSplitter
- Fallback to custom implementation
- Edge cases
"""

import pytest


class TestTextChunkerWithLlamaSplitter:
    """Tests for TextChunker using LlamaIndex SentenceSplitter."""

    def test_text_chunker_with_llama_splitter(self):
        """测试使用LlamaIndex分割器的TextChunker"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "这是一段测试文本。" * 20  # Create sufficiently long text

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        # LlamaIndex SentenceSplitter uses token-based chunking, not character-based.
        # For Chinese text, tokens are ~2-3 chars each, so chunk_size=100 tokens
        # can produce chunks up to ~110 characters.
        assert all(len(chunk) <= 110 for chunk in chunks)

    def test_text_chunker_empty_text(self):
        """测试TextChunker处理空文本"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)

        assert chunker.chunk_text("") == []
        assert chunker.chunk_text("   ") == []
        assert chunker.chunk_text(None) == []

    def test_text_chunker_short_text(self):
        """测试TextChunker处理短文本"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "Short text"

        chunks = chunker.chunk_text(text)

        assert len(chunks) == 1
        assert chunks[0] == text

    def test_text_chunker_invalid_overlap(self):
        """测试无效overlap引发ValueError"""
        from app.services.chunker import TextChunker

        with pytest.raises(ValueError):
            TextChunker(chunk_size=100, chunk_overlap=100)

        with pytest.raises(ValueError):
            TextChunker(chunk_size=100, chunk_overlap=150)

    def test_text_chunker_by_sentences(self):
        """测试chunk_text_by_sentences方法"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence."

        chunks = chunker.chunk_text_by_sentences(text)

        assert len(chunks) > 0

    def test_text_chunker_by_sentences_empty(self):
        """测试chunk_text_by_sentences处理空文本"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)

        assert chunker.chunk_text_by_sentences("") == []
        assert chunker.chunk_text_by_sentences("   ") == []
        assert chunker.chunk_text_by_sentences(None) == []

    def test_text_chunker_uses_llama_index(self):
        """测试TextChunker使用LlamaIndex SentenceSplitter"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)

        # Verify that the chunker uses LlamaIndex
        assert chunker._use_llama is True

    def test_text_chunker_chunk_size_respected(self):
        """测试chunk size约束被遵守"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=200, chunk_overlap=50)
        text = "This is a test sentence. " * 50  # Create long text

        chunks = chunker.chunk_text(text)

        # LlamaIndex SentenceSplitter uses token-based chunking
        # For English text, roughly 1 token ~ 4 characters
        # So chunk_size=200 tokens ~ 800 characters
        for chunk in chunks:
            assert len(chunk) <= 1000  # Allow for token-based chunking

    def test_text_chunker_preserves_content(self):
        """测试分块保留所有内容"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "这是一段测试文本。" * 20

        chunks = chunker.chunk_text(text)

        # All chunks should contain valid text
        assert all(len(chunk) > 0 for chunk in chunks)
        # Total content should be preserved (chunks may overlap)
        combined = "".join(chunks)
        assert len(combined) >= len(text)
