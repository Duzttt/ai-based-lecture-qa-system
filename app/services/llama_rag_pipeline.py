from typing import Any, Dict, List

from app.services.llama_llm_config import configure_llm

__all__ = ["LlamaRAGPipeline", "LlamaRAGError"]


class LlamaRAGError(Exception):
    pass


class LlamaRAGPipeline:
    """LlamaIndex RAG管道"""

    def __init__(self, index, provider: str = "gemini", **kwargs):
        self.index = index
        self.provider = provider

        configure_llm(provider, **kwargs)

        self.query_engine = index.as_query_engine()

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = retriever.retrieve(query)

        results = []
        for rank, node in enumerate(nodes, start=1):
            results.append(
                {
                    "index": rank,
                    "rank": rank,
                    "text": node.node.text,
                    "source": node.node.metadata.get("source", "unknown"),
                    "page": node.node.metadata.get("page"),
                    "distance": 1 - node.score if node.score else 0.0,
                }
            )

        return results

    def generate_answer(self, query: str, context: List[Dict[str, Any]]) -> str:
        response = self.query_engine.query(query)
        return response.response

    def query(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        sources = self.retrieve(question, top_k=top_k)
        answer = self.generate_answer(question, sources)

        return {
            "answer": answer,
            "sources": sources,
        }
