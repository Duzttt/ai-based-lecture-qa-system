from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.embedding import EmbeddingService
from app.services.llm_client import call_llm
from app.services.vector_store import VectorStore


class LLMError(Exception):
    pass


class RAGPipeline:
    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        provider: str = "gemini",
    ):
        self.embedding_service = embedding_service
        self.vector_store = vector_store
        self.provider = provider

        if provider == "gemini":
            self.api_key = api_key or settings.GEMINI_API_KEY
            self.model = model or settings.GEMINI_MODEL
            self.base_url = settings.GEMINI_BASE_URL
        else:
            self.api_key = api_key or settings.OPENROUTER_API_KEY
            self.model = model or "anthropic/claude-3-haiku"
            self.base_url = settings.OPENROUTER_BASE_URL

    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        query_embedding = self.embedding_service.embed_query(query)
        return self.vector_store.search_with_metadata(query_embedding, top_k=top_k)

    def generate_answer(self, query: str, context: List[Dict[str, Any]]) -> str:
        if not context:
            return "No relevant information found in the uploaded documents."

        if not self.api_key:
            raise LLMError(f"{self.provider.upper()} API key not configured")

        context_lines = []
        for item in context:
            source = item.get("source", "unknown")
            page = item.get("page")
            page_label = str(page) if page is not None else "unknown"
            text = item.get("text", "")
            rank = item.get("rank", "?")
            context_lines.append(f"[S{rank}] file={source}, page={page_label}\n{text}")
        context_text = "\n\n".join(context_lines)

        prompt = f"""You are a helpful teaching assistant.
Answer only using the provided sources.
If the sources do not contain enough evidence, say so explicitly.
When making claims, cite source tags like [S1], [S2].
When possible, mention both file name and page number in your citations.

Context:
{context_text}

Question: {query}

Answer:"""

        if self.provider == "gemini":
            return self._generate_gemini(prompt)
        else:
            return self._generate_openrouter(prompt)

    def _generate_gemini(self, prompt: str) -> str:
        return call_llm(
            provider="gemini",
            model=self.model,
            call_type="qa",
            messages=[{"role": "user", "content": prompt}],
            query_text=prompt,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.7,
            max_tokens=500,
        )

    def _generate_openrouter(self, prompt: str) -> str:
        return call_llm(
            provider="openrouter",
            model=self.model,
            call_type="qa",
            messages=[{"role": "user", "content": prompt}],
            query_text=prompt,
            api_key=self.api_key,
            base_url=self.base_url,
            temperature=0.7,
            max_tokens=500,
        )

    def query(self, question: str, top_k: int = 5) -> Dict:
        sources = self.retrieve(question, top_k=top_k)
        answer = self.generate_answer(question, sources)
        return {
            "answer": answer,
            "sources": sources,
        }
