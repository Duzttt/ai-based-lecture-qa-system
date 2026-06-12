from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.embedding import EmbeddingService
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
            self.model = model or settings.OPENROUTER_MODEL
            self.base_url = settings.OPENROUTER_BASE_URL

    def retrieve(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
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
        headers = {"Content-Type": "application/json"}

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": 500,
                "temperature": 0.7,
            },
        }

        try:
            url = f"{self.base_url}/models/{self.model}:generateContent"
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    url,
                    headers=headers,
                    json=payload,
                    params={"key": self.api_key},
                )
                response.raise_for_status()
                data = response.json()

            if "candidates" in data and len(data["candidates"]) > 0:
                candidate = data["candidates"][0]
                if "content" in candidate and "parts" in candidate["content"]:
                    return candidate["content"]["parts"][0]["text"]

            raise LLMError("Invalid response format from Gemini API")

        except httpx.HTTPStatusError as e:
            raise LLMError(f"Failed to generate answer: {e}") from e
        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response from Gemini API: {e}") from e

    def _generate_openrouter(self, prompt: str) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 500,
        }

        try:
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
            return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Failed to generate answer: {e}") from e
        except (KeyError, IndexError) as e:
            raise LLMError(f"Invalid response from LLM API: {e}") from e

    def query(self, question: str, top_k: int = 3) -> Dict[str, Any]:
        sources = self.retrieve(question, top_k=top_k)
        answer = self.generate_answer(question, sources)
        return {"answer": answer, "sources": sources}
