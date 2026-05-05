"""
Document Summarizer Service

Provides intelligent summarization for single or multiple documents
using LLM-based generation.
"""

import json
import re
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.llm_client import call_llm


class SummarizerError(Exception):
    """Exception raised for summarization errors."""

    pass


class DocumentSummarizer:
    """
    Document summarization service using LLM.

    Supports:
    - Single document summarization
    - Multi-document synthesis
    - Configurable length, style, and language
    - Citation extraction
    """

    # Length configurations
    LENGTH_LIMITS = {
        "short": {"sentences": "3-5", "tokens": 150},
        "medium": {"sentences": "8-12", "tokens": 300},
        "detailed": {"sentences": "15-20", "tokens": 600},
    }

    # Style prompts
    STYLE_PROMPTS = {
        "bullets": "List core content as bullet points. Each point should be concise and clear.",
        "narrative": "Summarize in a coherent narrative style with logical flow and smooth transitions between paragraphs.",
        "academic": "Write in academic language covering main arguments, methodology, and conclusions with scholarly rigor.",
        "executive": "Use an executive summary style highlighting key findings and actionable recommendations.",
    }

    # Language options
    LANGUAGE_OPTIONS = {
        "zh": "Chinese",
        "en": "English",
        "ja": "Japanese",
    }

    def __init__(self, llm_provider: str = None, model: str = None):
        """
        Initialize the summarizer.

        Args:
            llm_provider: LLM provider (gemini, openrouter, local_llm)
            model: Model name to use
        """
        from app.services.runtime_llm import load_runtime_llm_settings

        rt = load_runtime_llm_settings()
        self.llm_provider = llm_provider or rt["provider"] or settings.LLM_PROVIDER
        self.model = model or rt["model"] or settings.LOCAL_LLM_MODEL
        self.base_url = rt["base_url"] or settings.LOCAL_LLM_BASE_URL
        self.timeout = settings.LOCAL_LLM_TIMEOUT_SECONDS

    def _build_prompt(
        self,
        documents: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> str:
        """
        Build the prompt for summary generation.

        Args:
            documents: List of document dicts with name and text
            config: Summary configuration

        Returns:
            Formatted prompt string
        """
        length_config = config.get("length", "medium")
        style = config.get("style", "narrative")
        language = config.get("language", "en")
        include_citations = config.get("include_citations", True)

        length_info = self.LENGTH_LIMITS.get(
            length_config, self.LENGTH_LIMITS["medium"]
        )
        style_prompt = self.STYLE_PROMPTS.get(style, self.STYLE_PROMPTS["narrative"])
        language_name = self.LANGUAGE_OPTIONS.get(language, "Chinese")

        if len(documents) == 1:
            # Single document summary
            doc = documents[0]
            # Truncate text if too long (keep first 5000 chars)
            text = doc["text"][:5000] if len(doc["text"]) > 5000 else doc["text"]

            prompt = f"""Generate a summary for the following document.

**Document**: {doc["name"]}

**Content**:
{text}

**Requirements**:
- Length: approximately {length_info["tokens"]} words, {length_info["sentences"]} sentences
- Style: {style_prompt}
- Language: {language_name}
- Preserve domain-specific terminology and key concepts from the original
- Highlight the core arguments and important conclusions
{"- After the summary, list key quoted passages with page numbers" if include_citations else ""}

Output the summary directly:"""

        else:
            # Multi-document synthesis
            doc_list = "\n\n".join(
                [
                    f"**Document {i+1}**: {doc['name']}\n{doc['text'][:1000]}..."
                    for i, doc in enumerate(documents)
                ]
            )

            prompt = f"""Generate a synthesized summary across the following {len(documents)} related documents.

{doc_list}

**Requirements**:
- Synthesize core arguments from all documents into a coherent overview
- Identify agreements, differences, and complementary points across documents
- Style: {style_prompt}
- Language: {language_name}
- Length: medium (approximately 400-500 words)
- If documents conflict, clearly note the discrepancies
{"- After the summary, list key citations from each document" if include_citations else ""}

Output the synthesized summary directly:"""

        return prompt

    def _call_llm(self, prompt: str, response_format: str = None) -> str:
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt, response_format)
        elif self.llm_provider == "gemini":
            return self._call_gemini(prompt, response_format)
        elif self.llm_provider == "openrouter":
            return self._call_openrouter(prompt, response_format)
        raise SummarizerError(f"Unknown LLM provider: {self.llm_provider}")

    def _extractive_summary(self, text: str, length: str) -> str:
        clean_text = re.sub(r"\s+", " ", text).strip()
        if not clean_text:
            return ""

        sentence_candidates = re.split(r"(?<=[.!?。！？])\s+", clean_text)
        sentences = [s.strip() for s in sentence_candidates if s.strip()]
        if not sentences:
            return clean_text[:300]

        sentence_limit_map = {"short": 3, "medium": 6, "detailed": 10}
        sentence_limit = sentence_limit_map.get(length, 6)
        selected = sentences[:sentence_limit]
        return " ".join(selected)

    def _build_messages(
        self, prompt: str, response_format: str = None
    ) -> List[Dict[str, str]]:
        system_prompt = (
            "You are a professional document summarization assistant. "
            "Generate clear, accurate summaries."
        )
        if response_format == "json":
            system_prompt += " Output ONLY valid JSON."
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]

    def _call_local_llm(self, prompt: str, response_format: str = None) -> str:
        """Call local LLM via Ollama."""
        try:
            messages = self._build_messages(prompt, response_format)
            return call_llm(
                provider="local_llm",
                model=self.model,
                call_type="summary",
                messages=messages,
                base_url=self.base_url,
                timeout=self.timeout,
                keep_alive=settings.LOCAL_LLM_KEEP_ALIVE,
            )
        except Exception as e:
            raise SummarizerError(f"Failed to call local LLM: {str(e)}")

    def _call_gemini(self, prompt: str, response_format: str = None) -> str:
        """Call Google Gemini API."""
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise SummarizerError("Gemini API key not configured")
            messages = self._build_messages(prompt, response_format)
            return call_llm(
                provider="gemini",
                model=settings.GEMINI_MODEL,
                call_type="summary",
                messages=messages,
                api_key=api_key,
                base_url=settings.GEMINI_BASE_URL,
                temperature=0.3,
                max_tokens=2048,
                response_format=response_format,
            )
        except SummarizerError:
            raise
        except Exception as e:
            raise SummarizerError(f"Failed to call Gemini: {str(e)}")

    def _call_openrouter(self, prompt: str, response_format: str = None) -> str:
        """Call OpenRouter API."""
        try:
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                raise SummarizerError("OpenRouter API key not configured")
            messages = self._build_messages(prompt, response_format)
            return call_llm(
                provider="openrouter",
                model=settings.OPENROUTER_MODEL,
                call_type="summary",
                messages=messages,
                api_key=api_key,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=0.3,
                max_tokens=2048,
            )
        except SummarizerError:
            raise
        except Exception as e:
            raise SummarizerError(f"Failed to call OpenRouter: {str(e)}")

    def _extract_citations(
        self,
        document: Dict[str, Any],
        summary: str,
    ) -> List[Dict[str, Any]]:
        summary_sentences = [
            s.strip()
            for s in re.split(r"(?<=[.!?。！？])\s+", summary.strip())
            if s.strip()
        ]
        chunks = document.get("chunks", [])
        citations: List[Dict[str, Any]] = []
        for sentence in summary_sentences[:3]:
            best_page = None
            if chunks:
                best_score = 0
                sentence_lower = sentence.lower()
                sentence_words = set(sentence_lower.split())
                for chunk in chunks:
                    chunk_text = str(chunk.get("text", "")).lower()
                    chunk_words = set(chunk_text.split())
                    overlap = len(sentence_words & chunk_words)
                    if overlap > best_score:
                        best_score = overlap
                        best_page = chunk.get("page")
            citations.append(
                {
                    "point": sentence[:120],
                    "citation": sentence[:220],
                    "source": document.get("name", "unknown"),
                    "page": best_page,
                }
            )
        return citations

    def generate_single_doc_summary(
        self,
        document: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate summary for a single document.

        Args:
            document: Document dict with name, text, and metadata
            config: Summary configuration

        Returns:
            Summary result dict with text, citations, document info
        """
        import logging

        logger = logging.getLogger(__name__)

        summary_text = None
        try:
            prompt = self._build_prompt([document], config)
            summary_text = self._call_llm(prompt)
        except (SummarizerError, Exception) as e:
            logger.warning(
                "LLM summarization failed, falling back to extractive: %s", e
            )

        if not summary_text:
            summary_text = self._extractive_summary(
                str(document.get("text", "")),
                str(config.get("length", "medium")),
            )

        if not summary_text:
            raise SummarizerError("Document content is empty")

        citations = []
        if config.get("include_citations", True):
            citations = self._extract_citations(document, summary_text)

        return {
            "text": summary_text,
            "citations": citations,
            "document": document["name"],
            "document_count": 1,
            "config": config,
        }

    def generate_multi_doc_summary(
        self,
        documents: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate combined summary for multiple documents.

        Args:
            documents: List of document dicts
            config: Summary configuration

        Returns:
            Summary result dict with text, comparison, document count
        """
        import logging

        logger = logging.getLogger(__name__)

        summary_text = None
        try:
            prompt = self._build_prompt(documents, config)
            summary_text = self._call_llm(prompt)
        except (SummarizerError, Exception) as e:
            logger.warning(
                "LLM summarization failed, falling back to extractive: %s", e
            )

        if not summary_text:
            doc_summaries: List[str] = []
            for doc in documents:
                summary_piece = self._extractive_summary(
                    str(doc.get("text", "")),
                    "short",
                )
                if summary_piece:
                    doc_summaries.append(
                        f"[{doc.get('name', 'unknown')}] {summary_piece}"
                    )

            if not doc_summaries:
                raise SummarizerError("Document content is empty")
            summary_text = "\n\n".join(doc_summaries)

        # Generate comparison table if requested
        comparison = []
        if config.get("include_comparison", False):
            comparison = self._generate_comparison_table(documents)

        return {
            "text": summary_text,
            "comparison": comparison,
            "document_count": len(documents),
            "documents": [doc["name"] for doc in documents],
            "config": config,
        }

    def _generate_comparison_table(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Generate a comparison table for multiple documents.

        Args:
            documents: List of document dicts

        Returns:
            List of comparison dicts per document
        """
        comparison: List[Dict[str, Any]] = []
        for doc in documents:
            text = str(doc.get("text", ""))
            summary = self._extractive_summary(text, "short")
            tokens = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", text)]
            keyword_counts: Dict[str, int] = {}
            for token in tokens:
                keyword_counts[token] = keyword_counts.get(token, 0) + 1
            top_keywords = sorted(
                keyword_counts.keys(),
                key=lambda k: keyword_counts[k],
                reverse=True,
            )[:3]
            comparison.append(
                {
                    "name": doc.get("name", "unknown"),
                    "mainPoints": summary or "No sufficient content",
                    "keywords": top_keywords,
                    "methodology": "",
                    "conclusions": summary or "",
                }
            )
        return comparison

    def generate_summary(
        self,
        documents: List[Dict[str, Any]],
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate summary for one or more documents.

        Args:
            documents: List of document dicts
            config: Summary configuration

        Returns:
            Summary result dict
        """
        if not documents:
            raise SummarizerError("No documents provided")

        if len(documents) == 1:
            return self.generate_single_doc_summary(documents[0], config)
        else:
            return self.generate_multi_doc_summary(documents, config)


# Convenience function
def summarize_documents(
    documents: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convenience function to summarize documents.

    Args:
        documents: List of document dicts with name and text
        config: Optional configuration dict

    Returns:
        Summary result dict
    """
    default_config = {
        "length": "medium",
        "style": "narrative",
        "language": "en",
        "include_citations": True,
        "include_comparison": True,
    }

    if config:
        default_config.update(config)

    summarizer = DocumentSummarizer()
    return summarizer.generate_summary(documents, default_config)
