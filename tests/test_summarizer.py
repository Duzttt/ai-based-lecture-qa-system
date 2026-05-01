import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

from app.services.summarizer import summarize_documents


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

