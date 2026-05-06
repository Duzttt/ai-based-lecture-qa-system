import logging
import threading
from typing import Any, Dict, List

from app.services.llama_llm_config import configure_llm

__all__ = ["LlamaRAGPipeline", "LlamaRAGError"]

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are an academic teaching assistant for lecture notes Q&A.\n"
    "Base your answer strictly on the provided context. "
    "Cite sources using [S1], [S2] etc. "
    "If the context does not contain enough information, say so explicitly."
)

_llm_config_lock = threading.Lock()


class LlamaRAGError(Exception):
    pass


class LlamaRAGPipeline:
    """LlamaIndex RAG管道.

    Each instance configures the global LlamaIndex Settings.llm on construction.
    Create only one instance per provider to avoid global state conflicts.
    For concurrent multi-provider usage, use separate processes.
    """

    def __init__(self, index, provider: str = "gemini", **kwargs):
        self.index = index
        self.provider = provider

        try:
            with _llm_config_lock:
                configure_llm(provider, **kwargs)
        except Exception as exc:
            raise LlamaRAGError(f"Failed to configure LLM: {exc}") from exc

        self.query_engine = index.as_query_engine()

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        try:
            retriever = self.index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
        except Exception as exc:
            raise LlamaRAGError(f"Retrieval failed: {exc}") from exc

        results = []
        for rank, node in enumerate(nodes, start=1):
            score = node.score if node.score is not None else 0.0
            results.append(
                {
                    "index": rank,
                    "rank": rank,
                    "text": node.node.text,
                    "source": node.node.metadata.get("source", "unknown"),
                    "page": node.node.metadata.get("page"),
                    "distance": 1 - score,
                }
            )

        return results

    def generate_answer(self, query: str, context: List[Dict[str, Any]]) -> str:
        if not context:
            return "No relevant context was retrieved, so I cannot answer based on evidence."

        context_str = self._build_context(context)
        prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            f"## Context\n{context_str}\n\n"
            f"## Question\n{query}"
        )

        try:
            response = self.query_engine.query(prompt)
            return response.response
        except Exception as exc:
            raise LlamaRAGError(f"Answer generation failed: {exc}") from exc

    @staticmethod
    def _build_context(sources: List[Dict[str, Any]]) -> str:
        lines: List[str] = []
        for idx, item in enumerate(sources, start=1):
            source = item.get("source", "unknown")
            page = item.get("page")
            page_label = str(page) if page is not None else "unknown"
            text = item.get("text", "")
            lines.append(f"[S{idx}] (source: {source}, page: {page_label})\n{text}")
        return "\n\n".join(lines)

    def query(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        sources = self.retrieve(question, top_k=top_k)
        answer = self.generate_answer(question, sources)

        return {
            "answer": answer,
            "sources": sources,
        }
