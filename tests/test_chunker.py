"""
Unit tests for TextChunker with LlamaIndex SentenceSplitter support.

Spec test:
- test_text_chunker_with_llama_splitter (required by spec)

Additional tests (not in original spec):
- test_text_chunker_empty_text
- test_text_chunker_short_text
- test_text_chunker_invalid_overlap
- test_text_chunker_by_sentences
- test_text_chunker_by_sentences_empty
- test_text_chunker_uses_llama_index
- test_text_chunker_chunk_size_respected
- test_text_chunker_preserves_content
"""

import pytest


def test_text_chunker_with_llama_splitter():
    """Test that TextChunker works with LlamaIndex SentenceSplitter."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "这是一段测试文本。" * 20  # Create sufficiently long text

    chunks = chunker.chunk_text(text)

    assert len(chunks) > 0
    # LlamaIndex SentenceSplitter uses token-based chunking
    # For Chinese text, tokens are roughly 1-2 characters each
    # So chunk_size=100 tokens ≈ 100-200 characters; allow small margin
    assert all(len(chunk) <= 110 for chunk in chunks)


# ── Additional tests (not in original spec) ──────────────────────────────


def test_text_chunker_empty_text():
    """Test that TextChunker handles empty text."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)

    assert chunker.chunk_text("") == []
    assert chunker.chunk_text("   ") == []
    assert chunker.chunk_text(None) == []


def test_text_chunker_short_text():
    """Test that TextChunker handles text shorter than chunk_size."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "Short text"

    chunks = chunker.chunk_text(text)

    assert len(chunks) == 1
    assert chunks[0] == text


def test_text_chunker_invalid_overlap():
    """Test that invalid overlap raises ValueError."""
    from app.services.chunker import TextChunker

    with pytest.raises(ValueError):
        TextChunker(chunk_size=100, chunk_overlap=100)

    with pytest.raises(ValueError):
        TextChunker(chunk_size=100, chunk_overlap=150)


def test_text_chunker_by_sentences():
    """Test chunk_text_by_sentences method."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."

    chunks = chunker.chunk_text_by_sentences(text)

    assert len(chunks) > 0


def test_text_chunker_by_sentences_empty():
    """Test chunk_text_by_sentences with empty text."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)

    assert chunker.chunk_text_by_sentences("") == []
    assert chunker.chunk_text_by_sentences("   ") == []
    assert chunker.chunk_text_by_sentences(None) == []


def test_text_chunker_uses_llama_index():
    """Test that TextChunker uses LlamaIndex SentenceSplitter when available."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)

    # Verify that the chunker uses LlamaIndex
    assert chunker._use_llama is True


def test_text_chunker_chunk_size_respected():
    """Test that chunk sizes are approximately respected."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=200, chunk_overlap=50)
    text = "This is a test sentence. " * 50  # Create long text

    chunks = chunker.chunk_text(text)

    # LlamaIndex SentenceSplitter uses token-based chunking
    # For English text, roughly 1 token ≈ 4 characters
    # So chunk_size=200 tokens ≈ 800 characters
    for chunk in chunks:
        assert len(chunk) <= 1000  # Allow for token-based chunking


def test_text_chunker_preserves_content():
    """Test that chunking preserves all content."""
    from app.services.chunker import TextChunker

    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    text = "这是一段测试文本。" * 20

    chunks = chunker.chunk_text(text)

    # All chunks should contain valid text
    assert all(len(chunk) > 0 for chunk in chunks)
    # Total content should be preserved (chunks may overlap)
    combined = "".join(chunks)
    assert len(combined) >= len(text)
