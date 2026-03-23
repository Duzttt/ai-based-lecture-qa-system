"""
Document Summarizer Service

Provides intelligent summarization for single or multiple documents
using LLM-based generation.
"""

import json
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings


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
        "bullets": "用要点形式（bullet points）列出核心内容，每个要点简洁明了",
        "narrative": "用连贯的叙述方式概括，段落之间逻辑清晰、过渡自然",
        "academic": "用学术语言撰写，包含主要论点、方法论和结论，保持严谨性",
        "executive": "用行政摘要风格，突出关键发现和行动建议",
    }

    # Language options
    LANGUAGE_OPTIONS = {
        "zh": "中文",
        "en": "English",
        "ja": "日本語",
    }

    def __init__(self, llm_provider: str = None, model: str = None):
        """
        Initialize the summarizer.

        Args:
            llm_provider: LLM provider (gemini, openrouter, local_qwen)
            model: Model name to use
        """
        self.llm_provider = llm_provider or "local_qwen"
        self.model = model or settings.LOCAL_QWEN_MODEL
        self.base_url = settings.LOCAL_QWEN_BASE_URL
        self.timeout = settings.LOCAL_QWEN_TIMEOUT_SECONDS

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
        language = config.get("language", "zh")
        include_citations = config.get("include_citations", True)

        length_info = self.LENGTH_LIMITS.get(
            length_config, self.LENGTH_LIMITS["medium"]
        )
        style_prompt = self.STYLE_PROMPTS.get(style, self.STYLE_PROMPTS["narrative"])
        language_name = self.LANGUAGE_OPTIONS.get(language, "中文")

        if len(documents) == 1:
            # Single document summary
            doc = documents[0]
            # Truncate text if too long (keep first 5000 chars)
            text = doc["text"][:5000] if len(doc["text"]) > 5000 else doc["text"]

            prompt = f"""请对以下文档生成摘要。

**文档名称**: {doc["name"]}

**文档内容**:
{text}

**要求**:
- 摘要长度：约 {length_info["tokens"]} 词，{length_info["sentences"]} 句
- 风格：{style_prompt}
- 语言：{language_name}
- 保持原文的专业术语和关键概念
- 突出文档的核心观点和重要结论
{f"- 在摘要后列出关键引用段落（包含页码）" if include_citations else ""}

请直接输出摘要内容："""

        else:
            # Multi-document synthesis
            doc_list = "\n\n".join(
                [
                    f"**文档 {i+1}**: {doc['name']}\n{doc['text'][:1000]}..."
                    for i, doc in enumerate(documents)
                ]
            )

            prompt = f"""请对以下 {len(documents)} 个相关文档进行综合摘要。

{doc_list}

**要求**:
- 综合各个文档的核心观点，形成连贯的综述
- 指出文档间的共识、差异和互补之处
- 风格：{style_prompt}
- 语言：{language_name}
- 长度：中等篇幅（约 400-500 词）
- 如文档间存在矛盾，请明确指出
{f"- 在摘要后列出各文档的关键引用" if include_citations else ""}

请直接输出综合摘要："""

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
        if self.llm_provider == "local_qwen":
            return self._call_local_qwen(prompt, response_format)
        elif self.llm_provider == "gemini":
            return self._call_gemini(prompt, response_format)
        elif self.llm_provider == "openrouter":
            return self._call_openrouter(prompt, response_format)
        else:
            raise SummarizerError(f"Unsupported LLM provider: {self.llm_provider}")

    def _call_local_qwen(self, prompt: str, response_format: str = None) -> str:
        """Call local Qwen model via Ollama."""
        try:
            from ollama import Client as OllamaClient

            client = OllamaClient(
                host=self.base_url,
                timeout=self.timeout,
            )

            system_prompt = "You are a professional document summarization assistant. Generate clear, accurate summaries."
            if response_format == "json":
                system_prompt += " Output ONLY valid JSON."

            response = client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                stream=False,
                keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
            )

            return str(response.get("message", {}).get("content", "")).strip()

        except Exception as e:
            raise SummarizerError(f"Failed to call local Qwen: {str(e)}")

    def _call_gemini(self, prompt: str, response_format: str = None) -> str:
        """Call Google Gemini API."""
        try:
            api_key = settings.GEMINI_API_KEY
            if not api_key:
                raise SummarizerError("Gemini API key not configured")

            model_name = settings.GEMINI_MODEL
            base_url = settings.GEMINI_BASE_URL

            headers = {
                "Content-Type": "application/json",
            }

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "topK": 40,
                    "topP": 0.95,
                    "maxOutputTokens": 2048,
                },
            }

            if response_format == "json":
                payload["generationConfig"]["responseMimeType"] = "application/json"

            response = httpx.post(
                f"{base_url}/models/{model_name}:generateContent?key={api_key}",
                json=payload,
                timeout=60,
            )
            response.raise_for_status()

            data = response.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise SummarizerError("No response from Gemini")

            return (
                candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            )

        except httpx.HTTPStatusError as e:
            raise SummarizerError(f"Gemini API error: {e.response.status_code}")
        except Exception as e:
            raise SummarizerError(f"Failed to call Gemini: {str(e)}")

    def _call_openrouter(self, prompt: str, response_format: str = None) -> str:
        """Call OpenRouter API."""
        try:
            api_key = settings.OPENROUTER_API_KEY
            if not api_key:
                raise SummarizerError("OpenRouter API key not configured")

            model = settings.OPENROUTER_MODEL

            system_prompt = "You are a professional document summarization assistant. Generate clear, accurate summaries."
            if response_format == "json":
                system_prompt += " Output ONLY valid JSON."

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "stream": False,
            }

            response = httpx.post(
                f"{settings.OPENROUTER_BASE_URL}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise SummarizerError("No response from OpenRouter")

            return choices[0].get("message", {}).get("content", "").strip()

        except httpx.HTTPStatusError as e:
            raise SummarizerError(f"OpenRouter API error: {e.response.status_code}")
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

        prompt = f"""给定原文和它的摘要，找出摘要中每个关键观点对应的原文段落。

**原文**:
{text}

**摘要**:
{summary}

请以 JSON 数组格式返回，每个元素包含：
- point: 摘要中的关键观点（简短）
- citation: 对应的原文段落（直接引用）
- source: 文档来源
- page: 页码（如果有）

返回格式示例：
[
    {{"point": "观点 1", "citation": "原文引用 1", "source": "文档名", "page": 1}},
    {{"point": "观点 2", "citation": "原文引用 2", "source": "文档名", "page": 2}}
]

只返回 JSON 数组，不要其他文字："""

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
        except Exception as e:
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

            prompt = f"""分析以下文档，提取关键信息用于对比表格。

**文档**: {doc["name"]}

**内容**:
{text}

请以 JSON 格式返回：
{{
    "name": "文档名称",
    "mainPoints": "核心观点（1-2 句话）",
    "keywords": ["关键词 1", "关键词 2", "关键词 3"],
    "methodology": "方法论（如果有）",
    "conclusions": "主要结论"
}}

只返回 JSON 对象："""

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
                        "mainPoints": "分析失败",
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
        "language": "zh",
        "include_citations": True,
        "include_comparison": True,
    }

    if config:
        default_config.update(config)

    summarizer = DocumentSummarizer()
    return summarizer.generate_summary(documents, default_config)
