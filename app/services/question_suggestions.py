"""
Question Suggestion Service for generating intelligent question suggestions
based on selected documents using an LLM-first approach with template fallback.
"""

import logging
import random
import re
import string
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings

logger = logging.getLogger(__name__)


class QuestionSuggestionError(Exception):
    """Custom exception for question suggestion errors."""

    pass


class QuestionSuggestionService:
    """
    Service for generating smart question suggestions based on document content.

    Uses an LLM-first approach with template fallback:
    1. Extract keywords and key phrases from documents
    2. Ask the LLM to directly generate diverse, specific questions
    3. Fall back to template-based candidates if LLM is unavailable
    """

    QUESTION_TEMPLATES = {
        "concept": [
            "What is {keyword}?",
            "Explain the concept of {keyword}.",
            "Define {keyword} and its importance.",
            "What does {keyword} mean in this context?",
        ],
        "method": [
            "How does {keyword} work?",
            "What is the process of {keyword}?",
            "Explain how {keyword} is implemented.",
            "What are the steps involved in {keyword}?",
        ],
        "comparison": [
            "What's the difference between {keyword1} and {keyword2}?",
            "Compare {keyword1} with {keyword2}.",
            "How does {keyword1} differ from {keyword2}?",
        ],
        "reason": [
            "Why is {keyword} important?",
            "What are the reasons for using {keyword}?",
            "Why do we need {keyword}?",
        ],
        "example": [
            "Can you give an example of {keyword}?",
            "Show a practical example of {keyword}.",
            "How is {keyword} used in real applications?",
        ],
    }

    STOP_WORDS = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "must",
        "shall",
        "can",
        "need",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "as",
        "if",
        "then",
        "than",
        "so",
        "such",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "any",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "very",
        "just",
        "also",
        "now",
        "here",
        "there",
        "when",
        "where",
        "why",
        "how",
        "all",
        "about",
        "into",
        "over",
        "after",
        "before",
        "between",
        "under",
    }

    def __init__(self, llm_provider: str = "local_llm"):
        self.llm_provider = llm_provider

    def extract_keywords(
        self, text: str, top_k: int = 15, min_word_length: int = 3
    ) -> List[Tuple[str, float]]:
        """
        Extract keywords from text using TF-IDF-like scoring.

        Args:
            text: Input text to extract keywords from
            top_k: Number of top keywords to return
            min_word_length: Minimum word length to consider

        Returns:
            List of (keyword, score) tuples
        """
        if not text or not text.strip():
            return []

        # Clean and tokenize
        text = text.lower()
        # Remove punctuation
        text = text.translate(
            str.maketrans(string.punctuation, " " * len(string.punctuation))
        )
        words = text.split()

        # Filter stop words and short words
        filtered_words = [
            w for w in words if len(w) >= min_word_length and w not in self.STOP_WORDS
        ]

        # Count word frequencies
        word_counts = Counter(filtered_words)

        # Calculate simple scoring (frequency * word length bonus)
        scored_keywords = []
        for word, count in word_counts.items():
            # Bonus for longer words (often more specific)
            length_bonus = min(1.5, 1 + (len(word) - min_word_length) * 0.1)
            score = count * length_bonus
            scored_keywords.append((word, score))

        # Sort by score and return top_k
        scored_keywords.sort(key=lambda x: x[1], reverse=True)
        return scored_keywords[:top_k]

    def extract_keyphrases(
        self, text: str, max_phrase_length: int = 3, top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Extract key phrases from text (multi-word expressions).

        Args:
            text: Input text
            max_phrase_length: Maximum number of words in a phrase
            top_k: Number of top phrases to return

        Returns:
            List of (phrase, score) tuples
        """
        if not text or not text.strip():
            return []

        # Extract section headers (look for capitalized phrases or numbered sections)
        headers = self._extract_headers(text)

        # Extract noun phrases using simple pattern matching
        phrases = self._extract_noun_phrases(text, max_phrase_length)

        # Score phrases (headers get bonus)
        phrase_scores: Dict[str, float] = {}
        for phrase in phrases:
            base_score = len(phrase.split())  # Longer phrases get higher base score
            is_header = any(phrase.lower() in h.lower() for h in headers)
            score = base_score * (2.0 if is_header else 1.0)
            phrase_scores[phrase] = score

        # Sort and return top_k
        scored_phrases = sorted(phrase_scores.items(), key=lambda x: x[1], reverse=True)
        return scored_phrases[:top_k]

    def _extract_headers(self, text: str) -> List[str]:
        """Extract section headers from text."""
        headers = []

        # Pattern for numbered sections (e.g., "1. Introduction", "2.1 Background")
        numbered_pattern = r"^\s*(\d+\.?[\d\.]*\s+[A-Z][^\n]{10,60})"
        numbered_matches = re.findall(numbered_pattern, text, re.MULTILINE)
        headers.extend([m.strip() for m in numbered_matches])

        # Pattern for capitalized headers
        cap_pattern = r"^\s*([A-Z][A-Z\s]{3,40})$"
        cap_matches = re.findall(cap_pattern, text, re.MULTILINE)
        headers.extend([m.strip() for m in cap_matches])

        return headers

    def _extract_noun_phrases(self, text: str, max_length: int = 3) -> List[str]:
        """Extract simple noun phrases from text."""
        phrases = []

        # Split into sentences
        sentences = re.split(r"[.!?]", text)

        for sentence in sentences:
            words = sentence.split()
            # Look for adjective-noun or noun-noun patterns
            i = 0
            while i < len(words) - 1:
                # Start with a capitalized or significant word
                if len(words[i]) > 3 and words[i].lower() not in self.STOP_WORDS:
                    phrase_words = [words[i]]
                    j = i + 1
                    # Collect consecutive significant words
                    while j < len(words) and j - i < max_length:
                        if (
                            len(words[j]) > 2
                            and words[j].lower() not in self.STOP_WORDS
                        ):
                            phrase_words.append(words[j])
                            j += 1
                        else:
                            break

                    if len(phrase_words) >= 2:
                        phrase = " ".join(phrase_words)
                        # Clean the phrase
                        phrase = phrase.strip(string.punctuation)
                        if len(phrase) > 5 and phrase not in phrases:
                            phrases.append(phrase)

                    i = j
                else:
                    i += 1

        return phrases

    def generate_candidate_questions(
        self,
        keywords: List[Tuple[str, float]],
        keyphrases: List[Tuple[str, float]],
        num_candidates: int = 15,
    ) -> List[Dict[str, Any]]:
        """
        Generate candidate questions using templates and extracted keywords.

        Args:
            keywords: List of (keyword, score) tuples
            keyphrases: List of (phrase, score) tuples
            num_candidates: Number of candidate questions to generate

        Returns:
            List of question dictionaries with type and text
        """
        candidates: List[Dict[str, Any]] = []

        # Get top keywords and phrases
        top_keywords = [kw[0] for kw in keywords[:8]]
        top_phrases = [ph[0] for ph in keyphrases[:5]]

        # Generate questions from single keywords
        for q_type, templates in self.QUESTION_TEMPLATES.items():
            if q_type == "comparison":
                continue  # Handle separately

            for template in templates[:2]:  # Use first 2 templates per type
                for keyword in top_keywords[:5]:
                    # Skip if keyword is too short or common
                    if len(keyword) < 4:
                        continue

                    question = template.format(keyword=keyword)
                    candidates.append(
                        {
                            "type": q_type,
                            "text": question,
                            "keywords": [keyword],
                        }
                    )

        # Generate comparison questions
        comparison_templates = self.QUESTION_TEMPLATES["comparison"]
        for i, kw1 in enumerate(top_keywords[:4]):
            for kw2 in top_keywords[i + 1 : 5]:
                if kw1 != kw2:
                    template = comparison_templates[0]
                    question = template.format(keyword1=kw1, keyword2=kw2)
                    candidates.append(
                        {
                            "type": "comparison",
                            "text": question,
                            "keywords": [kw1, kw2],
                        }
                    )

        # Generate questions from key phrases
        for phrase in top_phrases[:3]:
            template = "Explain the concept of {keyword}."
            question = template.format(keyword=phrase)
            candidates.append(
                {
                    "type": "concept",
                    "text": question,
                    "keywords": [phrase],
                }
            )

        # Limit to num_candidates
        return candidates[:num_candidates]

    def generate_questions_with_llm(
        self,
        document_context: str,
        doc_names: List[str],
        keywords: List[Tuple[str, float]],
        num_final: int = 3,
    ) -> List[str]:
        """
        Use LLM to directly generate questions from document content.

        Falls back to template-based selection if LLM is unavailable.
        """
        prompt = self._build_direct_generation_prompt(
            document_context, doc_names, keywords, num_final
        )

        try:
            response = self._call_llm(prompt)
            questions = self._parse_llm_response(response, num_final)
            if questions:
                return questions
        except Exception as exc:
            logger.warning("LLM question generation failed: %s", exc)

        return []

    def _call_llm(self, prompt: str) -> str:
        """Dispatch to the configured LLM provider."""
        if self.llm_provider == "local_llm":
            return self._call_local_llm(prompt)
        elif self.llm_provider == "gemini":
            return self._call_gemini(prompt)
        elif self.llm_provider == "openrouter":
            return self._call_openrouter(prompt)
        raise QuestionSuggestionError(f"Unknown LLM provider: {self.llm_provider}")

    def _build_direct_generation_prompt(
        self,
        context: str,
        doc_names: List[str],
        keywords: List[Tuple[str, float]],
        num_final: int,
    ) -> str:
        """Build a prompt that asks the LLM to generate questions directly."""
        context_preview = context[:2000]
        if len(context) > 2000:
            context_preview += "\n..."

        keyword_hints = ", ".join(kw for kw, _ in keywords[:10])
        doc_list = ", ".join(doc_names)

        return f"""You are a teaching assistant helping students study lecture notes.

Based ONLY on the following lecture content from: {doc_list}
Generate EXACTLY {num_final} diverse study questions that a student would find useful.

Requirements:
1. Each question must be answerable from the provided content
2. Cover different cognitive levels: definition, explanation, comparison, application
3. Be specific — reference actual concepts, terms, or processes from the text
4. Keep each question under 20 words
5. Questions must be in English

Key topics found in the documents: {keyword_hints}

Lecture Content:
{context_preview}

Respond with EXACTLY {num_final} questions, one per line, numbered like:
1. <question>
2. <question>
3. <question>

Do NOT add any other text, explanation, or commentary."""

    def _call_local_llm(self, prompt: str) -> str:
        """Call local LLM via Ollama."""
        try:
            from app.services.llm_client import call_llm

            return call_llm(
                provider="local_llm",
                model=settings.LOCAL_LLM_MODEL,
                call_type="suggestion",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                base_url=settings.LOCAL_LLM_BASE_URL,
                timeout=settings.LOCAL_LLM_TIMEOUT_SECONDS,
                keep_alive=settings.LOCAL_LLM_KEEP_ALIVE,
            )
        except Exception as e:
            raise QuestionSuggestionError(f"Local LLM call failed: {e}")

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API."""
        try:
            from app.services.llm_client import call_llm

            return call_llm(
                provider="gemini",
                model=settings.GEMINI_MODEL,
                call_type="suggestion",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                api_key=settings.GEMINI_API_KEY,
                base_url=settings.GEMINI_BASE_URL,
                temperature=0.7,
                max_tokens=500,
            )
        except Exception as e:
            raise QuestionSuggestionError(f"Gemini call failed: {e}")

    def _call_openrouter(self, prompt: str) -> str:
        """Call OpenRouter API."""
        try:
            from app.services.llm_client import call_llm

            return call_llm(
                provider="openrouter",
                model=settings.OPENROUTER_MODEL,
                call_type="suggestion",
                messages=[{"role": "user", "content": prompt}],
                query_text=prompt[:200],
                api_key=settings.OPENROUTER_API_KEY,
                base_url=settings.OPENROUTER_BASE_URL,
                temperature=0.7,
                max_tokens=500,
            )
        except Exception as e:
            raise QuestionSuggestionError(f"OpenRouter call failed: {e}")

    def _parse_llm_response(self, response: str, num_final: int) -> List[str]:
        """Parse LLM response to extract generated questions.

        Handles formats like:
        - ``1. What is X?``
        - ``1) What is X?``
        - ``- What is X?``
        - Plain question lines ending with ``?``
        """
        questions: List[str] = []

        numbered_re = re.compile(r"^\s*\d+[\.\)]\s*(.+)")

        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Strip leading bullet/dash
            if line.startswith("- "):
                line = line[2:].strip()

            # Try numbered format: "1. Question text" or "1) Question text"
            match = numbered_re.match(line)
            if match:
                question = match.group(1).strip()
            elif line.endswith("?") and len(line) < 150:
                question = line
            else:
                continue

            # Clean up trailing/leading quotes
            question = question.strip("\"'")
            if question and question not in questions:
                questions.append(question)

        return questions[:num_final]

    def _select_diverse_questions(
        self, candidates: List[Dict[str, Any]], num_final: int
    ) -> List[str]:
        """
        Select diverse questions without LLM (fallback method).

        Prioritizes:
        1. Different question types
        2. Higher-scored keywords
        3. Questions under 15 words
        """
        selected: List[str] = []
        selected_types: set = set()

        # Group candidates by type
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for candidate in candidates:
            q_type = candidate["type"]
            if q_type not in by_type:
                by_type[q_type] = []
            by_type[q_type].append(candidate)

        # Prioritize order of question types
        type_priority = ["concept", "method", "comparison", "reason", "example"]

        # Select one question per type until we have enough
        for q_type in type_priority:
            if len(selected) >= num_final:
                break

            if q_type not in by_type:
                continue

            # Sort candidates by keyword score (approximated by position)
            type_candidates = by_type[q_type]

            for candidate in type_candidates:
                question = candidate["text"]

                # Skip if too long
                if len(question.split()) > 15:
                    continue

                # Skip if similar to already selected
                if self._is_similar_to_selected(question, selected):
                    continue

                selected.append(question)
                selected_types.add(q_type)
                break

        # If still need more, add from any type
        if len(selected) < num_final:
            for candidate in candidates:
                if len(selected) >= num_final:
                    break

                question = candidate["text"]
                if len(question.split()) <= 15 and question not in selected:
                    selected.append(question)

        return selected[:num_final]

    def _is_similar_to_selected(
        self, question: str, selected: List[str], threshold: float = 0.6
    ) -> bool:
        """Check if a question is too similar to already selected questions."""
        question_words = set(question.lower().split())

        for sel_question in selected:
            sel_words = set(sel_question.lower().split())

            # Simple Jaccard similarity
            if question_words and sel_words:
                intersection = len(question_words & sel_words)
                union = len(question_words | sel_words)
                similarity = intersection / union if union > 0 else 0

                if similarity > threshold:
                    return True

        return False

    def generate_suggestions(
        self,
        documents: List[Dict[str, Any]],
        num_suggestions: int = 3,
    ) -> Dict[str, Any]:
        """
        Generate question suggestions for *exactly* the selected documents.

        Uses an LLM-first approach: ask the LLM to generate questions directly
        from the document content.  Falls back to template-based candidate
        selection when the LLM is unavailable or returns an unusable response.
        """
        if not documents:
            return {"suggestions": [], "generated_from": []}

        all_text: List[str] = []
        doc_names: List[str] = []

        for doc in documents:
            doc_name = doc.get("name") or doc.get("filename", "Unknown")
            doc_names.append(doc_name)

            content = doc.get("content", "")
            chunks = doc.get("chunks", [])
            if chunks:
                num_samples = min(10, len(chunks))
                sampled_chunks = random.sample(chunks, num_samples)
                chunk_texts = [c.get("text", "") for c in sampled_chunks]
                content = "\n".join(chunk_texts)

            if content:
                all_text.append(f"=== {doc_name} ===\n{content}")

        combined_text = "\n\n".join(all_text)
        if not combined_text.strip():
            return {"suggestions": [], "generated_from": doc_names}

        keywords = self.extract_keywords(combined_text, top_k=15)
        keyphrases = self.extract_keyphrases(combined_text, top_k=10)

        # LLM-first: ask the LLM to generate questions directly
        final_questions = self.generate_questions_with_llm(
            combined_text, doc_names, keywords, num_final=num_suggestions
        )

        if not final_questions:
            # Fallback: template candidates + diverse selection
            candidates = self.generate_candidate_questions(
                keywords, keyphrases, num_candidates=15
            )
            final_questions = self._select_diverse_questions(
                candidates, num_suggestions
            )

        return {
            "suggestions": final_questions,
            "generated_from": doc_names,
        }


_service_instance: Optional[QuestionSuggestionService] = None


def get_question_suggestion_service(
    llm_provider: Optional[str] = None,
) -> QuestionSuggestionService:
    """Get or create the question suggestion service instance.

    Re-creates the instance when the requested provider differs from the
    current one so runtime provider changes take effect immediately.
    """
    global _service_instance
    provider = llm_provider or getattr(settings, "LLM_PROVIDER", "local_llm")

    if _service_instance is None or _service_instance.llm_provider != provider:
        _service_instance = QuestionSuggestionService(provider)

    return _service_instance


def generate_question_suggestions(
    documents: List[Dict[str, Any]],
    num_suggestions: int = 3,
) -> Dict[str, Any]:
    """Convenience function to generate question suggestions."""
    service = get_question_suggestion_service()
    return service.generate_suggestions(documents, num_suggestions)
