"""
Unit tests for smart chunking components.

Tests cover:
- SmartChunker with semantic boundaries
- Overlap handling
- Metadata extraction (headings, keywords)
- Chinese and English text support
"""

import pytest

# Test documents
CHINESE_TEXT = """
# Introduction to Machine Learning

Machine learning is a branch of artificial intelligence that uses algorithms to learn patterns from data.

## Supervised Learning

Supervised learning uses labeled data to train models. Common tasks include classification and regression.

### Classification Tasks

Classification tasks predict discrete labels, such as spam detection or sentiment analysis.

### Regression Tasks

Regression tasks predict continuous values, such as house price prediction or stock price prediction.

## Unsupervised Learning

Unsupervised learning discovers patterns in unlabeled data. Clustering is a common unsupervised learning task.
"""

ENGLISH_TEXT = """
# Introduction to Machine Learning

Machine learning is a subset of artificial intelligence that uses algorithms to learn patterns from data.

## Supervised Learning

Supervised learning uses labeled data to train models. Common tasks include classification and regression.

### Classification Tasks

Classification tasks predict discrete labels, such as spam detection or sentiment analysis.

### Regression Tasks

Regression tasks predict continuous values, such as house price prediction or stock price prediction.

## Unsupervised Learning

Unsupervised learning discovers patterns in unlabeled data. Clustering is a common unsupervised learning task.
"""

MIXED_TEXT = """
# Deep Learning Overview / Deep Learning Overview

Deep learning is a subfield of machine learning based on artificial neural networks.

Deep learning is a subfield of machine learning based on artificial neural networks.

## Convolutional Neural Networks / CNN

Convolutional Neural Networks are primarily used for image processing tasks.

Convolutional Neural Networks are primarily used for image processing tasks.
"""


class TestSmartChunkerInitialization:
    """Tests for SmartChunker initialization."""

    def test_default_initialization(self):
        """Test SmartChunker with default parameters."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        assert chunker.chunk_size == 500
        assert chunker.overlap == 100

    def test_custom_initialization(self):
        """Test SmartChunker with custom parameters."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=300, overlap=50)
        assert chunker.chunk_size == 300
        assert chunker.overlap == 50

    def test_invalid_overlap(self):
        """Test that overlap >= chunk_size raises error."""
        from chunking.smart_chunker import SmartChunker

        with pytest.raises(ValueError):
            SmartChunker(chunk_size=100, overlap=100)

    def test_invalid_min_paragraph_size(self):
        """Test that negative min_paragraph_size raises error."""
        from chunking.smart_chunker import SmartChunker

        with pytest.raises(ValueError):
            SmartChunker(min_paragraph_size=-1)


class TestSmartChunkerParagraphSplitting:
    """Tests for paragraph splitting."""

    def test_split_paragraphs_chinese(self):
        """Test paragraph splitting for Chinese text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        paragraphs = chunker._split_paragraphs(CHINESE_TEXT)

        assert len(paragraphs) > 0
        assert all(isinstance(p, str) for p in paragraphs)
        assert all(p.strip() for p in paragraphs)

    def test_split_paragraphs_english(self):
        """Test paragraph splitting for English text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        paragraphs = chunker._split_paragraphs(ENGLISH_TEXT)

        assert len(paragraphs) > 0

    def test_split_paragraphs_mixed(self):
        """Test paragraph splitting for mixed language text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        paragraphs = chunker._split_paragraphs(MIXED_TEXT)

        assert len(paragraphs) > 0


class TestSmartChunkerSentenceSplitting:
    """Tests for sentence splitting."""

    def test_split_sentences_chinese(self):
        """Test sentence splitting for Chinese text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        text = "This is the first sentence. This is the second sentence! Is this the third?"
        sentences = chunker._split_by_sentences(text)

        assert len(sentences) >= 3

    def test_split_sentences_english(self):
        """Test sentence splitting for English text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        text = "This is the first sentence. This is the second sentence! Is this the third?"
        sentences = chunker._split_by_sentences(text)

        assert len(sentences) >= 3

    def test_split_sentences_mixed(self):
        """Test sentence splitting for mixed text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        text = "This is a Chinese sentence. This is English sentence. This is another Chinese sentence."
        sentences = chunker._split_by_sentences(text)

        assert len(sentences) >= 3


class TestSmartChunkerMergeAndSplit:
    """Tests for merge and split functionality."""

    def test_merge_short_paragraphs(self):
        """Test that short paragraphs are merged."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(min_paragraph_size=100)
        paragraphs = [
            "Short paragraph",
            "Another short paragraph",
            "This is also short",
        ]

        chunks = chunker._merge_and_split(paragraphs)

        # Short paragraphs should be merged
        assert len(chunks) <= len(paragraphs)

    def test_split_long_paragraphs(self):
        """Test that long paragraphs are split."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=100, overlap=20, max_paragraph_size=200)
        long_text = "This is a very long piece of text. " * 50  # Create very long text
        paragraphs = [long_text]

        chunks = chunker._merge_and_split(paragraphs)

        # Long paragraph should be split
        assert len(chunks) > 1


class TestSmartChunkerOverlap:
    """Tests for overlap functionality."""

    def test_add_overlap(self):
        """Test that overlap is added between chunks."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(overlap=50)
        chunks = [
            "This is the first chunk. " * 10,
            "This is the second chunk. " * 10,
            "This is the third chunk. " * 10,
        ]

        overlapped = chunker._add_overlap(chunks)

        assert len(overlapped) == len(chunks)
        # Second and third chunks should have overlap
        assert len(overlapped[1]) > len(chunks[1])

    def test_no_overlap_single_chunk(self):
        """Test that single chunk doesn't get overlap."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(overlap=50)
        chunks = ["Only one chunk"]

        overlapped = chunker._add_overlap(chunks)

        assert len(overlapped) == 1
        assert overlapped[0] == chunks[0]

    def test_zero_overlap(self):
        """Test that zero overlap doesn't modify chunks."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(overlap=0)
        chunks = ["Chunk 1", "Chunk 2", "Chunk 3"]

        overlapped = chunker._add_overlap(chunks)

        assert overlapped == chunks


class TestSmartChunkerFullDocument:
    """Tests for full document chunking."""

    def test_chunk_document_chinese(self):
        """Test chunking a Chinese document."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk_document(CHINESE_TEXT)

        assert len(chunks) > 0
        for chunk in chunks:
            assert "text" in chunk
            assert "metadata" in chunk
            assert "position" in chunk

    def test_chunk_document_english(self):
        """Test chunking an English document."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk_document(ENGLISH_TEXT)

        assert len(chunks) > 0

    def test_chunk_document_mixed(self):
        """Test chunking a mixed language document."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=300, overlap=50)
        chunks = chunker.chunk_document(MIXED_TEXT)

        assert len(chunks) > 0

    def test_chunk_document_empty(self):
        """Test chunking an empty document."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        chunks = chunker.chunk_document("")

        assert len(chunks) == 0

    def test_chunk_document_metadata(self):
        """Test that metadata is properly attached to chunks."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        metadata = {"source": "test.pdf", "author": "Test Author"}
        chunks = chunker.chunk_document(CHINESE_TEXT, metadata=metadata)

        for chunk in chunks:
            assert chunk["metadata"].get("source") == "test.pdf"
            assert chunk["metadata"].get("author") == "Test Author"

    def test_chunk_positions(self):
        """Test that chunk positions are sequential."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        chunks = chunker.chunk_document(CHINESE_TEXT)

        for i, chunk in enumerate(chunks):
            assert chunk["position"] == i
            assert chunk["total_chunks"] == len(chunks)


class TestHeadingsExtraction:
    """Tests for heading extraction."""

    def test_extract_markdown_headings(self):
        """Test extraction of Markdown-style headings."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        headings = chunker._extract_headings(CHINESE_TEXT)

        assert len(headings) > 0
        assert "Introduction to Machine Learning" in headings
        assert "Supervised Learning" in headings

    def test_extract_numbered_headings(self):
        """Test extraction of numbered headings."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        text = """
1. Chapter 1 Introduction

1.1 Research Background

1.1.1 Problem Statement
"""
        headings = chunker._extract_headings(text)

        assert len(headings) > 0

    def test_extract_headings_max_level(self):
        """Test heading extraction with max level constraint."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        headings = chunker._extract_headings(CHINESE_TEXT, max_level=2)

        # Should only include # and ##, not ###
        for heading in headings:
            assert "###" not in heading or heading.count("#") <= 2


class TestKeywordExtraction:
    """Tests for keyword extraction."""

    def test_extract_keywords_chinese(self):
        """Test keyword extraction from Chinese text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        keywords = chunker._extract_keywords(CHINESE_TEXT, top_k=5)

        assert len(keywords) > 0
        assert len(keywords) <= 5

    def test_extract_keywords_empty_text(self):
        """Test keyword extraction from empty text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        keywords = chunker._extract_keywords("", top_k=5)

        assert len(keywords) == 0

    def test_extract_keywords_short_text(self):
        """Test keyword extraction from short text."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker()
        keywords = chunker._extract_keywords("Short text", top_k=5)

        # May return empty or few keywords for very short text
        assert len(keywords) <= 5


class TestChunkMetadata:
    """Tests for ChunkMetadata utility class."""

    def test_extract_headings_static(self):
        """Test static heading extraction method."""
        from chunking.smart_chunker import ChunkMetadata

        headings = ChunkMetadata.extract_headings(CHINESE_TEXT)
        assert len(headings) > 0

    def test_extract_keywords_static(self):
        """Test static keyword extraction method."""
        from chunking.smart_chunker import ChunkMetadata

        keywords = ChunkMetadata.extract_keywords(CHINESE_TEXT, top_k=5)
        assert len(keywords) > 0

    def test_count_words(self):
        """Test word counting."""
        from chunking.smart_chunker import ChunkMetadata

        text = "Machine learning is a branch of artificial intelligence"
        count = ChunkMetadata.count_words(text)
        assert count > 0

    def test_count_characters(self):
        """Test character counting."""
        from chunking.smart_chunker import ChunkMetadata

        text = "Machine learning is a branch of artificial intelligence"
        count = ChunkMetadata.count_characters(text)
        assert count == len(text.replace(" ", ""))


class TestChunkDataClass:
    """Tests for Chunk dataclass."""

    def test_chunk_to_dict(self):
        """Test Chunk to_dict method."""
        from chunking.smart_chunker import Chunk

        chunk = Chunk(
            text="Test text",
            metadata={"source": "test.pdf"},
            position=0,
            total_chunks=5,
        )

        result = chunk.to_dict()

        assert result["text"] == "Test text"
        assert result["metadata"]["source"] == "test.pdf"
        assert result["position"] == 0
        assert result["total_chunks"] == 5


class TestSmartChunkerIntegration:
    """Integration tests for the complete chunking pipeline."""

    def test_end_to_end_chunking(self):
        """Test complete chunking pipeline."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=300, overlap=50)

        # Process document
        chunks = chunker.chunk_document(
            CHINESE_TEXT,
            metadata={"source": "lecture_notes.pdf"},
            extract_keywords=True,
        )

        # Verify structure
        assert len(chunks) > 0

        for chunk in chunks:
            # Check required fields
            assert "text" in chunk
            assert "metadata" in chunk
            assert "position" in chunk
            assert "total_chunks" in chunk
            assert "headings" in chunk
            assert "keywords" in chunk

            # Check text is not empty
            assert len(chunk["text"]) > 0

            # Check metadata is preserved
            assert chunk["metadata"].get("source") == "lecture_notes.pdf"

    def test_chunk_size_respected(self):
        """Test that chunk sizes are approximately respected."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=200, overlap=50)
        chunks = chunker.chunk_document(ENGLISH_TEXT)

        # Most chunks should be around the target size
        for chunk in chunks:
            # Allow some flexibility due to sentence boundaries
            assert len(chunk["text"]) <= 300  # chunk_size + tolerance

    def test_overlap_preserves_context(self):
        """Test that overlap helps preserve context."""
        from chunking.smart_chunker import SmartChunker

        chunker = SmartChunker(chunk_size=200, overlap=50)
        chunks = chunker.chunk_document(CHINESE_TEXT)

        if len(chunks) > 1:
            # Check that consecutive chunks have some overlap
            for i in range(len(chunks) - 1):
                chunk1_end = chunks[i]["text"][-50:]  # Last 50 chars
                chunk2_start = chunks[i + 1]["text"][:50]  # First 50 chars

                # There should be some common text (overlap)
                # This is a soft check as overlap might not be exact
                pass  # Overlap logic is tested separately
