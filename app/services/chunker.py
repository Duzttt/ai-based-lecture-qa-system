from typing import List

try:
    from llama_index.core.node_parser import SentenceSplitter
except ImportError:
    SentenceSplitter = None

# 保留现有的LangChain导入作为后备
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    RecursiveCharacterTextSplitter = None


class TextChunker:
    def __init__(self, chunk_size: int = 400, chunk_overlap: int = 50):
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

        # 优先使用LlamaIndex分割器
        if SentenceSplitter is not None:
            self._use_llama = True
            self._splitter = SentenceSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        elif RecursiveCharacterTextSplitter is not None:
            self._use_llama = False
            self._character_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            self._sentence_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=[". ", "! ", "? ", "\n", " ", ""],
            )
        else:
            self._use_llama = False
            self._character_splitter = None
            self._sentence_splitter = None

    @staticmethod
    def _clean_chunks(chunks: List[str]) -> List[str]:
        return [chunk.strip() for chunk in chunks if chunk and chunk.strip()]

    def _chunk_text_fallback(self, text: str) -> List[str]:
        chunks: List[str] = []
        step = self.chunk_size - self.chunk_overlap
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunks.append(text[start:end])
            start += step

        return self._clean_chunks(chunks)

    def _chunk_text_by_sentences_fallback(self, text: str) -> List[str]:
        import re

        sentence_endings = re.compile(r"(?<=[.!?])\s+")
        sentences = sentence_endings.split(text)

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            candidate = f"{current_chunk} {sentence}".strip()
            if (
                current_chunk
                and len(candidate) > self.chunk_size
            ):
                chunks.append(current_chunk.strip())
                overlap = current_chunk[-self.chunk_overlap:]
                current_chunk = f"{overlap} {sentence}".strip()
            else:
                current_chunk = candidate

        if current_chunk:
            chunks.append(current_chunk.strip())

        return self._clean_chunks(chunks)

    def chunk_text(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        cleaned_text = text.strip()

        # 优先使用LlamaIndex分割器
        if self._use_llama:
            return self._clean_chunks(
                self._splitter.split_text(cleaned_text)
            )

        # 回退到LangChain分割器
        if self._character_splitter is not None:
            return self._clean_chunks(
                self._character_splitter.split_text(cleaned_text)
            )

        # 最终回退到自定义实现
        return self._chunk_text_fallback(cleaned_text)

    def chunk_text_by_sentences(self, text: str) -> List[str]:
        if not text or not text.strip():
            return []

        cleaned_text = text.strip()

        # 优先使用LlamaIndex分割器（它本身就按句子分割）
        if self._use_llama:
            return self._clean_chunks(
                self._splitter.split_text(cleaned_text)
            )

        # 回退到LangChain分割器
        if self._sentence_splitter is not None:
            return self._clean_chunks(
                self._sentence_splitter.split_text(cleaned_text)
            )

        # 最终回退到自定义实现
        return self._chunk_text_by_sentences_fallback(cleaned_text)
