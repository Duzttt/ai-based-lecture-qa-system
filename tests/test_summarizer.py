import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

from app.services.summarizer import DocumentSummarizer, summarize_documents


def test_summarize_documents_without_llm(monkeypatch):
    def _raise_if_called(*args, **kwargs):
        raise RuntimeError("call_llm should not be called")

    monkeypatch.setattr("app.services.summarizer.call_llm", _raise_if_called)

    result = summarize_documents(
        [
            {
                "name": "lecture1.pdf",
                "text": (
                    "Machine learning enables systems to learn from data. "
                    "Supervised learning uses labeled examples. "
                    "Evaluation relies on train and test splits."
                ),
            }
        ],
        {"length": "short", "include_citations": True},
    )

    assert isinstance(result["text"], str)
    assert result["text"].strip()
    assert result["document_count"] == 1
    assert result["document"] == "lecture1.pdf"
    assert isinstance(result["citations"], list)


def test_summarize_single_doc_with_llm(monkeypatch):
    llm_response = (
        "This document covers machine learning fundamentals. "
        "It discusses supervised learning with labeled data. "
        "The key conclusion is that evaluation requires proper train-test splits."
    )

    def mock_call_llm(*args, **kwargs):
        return llm_response

    monkeypatch.setattr("app.services.summarizer.call_llm", mock_call_llm)

    result = summarize_documents(
        [
            {
                "name": "ml_intro.pdf",
                "text": (
                    "Machine learning enables systems to learn from data. "
                    "Supervised learning uses labeled examples. "
                    "Evaluation relies on train and test splits."
                ),
            }
        ],
        {"length": "medium", "include_citations": True},
    )

    assert result["text"] == llm_response
    assert result["document_count"] == 1
    assert len(result["citations"]) > 0


def test_llm_failure_falls_back_to_extractive(monkeypatch):
    def mock_call_llm(*args, **kwargs):
        raise RuntimeError("LLM unavailable")

    monkeypatch.setattr("app.services.summarizer.call_llm", mock_call_llm)

    result = summarize_documents(
        [
            {
                "name": "lecture1.pdf",
                "text": (
                    "Machine learning enables systems to learn from data. "
                    "Supervised learning uses labeled examples. "
                    "Evaluation relies on train and test splits."
                ),
            }
        ],
        {"length": "short", "include_citations": False},
    )

    assert isinstance(result["text"], str)
    assert result["text"].strip()
    assert result["document_count"] == 1


def test_citation_extracts_page_from_chunks(monkeypatch):
    def mock_call_llm(*args, **kwargs):
        raise RuntimeError("force extractive")

    monkeypatch.setattr("app.services.summarizer.call_llm", mock_call_llm)

    document = {
        "name": "lecture1.pdf",
        "text": (
            "Machine learning enables systems to learn from data. "
            "Supervised learning uses labeled examples."
        ),
        "chunks": [
            {"text": "Machine learning enables systems to learn from data.", "page": 3},
            {"text": "Supervised learning uses labeled examples.", "page": 5},
        ],
    }

    summarizer = DocumentSummarizer.__new__(DocumentSummarizer)
    summarizer.llm_provider = "local_llm"
    summarizer.model = "test"
    summarizer.base_url = "http://localhost:8080"
    summarizer.timeout = 30

    citations = summarizer._extract_citations(
        document,
        "Machine learning enables systems to learn from data.",
    )

    assert len(citations) > 0
    assert citations[0]["page"] is not None


def test_citation_degrades_without_chunks(monkeypatch):
    document = {
        "name": "lecture1.pdf",
        "text": "Machine learning enables systems to learn from data.",
    }

    summarizer = DocumentSummarizer.__new__(DocumentSummarizer)
    summarizer.llm_provider = "local_llm"
    summarizer.model = "test"
    summarizer.base_url = "http://localhost:8080"
    summarizer.timeout = 30

    citations = summarizer._extract_citations(
        document,
        "Machine learning enables systems to learn from data.",
    )

    assert len(citations) > 0
    assert citations[0]["page"] is None

