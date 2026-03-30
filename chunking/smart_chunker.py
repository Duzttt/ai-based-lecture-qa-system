"""
Smart Chunker implementation with semantic boundaries and overlap.

This module provides intelligent document chunking that:
- Respects paragraph and sentence boundaries
- Merges small paragraphs and splits large ones
- Adds overlap between chunks to preserve context
- Extracts and preserves metadata including headings
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import jieba
    import jieba.analyse
except ImportError:
    raise ImportError("Please install jieba: pip install jieba")


class SmartChunkerError(Exception):
    """Custom exception for SmartChunker errors."""

    pass


@dataclass
class Chunk:
    """Represents a text chunk with metadata."""

    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    position: int = 0  # Chunk position in document (0-indexed)
    total_chunks: int = 1
    start_char: int = 0  # Start character position in original text
    end_char: int = 0  # End character position in original text
    headings: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            "text": self.text,
            "metadata": self.metadata,
            "position": self.position,
            "total_chunks": self.total_chunks,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "headings": self.headings,
            "keywords": self.keywords,
        }


class SmartChunker:
    """
    Intelligent document chunker.

    Implements intelligent document chunking with:
    - Paragraph-aware splitting
    - Sentence boundary detection for Chinese and English
    - Adaptive chunk sizing (merge small, split large)
    - Overlap to preserve context across chunk boundaries
    - Metadata extraction (headings, keywords, positions)

    Attributes:
        chunk_size: Target chunk size in characters
        overlap: Overlap size in characters
        min_paragraph_size: Minimum paragraph size before merging
        max_paragraph_size: Maximum paragraph size before splitting
    """

    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 100,
        min_paragraph_size: int = 100,
        max_paragraph_size: int = 800,
    ):
        """
        Initialize the intelligent chunker.

        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap size in characters
            min_paragraph_size: Minimum paragraph size, paragraphs smaller than this will be merged with the next
            max_paragraph_size: Maximum paragraph size, paragraphs larger than this will be split by sentences
        """
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        if min_paragraph_size <= 0:
            raise ValueError("min_paragraph_size must be positive")
        if max_paragraph_size <= min_paragraph_size:
            raise ValueError(
                "max_paragraph_size must be greater than min_paragraph_size"
            )

        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_paragraph_size = min_paragraph_size
        self.max_paragraph_size = max_paragraph_size

        # Sentence ending patterns for Chinese and English
        self._chinese_sentence_endings = "。！？；!?；"
        self._english_sentence_endings = ".!?;:。！？；"
        self._sentence_pattern = re.compile(
            rf"(?<=[{re.escape(self._english_sentence_endings)}])\s*"
        )

    def chunk_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        extract_keywords: bool = True,
        top_k_keywords: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Split document into intelligent chunks.

        Args:
            text: Full document text
            metadata: Document metadata (title, source, etc.)
            extract_keywords: Whether to extract keywords
            top_k_keywords: Number of keywords to extract

        Returns:
            List[Dict] - Each chunk contains text, metadata, position, headings, keywords
        """
        if not text or not text.strip():
            return []

        text = text.strip()
        metadata = metadata or {}

        # 1. Split by paragraphs
        paragraphs = self._split_paragraphs(text)

        # 2. Merge small paragraphs, split large paragraphs
        chunks = self._merge_and_split(paragraphs)

        # 3. Add overlap
        chunks = self._add_overlap(chunks)

        # 4. Extract headings
        headings_map = self._extract_headings(text)

        # 5. Add metadata
        result = []
        for idx, chunk_text in enumerate(chunks):
            chunk_start = (
                text.find(chunk_text[:50])
                if len(chunk_text) >= 50
                else text.find(chunk_text)
            )
            if chunk_start == -1:
                chunk_start = idx * (self.chunk_size - self.overlap)

            chunk_end = chunk_start + len(chunk_text)

            # Find applicable headings based on position
            chunk_headings = []
            for heading, start_pos in headings_map.items():
                if start_pos <= chunk_end:
                    chunk_headings.append(heading)

            # Extract keywords for this chunk
            chunk_keywords = []
            if extract_keywords:
                chunk_keywords = self._extract_keywords(chunk_text, top_k_keywords)

            chunk_dict = {
                "text": chunk_text,
                "metadata": metadata.copy(),
                "position": idx,
                "total_chunks": len(chunks),
                "start_char": chunk_start,
                "end_char": chunk_end,
                "headings": chunk_headings[:3],  # Limit to 3 headings
                "keywords": chunk_keywords,
            }
            result.append(chunk_dict)

        return result

    def _split_paragraphs(self, text: str) -> List[str]:
        """
        Split by paragraphs (supports Chinese and English).

        Recognizes: \n\n, \r\n\r\n, \n and other paragraph separators

        Args:
            text: Input text

        Returns:
            List[str]: List of paragraphs
        """
        # Split on common paragraph separators
        # Handle both Windows (\r\n) and Unix (\n) line endings
        paragraphs = re.split(r"\n\s*\n|\r\n\s*\r\n", text)

        # Clean up paragraphs
        cleaned = []
        for para in paragraphs:
            para = para.strip()
            if para:
                # Replace single newlines with spaces within paragraph
                para = re.sub(r"\s+", " ", para)
                cleaned.append(para)

        return cleaned

    def _merge_and_split(self, paragraphs: List[str]) -> List[str]:
        """
        Intelligently merge/split paragraphs.

        Rules:
        - Short paragraphs (<min_paragraph_size characters) are merged with the next
        - Long paragraphs (>max_paragraph_size characters) are split by sentences
        - Try to split at sentence boundaries

        Args:
            paragraphs: List of paragraphs

        Returns:
            List[str]: List of processed chunks
        """
        if not paragraphs:
            return []

        chunks: List[str] = []
        current_chunk = ""

        for para in paragraphs:
            # If current chunk is empty, start with this paragraph
            if not current_chunk:
                current_chunk = para
                continue

            # If paragraph is short, merge with next
            if len(para) < self.min_paragraph_size:
                # Check if merging would exceed max size
                if len(current_chunk) + len(para) + 1 <= self.max_paragraph_size:
                    current_chunk += " " + para
                else:
                    # Current chunk is full, add it and start new one
                    chunks.extend(self._split_if_needed(current_chunk))
                    current_chunk = para
            else:
                # Paragraph is long enough to stand alone
                # First, save current chunk if it exists
                if current_chunk:
                    chunks.extend(self._split_if_needed(current_chunk))
                current_chunk = para

        # Don't forget the last chunk
        if current_chunk:
            chunks.extend(self._split_if_needed(current_chunk))

        return chunks

    def _split_if_needed(self, text: str) -> List[str]:
        """
        If text is too long, split by sentences.

        Args:
            text: Input text

        Returns:
            List[str]: List of split chunks
        """
        if len(text) <= self.chunk_size:
            return [text]

        # Split by sentences
        sentences = self._split_by_sentences(text)

        if len(sentences) <= 1:
            # Can't split further, just return as is
            return [text]

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed chunk size
            if len(current_chunk) + len(sentence) + 1 <= self.chunk_size:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                # Current chunk is full
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # Start new chunk with current sentence
                current_chunk = sentence

        # Add remaining chunk
        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """
        Add overlap content.

        Each chunk's beginning contains overlap content from the end of the previous chunk
        Avoid losing context at split points

        Args:
            chunks: List of chunks

        Returns:
            List[str]: List of chunks with overlap added
        """
        if len(chunks) <= 1 or self.overlap <= 0:
            return chunks

        result: List[str] = [chunks[0]]

        for i in range(1, len(chunks)):
            prev_chunk = result[-1]
            current_chunk = chunks[i]

            # Get overlap from end of previous chunk
            overlap_text = ""
            if len(prev_chunk) > self.overlap:
                # Try to find a good break point (sentence or word boundary)
                overlap_candidate = prev_chunk[-self.overlap :]

                # Find sentence boundary in overlap
                for ending in self._chinese_sentence_endings:
                    idx = overlap_candidate.find(ending)
                    if idx != -1 and idx > len(overlap_candidate) // 2:
                        overlap_text = overlap_candidate[idx + 1 :].strip()
                        break

                # If no good sentence boundary, use word boundary
                if not overlap_text:
                    # For Chinese, try to break at word boundary using jieba
                    words = list(jieba.cut(overlap_candidate))
                    overlap_text = overlap_candidate
                    for i, word in enumerate(reversed(words)):
                        if (
                            len(overlap_candidate)
                            - sum(len(w) for w in words[len(words) - i :])
                            >= self.overlap // 2
                        ):
                            overlap_text = "".join(words[len(words) - i :])
                            break

            if overlap_text:
                # Prepend overlap to current chunk
                if not current_chunk.startswith(overlap_text):
                    result.append(overlap_text + " " + current_chunk)
                else:
                    result.append(current_chunk)
            else:
                result.append(current_chunk)

        return result

    def _split_by_sentences(self, text: str) -> List[str]:
        """
        Split by sentences (Chinese and English).

        Chinese: 。！？etc.
        English: .!?etc.

        Args:
            text: Input text

        Returns:
            List[str]: List of sentences
        """
        # Use regex to split on sentence boundaries
        # This pattern handles both Chinese and English sentence endings
        sentences = self._sentence_pattern.split(text)

        # Filter out empty sentences
        return [s.strip() for s in sentences if s.strip()]

    def _extract_headings(self, text: str, max_level: int = 3) -> Dict[str, int]:
        """
        Extract headings from text.

        Recognizes Markdown-style headings (#, ##) or numbered headings (1., 1.1)

        Args:
            text: Input text
            max_level: Maximum heading level (1-3)

        Returns:
            Dict[heading_text, position]: Headings and their positions in the text
        """
        headings: Dict[str, int] = {}

        # Pattern for Markdown-style headings: #, ##, ###
        markdown_pattern = re.compile(
            r"^(#{1," + str(max_level) + r"})\s+(.+)$", re.MULTILINE
        )

        # Pattern for numbered headings: 1., 1.1, 1.1.1
        numbered_pattern = re.compile(
            r"^(\d+(?:\.\d+){0," + str(max_level - 1) + r"})[\s、.]\s*(.+)$",
            re.MULTILINE,
        )

        # Find Markdown headings
        for match in markdown_pattern.finditer(text):
            heading = match.group(2).strip()
            if heading and len(heading) < 200:  # Reasonable heading length
                headings[heading] = match.start()

        # Find numbered headings
        for match in numbered_pattern.finditer(text):
            number = match.group(1)
            title = match.group(2).strip()
            if title and len(title) < 200:
                headings[f"{number} {title}"] = match.start()

        return headings

    def _extract_keywords(self, text: str, top_k: int = 5) -> List[str]:
        """
        Extract keywords (for retrieval filtering).

        Uses jieba word segmentation + TF-IDF

        Args:
            text: Input text
            top_k: Number of keywords to extract

        Returns:
            List[str]: List of keywords
        """
        if not text or len(text) < 10:
            return []

        try:
            # Use jieba's TF-IDF keyword extraction
            keywords = jieba.analyse.extract_tags(text, topK=top_k)
            return keywords
        except Exception:
            # Fallback to simple word frequency
            words = jieba.lcut(text)
            word_freq: Dict[str, int] = {}
            for word in words:
                word = word.strip().lower()
                if len(word) > 1:  # Filter out single characters
                    word_freq[word] = word_freq.get(word, 0) + 1

            # Sort by frequency
            sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
            return [word for word, _ in sorted_words[:top_k]]


class ChunkMetadata:
    """
    Chunk metadata utility class.

    Provides static methods for extracting metadata from text chunks.
    """

    @staticmethod
    def extract_headings(text: str, max_level: int = 3) -> List[str]:
        """
        Extract headings from text.

        Recognizes Markdown-style headings (#, ##) or numbered headings (1., 1.1)

        Args:
            text: Input text
            max_level: Maximum heading level

        Returns:
            List[str]: List of headings
        """
        chunker = SmartChunker()
        headings_dict = chunker._extract_headings(text, max_level)
        return list(headings_dict.keys())

    @staticmethod
    def extract_keywords(text: str, top_k: int = 5) -> List[str]:
        """
        Extract keywords (for retrieval filtering).

        Uses jieba word segmentation + TF-IDF

        Args:
            text: Input text
            top_k: Number of keywords to extract

        Returns:
            List[str]: List of keywords
        """
        chunker = SmartChunker()
        return chunker._extract_keywords(text, top_k)

    @staticmethod
    def count_words(text: str) -> int:
        """
        Count words in text.

        Args:
            text: Input text

        Returns:
            int: Word count
        """
        words = jieba.lcut(text)
        return len([w for w in words if w.strip()])

    @staticmethod
    def count_characters(text: str) -> int:
        """
        Count characters in text (excluding spaces).

        Args:
            text: Input text

        Returns:
            int: Character count
        """
        return len(text.replace(" ", "").replace("\n", "").replace("\t", ""))
