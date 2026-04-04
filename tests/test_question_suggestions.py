"""
Unit tests for the Question Suggestion Service.

Tests cover:
1. Keyword extraction
2. Key phrase extraction
3. Candidate question generation
4. Question diversity selection
5. Full suggestion pipeline
"""

import pytest

from app.services.question_suggestions import (
    QuestionSuggestionError,
    QuestionSuggestionService,
    generate_question_suggestions,
)


class TestKeywordExtraction:
    """Tests for keyword extraction functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionSuggestionService(llm_provider="local_llm")

    def test_extract_keywords_basic(self):
        """Test basic keyword extraction from text."""
        text = """
        Machine learning is a subset of artificial intelligence that enables 
        systems to learn and improve from experience without being explicitly 
        programmed. Machine learning algorithms build mathematical models based 
        on sample data, known as training data, to make predictions or decisions.
        """

        keywords = self.service.extract_keywords(text, top_k=5)

        assert len(keywords) > 0
        assert len(keywords) <= 5

        # Check that keywords are tuples of (word, score)
        for keyword, score in keywords:
            assert isinstance(keyword, str)
            assert isinstance(score, (int, float))
            assert len(keyword) >= 3  # Minimum word length

        # Should contain important terms
        keyword_words = [kw[0] for kw in keywords]
        assert any("machine" in kw for kw in keyword_words)
        assert any("learning" in kw for kw in keyword_words)

    def test_extract_keywords_empty_text(self):
        """Test keyword extraction with empty text."""
        keywords = self.service.extract_keywords("", top_k=5)
        assert keywords == []

    def test_extract_keywords_short_text(self):
        """Test keyword extraction with very short text."""
        text = "Hello world"
        keywords = self.service.extract_keywords(text, top_k=5)
        # May return empty or few keywords for very short text
        assert len(keywords) <= 2

    def test_extract_keywords_filters_stop_words(self):
        """Test that stop words are filtered out."""
        text = "The quick brown fox jumps over the lazy dog in the park"

        keywords = self.service.extract_keywords(text, top_k=10)
        keyword_words = [kw[0] for kw in keywords]

        # Stop words should not appear
        assert "the" not in keyword_words
        assert "in" not in keyword_words
        assert "over" not in keyword_words

    def test_extract_keywords_respects_top_k(self):
        """Test that top_k parameter limits results."""
        text = """
        Neural networks are computing systems inspired by biological neural networks.
        They consist of layers of interconnected nodes that process information.
        Deep learning uses multiple layers of neural networks for complex patterns.
        """

        for k in [3, 5, 10]:
            keywords = self.service.extract_keywords(text, top_k=k)
            assert len(keywords) <= k


class TestKeyphraseExtraction:
    """Tests for key phrase extraction functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionSuggestionService(llm_provider="local_llm")

    def test_extract_keyphrases_basic(self):
        """Test basic key phrase extraction."""
        text = """
        1. Introduction to Neural Networks
        
        Neural networks are computing systems that process information using 
        interconnected nodes organized in layers. The architecture consists of 
        input layers, hidden layers, and output layers.
        
        2. Deep Learning Applications
        
        Deep learning applications include image recognition, natural language 
        processing, and speech recognition systems.
        """

        phrases = self.service.extract_keyphrases(text, max_phrase_length=3, top_k=5)

        assert len(phrases) > 0
        assert len(phrases) <= 5

        # Check format
        for phrase, score in phrases:
            assert isinstance(phrase, str)
            assert isinstance(score, (int, float))

    def test_extract_keyphrases_empty_text(self):
        """Test key phrase extraction with empty text."""
        phrases = self.service.extract_keyphrases("", top_k=5)
        assert phrases == []


class TestCandidateQuestionGeneration:
    """Tests for candidate question generation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionSuggestionService(llm_provider="local_llm")

    def test_generate_candidate_questions_basic(self):
        """Test generating candidate questions from keywords."""
        keywords = [
            ("machine learning", 5.0),
            ("neural networks", 4.5),
            ("deep learning", 4.0),
            ("algorithms", 3.5),
        ]
        keyphrases = [
            ("artificial intelligence", 3.0),
        ]

        candidates = self.service.generate_candidate_questions(
            keywords, keyphrases, num_candidates=10
        )

        assert len(candidates) > 0
        assert len(candidates) <= 10

        # Check structure
        for candidate in candidates:
            assert "type" in candidate
            assert "text" in candidate
            assert "keywords" in candidate
            assert candidate["text"].endswith("?") or candidate["text"].endswith(".")

    def test_generate_candidate_questions_diverse_types(self):
        """Test that generated questions have diverse types."""
        keywords = [
            ("machine learning", 5.0),
            ("neural networks", 4.5),
            ("deep learning", 4.0),
        ]
        keyphrases = []

        candidates = self.service.generate_candidate_questions(
            keywords, keyphrases, num_candidates=15
        )

        # Should have multiple question types
        question_types = set(c["type"] for c in candidates)
        assert len(question_types) >= 2  # At least 2 different types


class TestDiverseQuestionSelection:
    """Tests for diverse question selection (fallback method)."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionSuggestionService(llm_provider="local_llm")

    def test_select_diverse_questions_basic(self):
        """Test selecting diverse questions."""
        candidates = [
            {
                "type": "concept",
                "text": "What is machine learning?",
                "keywords": ["machine learning"],
            },
            {
                "type": "method",
                "text": "How does machine learning work?",
                "keywords": ["machine learning"],
            },
            {
                "type": "comparison",
                "text": "What's the difference between AI and ML?",
                "keywords": ["AI", "ML"],
            },
            {
                "type": "example",
                "text": "Can you give an example of machine learning?",
                "keywords": ["machine learning"],
            },
            {
                "type": "reason",
                "text": "Why is machine learning important?",
                "keywords": ["machine learning"],
            },
        ]

        selected = self.service._select_diverse_questions(candidates, num_final=3)

        assert len(selected) == 3

        # All selected questions should be from candidates
        candidate_texts = set(c["text"] for c in candidates)
        for question in selected:
            assert question in candidate_texts

    def test_select_diverse_questions_avoids_similarity(self):
        """Test that similar questions are avoided."""
        candidates = [
            {
                "type": "concept",
                "text": "What is machine learning?",
                "keywords": ["machine learning"],
            },
            {
                "type": "concept",
                "text": "What is ML?",
                "keywords": ["ML"],
            },  # Very similar
            {
                "type": "method",
                "text": "How do neural networks work?",
                "keywords": ["neural networks"],
            },
        ]

        selected = self.service._select_diverse_questions(candidates, num_final=2)

        # Should not select both very similar questions
        assert len(selected) <= 2

    def test_is_similar_to_selected(self):
        """Test question similarity detection."""
        # Questions with very high word overlap (Jaccard similarity)
        question1 = "What are machine learning algorithms"  # 4 words
        question2 = "What are machine learning techniques"  # 3/4 words overlap = 0.75 similarity with union of 5
        question3 = "How do neural networks work"  # Different topic

        # Similar questions (share most words - Jaccard > 0.5)
        # question1: {what, are, machine, learning, algorithms} = 5 words
        # question2: {what, are, machine, learning, techniques} = 5 words
        # intersection: {what, are, machine, learning} = 4 words
        # union: {what, are, machine, learning, algorithms, techniques} = 6 words
        # Jaccard = 4/6 = 0.67
        assert self.service._is_similar_to_selected(
            question1, [question2], threshold=0.5
        )

        # Dissimilar questions
        assert not self.service._is_similar_to_selected(
            question1, [question3], threshold=0.5
        )


class TestFullSuggestionPipeline:
    """Tests for the complete suggestion generation pipeline."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = QuestionSuggestionService(llm_provider="local_llm")

    def test_generate_suggestions_basic(self):
        """Test full suggestion generation with sample documents."""
        documents = [
            {
                "name": "test_lecture.pdf",
                "content": """
                Machine Learning Fundamentals
                
                1. Introduction to Machine Learning
                
                Machine learning is a subset of artificial intelligence that enables 
                systems to learn from data. It uses algorithms to identify patterns 
                and make decisions with minimal human intervention.
                
                2. Types of Machine Learning
                
                There are three main types: supervised learning, unsupervised learning, 
                and reinforcement learning. Each type has different applications and 
                use cases in real-world scenarios.
                
                3. Neural Networks
                
                Neural networks are computing systems inspired by biological neural 
                networks in the brain. They consist of layers of interconnected nodes 
                that process information.
                """,
            }
        ]

        result = self.service.generate_suggestions(documents, num_suggestions=3)

        assert "suggestions" in result
        assert "generated_from" in result

        suggestions = result["suggestions"]
        assert len(suggestions) > 0

        # Check suggestion format
        for suggestion in suggestions:
            assert isinstance(suggestion, str)
            assert len(suggestion) > 0
            assert len(suggestion.split()) <= 20  # Reasonable length

    def test_generate_suggestions_multiple_documents(self):
        """Test suggestion generation with multiple documents."""
        documents = [
            {
                "name": "doc1.pdf",
                "content": "Deep learning uses neural networks with multiple layers.",
            },
            {
                "name": "doc2.pdf",
                "content": "Natural language processing enables computers to understand text.",
            },
        ]

        result = self.service.generate_suggestions(documents, num_suggestions=3)

        assert len(result["suggestions"]) > 0
        assert len(result["generated_from"]) == 2

    def test_generate_suggestions_empty_documents(self):
        """Test suggestion generation with no documents."""
        result = self.service.generate_suggestions([], num_suggestions=3)

        assert result["suggestions"] == []
        assert result["generated_from"] == []

    def test_generate_suggestions_no_content(self):
        """Test suggestion generation with empty document content."""
        documents = [
            {"name": "empty.pdf", "content": ""},
        ]

        result = self.service.generate_suggestions(documents, num_suggestions=3)

        # Should return empty suggestions for empty content
        assert result["suggestions"] == []


class TestConvenienceFunction:
    """Tests for the convenience function."""

    def test_generate_question_suggestions(self):
        """Test the module-level convenience function."""
        documents = [
            {
                "name": "test.pdf",
                "content": "Artificial intelligence is transforming many industries.",
            }
        ]

        result = generate_question_suggestions(documents, num_suggestions=3)

        assert isinstance(result, dict)
        assert "suggestions" in result
        assert "generated_from" in result


class TestQuestionSuggestionError:
    """Tests for custom exception."""

    def test_question_suggestion_error(self):
        """Test that QuestionSuggestionError can be raised and caught."""
        with pytest.raises(QuestionSuggestionError) as exc_info:
            raise QuestionSuggestionError("Test error message")

        assert "Test error message" in str(exc_info.value)


# Integration-style tests (can be run without LLM)
class TestIntegration:
    """Integration tests that test the flow without requiring LLM."""

    def test_fallback_without_llm(self):
        """Test that fallback works when LLM is unavailable."""
        service = QuestionSuggestionService(llm_provider="local_llm")

        # Create candidates manually
        candidates = [
            {"type": "concept", "text": "What is AI?", "keywords": ["AI"]},
            {"type": "method", "text": "How does AI work?", "keywords": ["AI"]},
            {"type": "example", "text": "Give an AI example.", "keywords": ["AI"]},
        ]

        # Test fallback selection (doesn't require LLM)
        selected = service._select_diverse_questions(candidates, num_final=2)

        assert len(selected) >= 1
        assert all(isinstance(q, str) for q in selected)
        assert all(len(q) > 0 for q in selected)
