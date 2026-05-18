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
        """测试chunk_text_by_sentences方法实际分割长文本"""
        from app.services.chunker import TextChunker

        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "This is sentence number one. " * 10 + "This is sentence number two. " * 10

        chunks = chunker.chunk_text_by_sentences(text)

        assert len(chunks) > 1
        assert all(len(chunk) < len(text) for chunk in chunks)
        for chunk in chunks:
            assert chunk in text

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
        cleaned = text.strip()

        # All chunks should contain valid text
        assert all(len(chunk) > 0 for chunk in chunks)
        # Each chunk must be a valid substring of the original (no corruption)
        for chunk in chunks:
            assert chunk in cleaned
        # Chunks span the full text from start to end
        assert cleaned.startswith(chunks[0])
        assert cleaned.endswith(chunks[-1])


class TestTextChunkerLangChainFallback:
    """Tests for TextChunker falling back to LangChain RecursiveCharacterTextSplitter."""

    def test_text_chunker_langchain_fallback(self, monkeypatch):
        """Test TextChunker uses LangChain when LlamaIndex is unavailable."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        if chunker_module.RecursiveCharacterTextSplitter is None:
            pytest.skip("LangChain not installed")

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 20

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        assert chunker._use_llama is False
        assert chunker._character_splitter is not None

    def test_text_chunker_langchain_sentences_fallback(self, monkeypatch):
        """Test chunk_text_by_sentences uses LangChain when LlamaIndex unavailable."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        if chunker_module.RecursiveCharacterTextSplitter is None:
            pytest.skip("LangChain not installed")

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 5

        chunks = chunker.chunk_text_by_sentences(text)

        assert len(chunks) > 0
        assert chunker._use_llama is False

    def test_text_chunker_langchain_preserves_content(self, monkeypatch):
        """Test LangChain fallback preserves content."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        if chunker_module.RecursiveCharacterTextSplitter is None:
            pytest.skip("LangChain not installed")

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 20

        chunks = chunker.chunk_text(text)
        cleaned = text.strip()

        for chunk in chunks:
            assert chunk in cleaned
        assert cleaned.startswith(chunks[0])
        assert cleaned.endswith(chunks[-1])


class TestTextChunkerCustomFallback:
    """Tests for TextChunker falling back to custom implementation."""

    def test_text_chunker_custom_fallback(self, monkeypatch):
        """Test TextChunker uses custom fallback when both libraries unavailable."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)
        monkeypatch.setattr(chunker_module, "RecursiveCharacterTextSplitter", None)

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 20

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 0
        assert chunker._use_llama is False
        assert chunker._character_splitter is None

    def test_text_chunker_custom_sentences_fallback(self, monkeypatch):
        """Test chunk_text_by_sentences uses custom fallback."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)
        monkeypatch.setattr(chunker_module, "RecursiveCharacterTextSplitter", None)

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "First sentence. Second sentence. Third sentence. Fourth sentence. " * 5

        chunks = chunker.chunk_text_by_sentences(text)

        assert len(chunks) > 0

    def test_text_chunker_custom_fallback_preserves_content(self, monkeypatch):
        """Test custom fallback preserves content."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)
        monkeypatch.setattr(chunker_module, "RecursiveCharacterTextSplitter", None)

        chunker = TextChunker(chunk_size=100, chunk_overlap=20)
        text = "This is a test sentence. " * 20

        chunks = chunker.chunk_text(text)

        cleaned = text.strip()
        for chunk in chunks:
            assert chunk in cleaned
        assert cleaned.startswith(chunks[0])
        assert cleaned.endswith(chunks[-1])

    def test_text_chunker_custom_fallback_chunk_size(self, monkeypatch):
        """Test custom fallback respects chunk size."""
        import app.services.chunker as chunker_module
        from app.services.chunker import TextChunker

        monkeypatch.setattr(chunker_module, "SentenceSplitter", None)
        monkeypatch.setattr(chunker_module, "RecursiveCharacterTextSplitter", None)

        chunker = TextChunker(chunk_size=50, chunk_overlap=10)
        text = "This is a test sentence. " * 20

        chunks = chunker.chunk_text(text)

        for chunk in chunks:
            assert len(chunk) <= 50 + 10  # small tolerance for edge alignment
