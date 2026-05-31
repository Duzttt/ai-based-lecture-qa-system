# Retrieval Quality Improvement — Phase 1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Persist HybridRetriever as a global singleton (built once, used for all queries) and enable it by default.

**Architecture:** Create `HybridRetrieverService` that wraps the existing `HybridRetriever` with lazy singleton initialization and automatic refresh on PDF indexing. Modify `local_rag.py` to always call hybrid retrieval by default, falling back to dense-only when no documents are indexed.

**Tech Stack:** Python, FAISS, BM25 (rank_bm25), SentenceTransformers

---

### Task 1: Create HybridRetrieverService

**Files:**
- Create: `app/services/hybrid_retriever_service.py`
- Test: `tests/test_hybrid_retriever_service.py`

**Step 1: Write the failing test**

Create `tests/test_hybrid_retriever_service.py`:

```python
import pytest
from unittest.mock import Mock, patch, PropertyMock
from app.services.hybrid_retriever_service import HybridRetrieverService


class TestHybridRetrieverService:
    def test_get_instance_returns_singleton(self):
        instance1 = HybridRetrieverService.get_instance()
        instance2 = HybridRetrieverService.get_instance()
        assert instance1 is instance2

    def test_get_instance_returns_none_when_no_documents(self):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False
        with patch(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            return_value=Mock(chunks=[]),
        ):
            result = HybridRetrieverService.get_instance()
            assert result is None

    def test_refresh_rebuilds_index(self, monkeypatch):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False

        fake_chunks = [
            {"text": "doc1 text", "source": "a.pdf", "page": 1},
            {"text": "doc2 text", "source": "b.pdf", "page": 1},
        ]
        mock_store = Mock()
        mock_store.chunks = fake_chunks
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            lambda **kwargs: mock_store,
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.HybridRetriever",
            lambda documents, model_name, fusion_method: Mock(
                retrieve=lambda query, top_k: [
                    {"text": d["text"], "source": d["source"], "score": 0.9}
                    for d in documents[:top_k]
                ],
                get_document_count=lambda: len(fake_chunks),
            ),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.load_runtime_embedding_settings",
            lambda: {"model_id": "test-model", "embedding_dim": 384},
        )

        service = HybridRetrieverService.get_instance()
        assert service is not None
        assert service.get_document_count() == 2

    def test_search_returns_results(self, monkeypatch):
        HybridRetrieverService._instance = None
        HybridRetrieverService._initialized = False

        fake_chunks = [
            {"text": "doc1 text", "source": "a.pdf", "page": 1},
            {"text": "doc2 text", "source": "b.pdf", "page": 2},
        ]
        mock_store = Mock()
        mock_store.chunks = fake_chunks
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.VectorStore.get_cached",
            lambda **kwargs: mock_store,
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.HybridRetriever",
            lambda documents, model_name, fusion_method: Mock(
                retrieve=lambda query, top_k: [
                    {"text": "doc1 text", "source": "a.pdf", "score": 0.9}
                ],
                get_document_count=lambda: len(fake_chunks),
            ),
        )
        monkeypatch.setattr(
            "app.services.hybrid_retriever_service.load_runtime_embedding_settings",
            lambda: {"model_id": "test-model", "embedding_dim": 384},
        )

        service = HybridRetrieverService.get_instance()
        results = service.search("test query", top_k=5)
        assert len(results) == 1
        assert results[0]["text"] == "doc1 text"
        assert results[0]["score"] == 0.9

    def test_clear_resets_singleton(self):
        HybridRetrieverService._instance = Mock()
        HybridRetrieverService._initialized = True
        HybridRetrieverService.clear()
        assert HybridRetrieverService._instance is None
        assert HybridRetrieverService._initialized is False
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_hybrid_retriever_service.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.hybrid_retriever_service'"

**Step 3: Write minimal implementation**

Create `app/services/hybrid_retriever_service.py`:

```python
import logging
import threading
from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.vector_store import VectorStore

try:
    from retrieval.hybrid_retriever import FusionMethod, HybridRetriever

    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False

logger = logging.getLogger("hybrid_retriever_service")


class HybridRetrieverServiceError(Exception):
    pass


class HybridRetrieverService:
    _instance: Optional["HybridRetrieverService"] = None
    _initialized: bool = False
    _lock: threading.Lock = threading.Lock()

    def __init__(self, retriever: HybridRetriever, model_name: str) -> None:
        self._retriever = retriever
        self._model_name = model_name

    @classmethod
    def get_instance(cls) -> Optional["HybridRetrieverService"]:
        if cls._instance is not None:
            return cls._instance

        if not HYBRID_AVAILABLE:
            return None

        with cls._lock:
            if cls._instance is not None:
                return cls._instance
            if cls._initialized:
                return cls._instance

            try:
                rt = load_runtime_embedding_settings()
                vector_store = VectorStore.get_cached(
                    index_path=settings.FAISS_INDEX_PATH,
                    embedding_dim=rt["embedding_dim"],
                )

                documents = _build_document_list(vector_store.chunks)
                if not documents:
                    logger.warning("No documents available for hybrid retrieval")
                    cls._initialized = True
                    return None

                retriever = HybridRetriever(
                    documents=documents,
                    model_name=rt["model_id"],
                    fusion_method=FusionMethod.RRF,
                )

                cls._instance = cls(retriever, rt["model_id"])
                cls._initialized = True
                logger.info(
                    "HybridRetrieverService initialized with %d documents",
                    len(documents),
                )
                return cls._instance

            except Exception as exc:
                logger.error("Failed to initialize hybrid retriever: %s", exc)
                cls._initialized = True
                return None

    @classmethod
    def refresh(cls) -> None:
        with cls._lock:
            cls._instance = None
            cls._initialized = False
        logger.info("HybridRetrieverService cache cleared, will rebuild on next query")

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._instance = None
            cls._initialized = False

    def search(
        self, query: str, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        hybrid_results = self._retriever.retrieve(query=query, top_k=top_k)
        return [
            {
                "text": r.get("text", ""),
                "source": r.get("source", "unknown"),
                "page": r.get("metadata", {}).get("page"),
                "score": r.get("score", 0.0),
            }
            for r in hybrid_results
        ]

    def get_document_count(self) -> int:
        return self._retriever.get_document_count()


def _build_document_list(chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    documents = []
    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text.strip():
            continue
        documents.append(
            {
                "id": f"chunk_{i}",
                "text": text,
                "source": chunk.get("source", "unknown"),
                "metadata": {
                    "page": chunk.get("page"),
                    "source": chunk.get("source", "unknown"),
                },
            }
        )
    return documents
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_hybrid_retriever_service.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/hybrid_retriever_service.py tests/test_hybrid_retriever_service.py
git commit -m "feat: add HybridRetrieverService singleton for persistent hybrid retrieval"
```

---

### Task 2: Integrate into local_rag.py

**Files:**
- Modify: `app/services/local_rag.py`
- Test: `tests/test_local_rag.py` (existing)

**Step 1: Understand existing code**

The existing `local_rag.py` already has:
- `_is_hybrid_enabled()` at line 62 — checks config flag
- `retrieve_with_hybrid()` at line 69 — rebuilds HybridRetriever per call
- `retrieve_with_faiss()` at line 131 — dispatches to hybrid or dense

We need to:
1. Remove `_is_hybrid_enabled()` and `retrieve_with_hybrid()` logic
2. Replace with `HybridRetrieverService.get_instance().search()`
3. Fall back to pure dense when hybrid is unavailable

**Step 2: Write failing test first**

Add to `tests/test_local_rag.py`:

```python
def test_retrieve_with_faiss_uses_hybrid_service_when_available(monkeypatch):
    from app.services.local_rag import retrieve_with_faiss

    fake_results = [
        {"text": "result 1", "source": "a.pdf", "page": 1, "score": 0.95},
        {"text": "result 2", "source": "a.pdf", "page": 2, "score": 0.80},
    ]

    class FakeHybridService:
        @staticmethod
        def get_instance():
            return FakeHybridService()

        def search(self, query, top_k=5):
            return fake_results

    monkeypatch.setattr(
        "app.services.local_rag.HybridRetrieverService",
        FakeHybridService,
    )

    results = retrieve_with_faiss("test query", top_k=5)
    assert len(results) == 2
    assert results[0]["text"] == "result 1"
    assert results[0]["score"] == 0.95


def test_retrieve_with_faiss_falls_back_to_dense_when_hybrid_unavailable(monkeypatch):
    from app.services.local_rag import retrieve_with_faiss

    monkeypatch.setattr(
        "app.services.local_rag.HybridRetrieverService",
        type("HS", (), {"get_instance": staticmethod(lambda: None)}),
    )

    fake_results = [
        {"text": "dense result", "source": "b.pdf", "page": 1},
    ]

    monkeypatch.setattr(
        "app.services.local_rag.load_runtime_embedding_settings",
        lambda: {"model_id": "test", "embedding_dim": 384},
    )

    class FakeVectorStore:
        chunks = [{"text": "dense result", "source": "b.pdf", "page": 1}]
        search_with_metadata = classmethod(
            lambda cls, *a, **kw: [{"text": "dense result", "source": "b.pdf", "page": 1}]
        )
        @classmethod
        def get_cached(cls, **kw):
            return FakeVectorStore()

    monkeypatch.setattr(
        "app.services.local_rag.VectorStore",
        FakeVectorStore,
    )

    mock_embed = Mock()
    mock_embed.embed_query.return_value = [0.1] * 384
    monkeypatch.setattr(
        "app.services.local_rag.EmbeddingService",
        lambda **kw: mock_embed,
    )

    results = retrieve_with_faiss("test query", top_k=5)
    assert len(results) == 1
    assert results[0]["text"] == "dense result"
```

**Step 3: Run tests to verify they fail**

Run: `pytest tests/test_local_rag.py::test_retrieve_with_faiss_uses_hybrid_service_when_available -v`
Expected: FAIL — existing code doesn't use HybridRetrieverService yet

**Step 4: Modify local_rag.py**

Replace the relevant section of `app/services/local_rag.py`:

Replace lines 12-18 (imports):
```python
from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.hybrid_retriever_service import HybridRetrieverService
from app.services.llm_client import call_llm
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.runtime_llm import load_runtime_llm_settings, resolve_gemini_api_model
from app.services.vector_store import VectorStore, VectorStoreError
```

Remove lines 13-25 (remove HYBRID_AVAILABLE and LLAMA_AVAILABLE imports):
```python
# Remove these:
try:
    from app.services.llama_vector_store import LlamaVectorStore
    LLAMA_AVAILABLE = True
except ImportError:
    LLAMA_AVAILABLE = False

try:
    from retrieval.hybrid_retriever import FusionMethod, HybridRetriever
    HYBRID_AVAILABLE = True
except ImportError:
    HYBRID_AVAILABLE = False
```

Replace lines 62-128 (remove `_is_hybrid_enabled()` and `retrieve_with_hybrid()`) and modify `retrieve_with_faiss()`:

```python
def retrieve_with_faiss(
    query: str, top_k: int = 5, source_filter: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    if not query.strip():
        raise LocalRAGError("Query cannot be empty")

    hybrid_service = HybridRetrieverService.get_instance()
    if hybrid_service is not None:
        try:
            search_k = top_k * 10 if source_filter else top_k
            results = hybrid_service.search(query=query, top_k=search_k)

            if source_filter:
                normalized_filters = [str(s).lower().strip() for s in source_filter]
                filtered = []
                for r in results:
                    source = str(r.get("source", "")).lower().strip()
                    for f in normalized_filters:
                        if source == f or source.startswith(f) or f in source:
                            filtered.append(r)
                            break
                return filtered[:top_k]

            return results[:top_k]
        except Exception as exc:
            logger.warning("Hybrid retrieval failed, falling back to dense: %s", exc)

    rt = load_runtime_embedding_settings()
    embedding_service = EmbeddingService(model_name=rt["model_id"])

    vector_store = VectorStore.get_cached(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=rt["embedding_dim"],
    )

    try:
        query_embedding = embedding_service.embed_query(query)
        search_k = top_k * 10 if source_filter else top_k
        results = vector_store.search_with_metadata(query_embedding, top_k=search_k)

        if source_filter:
            normalized_filters = [str(s).lower().strip() for s in source_filter]
            filtered = []
            for r in results:
                source = str(r.get("source", "")).lower().strip()
                for f in normalized_filters:
                    if source == f or source.startswith(f) or f in source:
                        filtered.append(r)
                        break
            return filtered[:top_k]

        return results
    except EmbeddingError as exc:
        raise LocalRAGError(str(exc)) from exc
    except VectorStoreError as exc:
        raise LocalRAGError(str(exc)) from exc
```

**Step 5: Run tests to verify they pass**

Run: `pytest tests/test_local_rag.py -v`
Expected: All tests PASS

**Step 6: Commit**

```bash
git add app/services/local_rag.py
git commit -m "refactor: integrate HybridRetrieverService into local_rag"
```

---

### Task 3: Refresh hybrid index on PDF upload

**Files:**
- Modify: `app/services/pdf_indexing.py`
- Test: `tests/test_pdf_indexing.py`

**Step 1: Write the failing test**

Add to a new test or existing `tests/test_pdf_indexing.py`:

```python
def test_index_calls_hybrid_refresh(monkeypatch):
    from app.services.pdf_indexing import index_pdf_file
    import tempfile
    import os

    refresh_called = False

    class FakeHybridService:
        @staticmethod
        def refresh():
            nonlocal refresh_called
            refresh_called = True

    monkeypatch.setattr(
        "app.services.pdf_indexing.HybridRetrieverService",
        FakeHybridService,
    )

    # Mock the rest of the pipeline
    monkeypatch.setattr(
        "app.services.pdf_indexing.PDFLoader",
        lambda **kw: Mock(
            extract_text=lambda path: "test text",
            load_pdf=lambda path: [{"text": "test text", "source": "test.pdf", "page": 1}],
        ),
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.chunk_pdf_with_metadata",
        lambda *a, **kw: [{"text": "test chunk", "source": "test.pdf", "page": 1}],
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.EmbeddingService",
        lambda **kw: Mock(embed_texts=lambda texts: [[0.1] * 384]),
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.VectorStore",
        Mock(
            get_cached=classmethod(lambda cls, **kw: Mock(
                add_embeddings=lambda e, c: None,
                save=lambda: None,
                get_total_chunks=lambda: 1,
            ))
        ),
    )
    monkeypatch.setattr(
        "app.services.pdf_indexing.settings",
        Mock(FAISS_INDEX_PATH="/tmp/test_index"),
    )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.4 test content")
        pdf_path = f.name

    try:
        index_pdf_file(pdf_path, rebuild_index=True)
        assert refresh_called, "HybridRetrieverService.refresh() should be called"
    finally:
        os.unlink(pdf_path)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_indexing.py::test_index_calls_hybrid_refresh -v`
Expected: FAIL — pdf_indexing doesn't call refresh yet

**Step 3: Modify pdf_indexing.py**

At the end of `index_pdf_file()` function, after `vector_store.save()`, add:

```python
    # Rebuild hybrid retrieval index
    try:
        from app.services.hybrid_retriever_service import HybridRetrieverService
        HybridRetrieverService.refresh()
    except ImportError:
        pass
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_pdf_indexing.py::test_index_calls_hybrid_refresh -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/pdf_indexing.py tests/test_pdf_indexing.py
git commit -m "feat: refresh hybrid retrieval index after PDF indexing"
```

---

### Task 4: Remove rag_config switch, default to hybrid

**Files:**
- Modify: `app/services/local_rag.py`
- Remove: `data/rag_config.json` entry `use_hybrid_retrieval` (documentation)

**Step 1: Update `app/services/local_rag.py`**

Remove the `_load_rag_config()` call from `_is_hybrid_enabled()`, or simply remove the function since hybrid is always on now.

No failing test needed — existing tests already validate hybrid-first behavior.

**Step 2: Update rag_config.json if it exists**

Check if `data/rag_config.json` exists and has `use_hybrid_retrieval`. If so, remove that field (or just leave it as legacy — the new code ignores it).

**Step 3: Commit**

```bash
git add app/services/local_rag.py
git commit -m "feat: enable hybrid retrieval by default, remove config switch"
```

---

### Task 5: Run full test suite and RAGAS validation

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All tests PASS (with the new tests added)

**Step 2: Run lint/type check**

Run: `ruff check app/ tests/ && black --check app/ tests/ && mypy app/`
Expected: Clean

**Step 3: Run RAGAS baseline comparison**

Run: `python tests/test_ragas_eval.py --all --num-questions 5`
Expected: Generates new RAGAS CSV that can be compared with existing baselines in `evaluation/ragas_results_*.csv`

**Step 4: Commit**

```bash
git add -A
git commit -m "test: verify Phase 1 hybrid persistence with full test suite"
```

---

## Execution Options

Plan complete and saved to `docs/plans/2026-05-31-retrieval-quality-improvement-plan.md`. Two execution options:

1. **Subagent-Driven (this session)** — I dispatch fresh subagent per task, review between tasks, fast iteration
2. **Parallel Session (separate)** — Open new session with executing-plans, batch execution with checkpoints

Which approach?
