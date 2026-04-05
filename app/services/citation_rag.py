"""
Citation-aware RAG pipeline with sentence-level citation support.

This module provides functionality to:
1. Generate answers with sentence-level citations in structured JSON format
2. Parse and validate LLM responses
3. Format responses with source metadata for frontend rendering
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.embedding import EmbeddingService
from app.services.llm_client import call_llm
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.runtime_llm import load_runtime_llm_settings, resolve_gemini_api_model
from app.services.vector_store import VectorStore


class CitationRAGError(Exception):
    """Custom exception for citation RAG errors."""

    pass


class CitationRAGPipeline:
    """
    RAG Pipeline that generates answers with sentence-level citations.

    The LLM is prompted to output structured JSON where each sentence
    includes an array of citation IDs referencing the source chunks.
    """

    def __init__(
        self,
        embedding_service: Optional[EmbeddingService] = None,
        vector_store: Optional[VectorStore] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
    ):
        runtime_settings = load_runtime_llm_settings()
        rt_embed = load_runtime_embedding_settings()
        self.embedding_service = embedding_service or EmbeddingService(
            model_name=rt_embed["model_id"]
        )
        self.vector_store = vector_store or VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt_embed["embedding_dim"],
        )
        self.model = model or runtime_settings["model"] or settings.LOCAL_LLM_MODEL
        self.base_url = (
            base_url or runtime_settings["base_url"] or settings.LOCAL_LLM_BASE_URL
        )
        self.timeout_seconds = timeout_seconds or settings.LOCAL_LLM_TIMEOUT_SECONDS

    def retrieve(
        self, query: str, top_k: int = 3, source_filter: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant chunks for the query.

        Args:
            query: The user's question
            top_k: Number of chunks to retrieve
            source_filter: Optional list of source filenames to filter by

        Returns:
            List of chunks with text, source, page, and chunk_id
        """
        if not query.strip():
            raise CitationRAGError("Query cannot be empty")

        query_embedding = self.embedding_service.embed_query(query)

        # Retrieve more candidates if filtering is needed
        search_k = top_k * 10 if source_filter else top_k
        results = self.vector_store.search_with_metadata(
            query_embedding, top_k=search_k
        )

        if source_filter:
            normalized_filters = [str(s).lower().strip() for s in source_filter]
            filtered = []
            for r in results:
                source = str(r.get("source", "")).lower().strip()
                for f in normalized_filters:
                    if source == f or source.startswith(f) or f in source:
                        filtered.append(r)
                        break
            results = filtered[:top_k]
        else:
            results = results[:top_k]

        # Add chunk_id for citation tracking
        for idx, chunk in enumerate(results, start=1):
            chunk["chunk_id"] = idx

        return results

    def _build_citation_prompt(self, query: str, chunks: List[Dict[str, Any]]) -> str:
        """
        Build the prompt that instructs the LLM to output structured JSON with citations.

        Args:
            query: The user's question
            chunks: Retrieved chunks with chunk_id, text, source, page

        Returns:
            Formatted prompt string
        """
        # Build context with chunk IDs
        context_lines = []
        for chunk in chunks:
            chunk_id = chunk.get("chunk_id", "?")
            source = chunk.get("source", "unknown")
            page = chunk.get("page", "unknown")
            text = chunk.get("text", "")
            context_lines.append(f"[{chunk_id}] Source: {source}, Page: {page}\n{text}")
        context_text = "\n\n".join(context_lines)

        # Prompt that enforces structured JSON output with sentence-level citations
        prompt = f"""You are a rigorous academic teaching assistant. Your task is to answer questions based ONLY on the provided reference materials.

IMPORTANT: You must output your answer as a valid JSON object with the following structure:
{{
  "sentences": [
    {{"text": "First sentence of your answer.", "citations": [1, 2]}},
    {{"text": "Second sentence with different sources.", "citations": [1]}},
    {{"text": "General knowledge sentence.", "citations": []}}
  ]
}}

Rules for citations:
1. Each sentence MUST have a "citations" array
2. If a sentence uses information from a chunk, include that chunk's ID number in the citations array
3. If a sentence is general knowledge or doesn't use the provided sources, use an empty array []
4. A sentence can cite multiple chunks if it combines information from multiple sources
5. Only cite chunks that actually support the statement
6. Do not make up information not found in the provided context
7. Unless the user asks for a one-line answer, write 2 to 4 complete sentences
8. For definition or explanation questions, define the term first and then explain why it matters in context

Reference Materials:
{context_text}

Question: {query}

Output ONLY the JSON object. No additional text, no markdown code blocks, no explanations."""

        return prompt

    def _generate_with_llm(self, prompt: str, model: Optional[str] = None) -> str:
        """
        Generate response using local LLM.

        Args:
            prompt: The formatted prompt
            model: Optional model override.

        Returns:
            Raw response text from the model
        """
        runtime_settings = load_runtime_llm_settings()
        return call_llm(
            provider="local_llm",
            model=model or self.model or settings.LOCAL_LLM_MODEL,
            call_type="citation",
            messages=[{"role": "user", "content": prompt}],
            query_text=prompt,
            base_url=self.base_url or runtime_settings["base_url"],
            temperature=0.3,
            num_predict=settings.CITATION_MAX_OUTPUT_TOKENS,
        )

    def _generate_with_openrouter(self, prompt: str) -> str:
        """
        Generate response using OpenRouter API.

        Args:
            prompt: The formatted prompt

        Returns:
            Raw response text from the model
        """
        runtime_settings = load_runtime_llm_settings()
        api_key = runtime_settings["api_key"] or settings.OPENROUTER_API_KEY
        if not api_key:
            raise CitationRAGError("OPENROUTER_API_KEY is not configured")
        return call_llm(
            provider="openrouter",
            model=self.model or runtime_settings["model"] or settings.OPENROUTER_MODEL,
            call_type="citation",
            messages=[{"role": "user", "content": prompt}],
            query_text=prompt,
            api_key=api_key,
            base_url=runtime_settings["base_url"] or settings.OPENROUTER_BASE_URL,
            temperature=0.3,
            max_tokens=settings.CITATION_MAX_OUTPUT_TOKENS,
        )

    def _generate_with_gemini(self, prompt: str) -> str:
        """
        Generate response using Gemini API.

        Args:
            prompt: The formatted prompt

        Returns:
            Raw response text from the model
        """
        runtime_settings = load_runtime_llm_settings()
        api_key = runtime_settings["api_key"] or settings.GEMINI_API_KEY
        if not api_key:
            raise CitationRAGError("GEMINI_API_KEY is not configured")
        return call_llm(
            provider="gemini",
            model=resolve_gemini_api_model(self.model, runtime_settings["model"]),
            call_type="citation",
            messages=[{"role": "user", "content": prompt}],
            query_text=prompt,
            api_key=api_key,
            base_url=runtime_settings["base_url"] or settings.GEMINI_BASE_URL,
            temperature=0.3,
            max_tokens=settings.CITATION_MAX_OUTPUT_TOKENS,
            response_format="json",
        )

    def _generate(self, prompt: str) -> str:
        """Dispatch to the configured LLM provider."""
        provider = load_runtime_llm_settings()["provider"] or settings.LLM_PROVIDER

        if provider == "gemini":
            return self._generate_with_gemini(prompt)
        elif provider == "openrouter":
            return self._generate_with_openrouter(prompt)
        elif provider == "local_llm":
            return self._generate_with_llm(prompt)
        else:
            raise CitationRAGError(f"Unsupported LLM_PROVIDER: {provider}")

    def _parse_llm_response(self, raw_response: str) -> Dict[str, Any]:
        """
        Parse the LLM's JSON response and validate structure.

        Args:
            raw_response: Raw text response from LLM

        Returns:
            Parsed and validated JSON structure
        """
        # Try to extract JSON from the response (handle markdown code blocks)
        json_match = re.search(r"\{[\s\S]*\}", raw_response)
        if json_match:
            raw_response = json_match.group()

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise CitationRAGError(f"Failed to parse LLM response as JSON: {e}")

        # Validate structure
        if not isinstance(parsed, dict):
            raise CitationRAGError("Response must be a JSON object")

        if "sentences" not in parsed:
            raise CitationRAGError("Response must contain 'sentences' array")

        sentences = parsed["sentences"]
        if not isinstance(sentences, list):
            raise CitationRAGError("'sentences' must be an array")

        # Validate each sentence
        for i, sentence in enumerate(sentences):
            if not isinstance(sentence, dict):
                raise CitationRAGError(f"Sentence {i} must be an object")
            if "text" not in sentence:
                raise CitationRAGError(f"Sentence {i} must have 'text' field")
            if "citations" not in sentence:
                raise CitationRAGError(f"Sentence {i} must have 'citations' field")
            if not isinstance(sentence["citations"], list):
                raise CitationRAGError(f"Sentence {i} citations must be an array")

        return parsed

    def _recover_sentences_from_malformed_response(
        self, raw_response: str
    ) -> Optional[Dict[str, Any]]:
        """
        Recover sentence text from JSON-like model output that is malformed.

        Models sometimes follow the requested schema but forget to escape quotes
        inside the "text" value. In those cases we still want to surface the
        answer text instead of replacing it with a generic error message.
        """
        response_text = str(raw_response or "").strip()
        if not response_text:
            return None

        recovered_sentences: List[Dict[str, Any]] = []
        text_matches = re.finditer(
            r'"text"\s*:\s*"(?P<text>[\s\S]*?)"\s*,\s*"citations"\s*:\s*\[(?P<citations>[^\]]*)\]',
            response_text,
        )
        for match in text_matches:
            text_value = match.group("text").strip()
            if not text_value:
                continue

            citations_raw = match.group("citations").strip()
            citation_ids = [int(item) for item in re.findall(r"\d+", citations_raw)]
            recovered_sentences.append(
                {
                    "text": text_value,
                    "citations": citation_ids,
                }
            )

        if recovered_sentences:
            return {"sentences": recovered_sentences}

        answer_match = re.search(
            r'"(?:answer|response|text)"\s*:\s*"(?P<text>[\s\S]*?)"\s*(?:[,}])',
            response_text,
        )
        if answer_match:
            text_value = answer_match.group("text").strip()
            if text_value:
                return {"sentences": [{"text": text_value, "citations": []}]}

        return None

    def _build_response_with_sources(
        self,
        sentences_data: Dict[str, Any],
        chunks: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Build the final response format with source metadata.

        Args:
            sentences_data: Parsed sentences with citation IDs
            chunks: Retrieved chunks with source information

        Returns:
            Formatted response with sentences and sources map
        """
        # Build sources map from chunks
        sources = {}
        for chunk in chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            if chunk_id:
                sources[chunk_id] = {
                    "file": chunk.get("source", "unknown"),
                    "page": chunk.get("page"),
                    "text": chunk.get("text", ""),
                }

        return {
            "sentences": sentences_data.get("sentences", []),
            "sources": sources,
        }

    def _generate_plain_answer_fallback(
        self, question: str, chunks: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Fall back to the standard RAG answer path when citation JSON generation
        fails. This prefers returning a usable answer over surfacing a parser
        error to the user.
        """
        if not chunks:
            return None

        try:
            from app.services.local_rag import build_context_from_sources, generate

            context = build_context_from_sources(chunks)
            plain_answer = str(
                generate(
                    query=question,
                    context=context,
                    model=self.model,
                    temperature=0.3,
                )
                or ""
            ).strip()
        except Exception:
            return None

        if not plain_answer:
            return None

        return {
            "sentences": [{"text": plain_answer, "citations": []}],
        }

    def query(
        self,
        question: str,
        top_k: int = 3,
        source_filter: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Execute a complete RAG query with citation support.

        Args:
            question: The user's question
            top_k: Number of chunks to retrieve
            source_filter: Optional list of source filenames to filter by

        Returns:
            Response with sentences and sources in the format:
            {
                "sentences": [
                    {"text": "...", "citations": [1, 2]},
                    ...
                ],
                "sources": {
                    "1": {"file": "...", "page": 24},
                    "2": {"file": "...", "page": 3}
                }
            }
        """
        # Retrieve relevant chunks
        chunks = self.retrieve(question, top_k=top_k, source_filter=source_filter)

        if not chunks:
            return {
                "sentences": [
                    {
                        "text": "No relevant information found in the uploaded documents.",
                        "citations": [],
                    }
                ],
                "sources": {},
            }

        # Build prompt with citation instructions
        prompt = self._build_citation_prompt(question, chunks)

        # Generate response from LLM
        raw_response = self._generate(prompt)

        # Parse and validate JSON response. Some providers occasionally return
        # plain text even when asked for JSON; degrade gracefully instead of
        # failing the whole request with 503.
        try:
            parsed_response = self._parse_llm_response(raw_response)
        except CitationRAGError:
            recovered_response = self._recover_sentences_from_malformed_response(
                raw_response
            )
            if recovered_response:
                parsed_response = recovered_response
            else:
                plain_answer_response = self._generate_plain_answer_fallback(
                    question, chunks
                )
                if plain_answer_response:
                    parsed_response = plain_answer_response
                else:
                    fallback_text = str(raw_response or "").strip()
                    if not fallback_text:
                        raise
                    if fallback_text.startswith("{") and (
                        "sentences" in fallback_text or "text" in fallback_text
                    ):
                        fallback_text = (
                            "The model returned a malformed response. "
                            "Please try rephrasing your question or try again later."
                        )
                    parsed_response = {
                        "sentences": [{"text": fallback_text, "citations": []}],
                    }

        # Build final response with source metadata
        return self._build_response_with_sources(parsed_response, chunks)


# Convenience function for simple usage
def query_with_citations(
    question: str,
    top_k: int = 3,
    source_filter: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Simple function to query with citation support.

    Args:
        question: The user's question
        top_k: Number of chunks to retrieve
        source_filter: Optional list of source filenames to filter by
        model: Optional model override

    Returns:
        Response with sentences and sources
    """
    pipeline = CitationRAGPipeline(model=model)
    return pipeline.query(question, top_k=top_k, source_filter=source_filter)
