"""
Document Summarizer Service

Provides intelligent summarization for single or multiple documents
using LLM-based generation.
"""

import json
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
        self.llm_provider = llm_provider or "local_llm"
        self.model = model or settings.LOCAL_LLM_MODEL
        self.base_url = settings.LOCAL_LLM_BASE_URL
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
        """
        Call the LLM to generate response.

        Args:
            prompt: Input prompt
            response_format: Expected format (e.g., 'json')

        Returns:
            LLM response text
        """
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt, response_format)
        elif self.llm_provider == "gemini":
            return self._call_gemini(prompt, response_format)
        elif self.llm_provider == "openrouter":
            return self._call_openrouter(prompt, response_format)
        else:
            raise SummarizerError(f"Unsupported LLM provider: {self.llm_provider}")

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
        """
        Extract key citations from document that support the summary.

        Args:
            document: Document dict with text and metadata
            summary: Generated summary text

        Returns:
            List of citation dicts with point, citation, source, page
        """
        text = document["text"][:3000]  # Limit for citation extraction

        prompt = f"""Given the original text and its summary, find the source passages that support each key point in the summary.

**Original Text**:
{text}

**Summary**:
{summary}

Return a JSON array where each element contains:
- point: A key point from the summary (brief)
- citation: The corresponding passage from the original text (direct quote)
- source: Document source name
- page: Page number (if available)

Example format:
[
    {{"point": "Key point 1", "citation": "Direct quote 1", "source": "doc_name", "page": 1}},
    {{"point": "Key point 2", "citation": "Direct quote 2", "source": "doc_name", "page": 2}}
]

Output ONLY the JSON array, no other text:"""

        try:
            result = self._call_llm(prompt, response_format="json")
            # Clean up response to extract JSON
            result = result.strip()
            if result.startswith("```json"):
                result = result[7:]
            if result.endswith("```"):
                result = result[:-3]
            result = result.strip()

            citations = json.loads(result)
            if isinstance(citations, list):
                return citations
            return []
        except Exception:
            # Return empty citations on error
            return []

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
        prompt = self._build_prompt([document], config)
        summary_text = self._call_llm(prompt)

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
        prompt = self._build_prompt(documents, config)
        summary_text = self._call_llm(prompt)

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
        comparison = []

        for doc in documents:
            text = doc["text"][:2000]  # Limit for comparison

            prompt = f"""Analyze the following document and extract key information for a comparison table.

**Document**: {doc["name"]}

**Content**:
{text}

Return in JSON format:
{{
    "name": "Document name",
    "mainPoints": "Core arguments (1-2 sentences)",
    "keywords": ["keyword 1", "keyword 2", "keyword 3"],
    "methodology": "Methodology (if any)",
    "conclusions": "Main conclusions"
}}

Output ONLY the JSON object:"""

            try:
                result = self._call_llm(prompt, response_format="json")
                # Clean up response
                result = result.strip()
                if result.startswith("```json"):
                    result = result[7:]
                if result.endswith("```"):
                    result = result[:-3]
                result = result.strip()

                comparison_data = json.loads(result)
                comparison_data["name"] = doc["name"]  # Ensure name is correct
                comparison.append(comparison_data)
            except Exception:
                # Add basic info on error
                comparison.append(
                    {
                        "name": doc["name"],
                        "mainPoints": "Analysis failed",
                        "keywords": [],
                        "methodology": "",
                        "conclusions": "",
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
