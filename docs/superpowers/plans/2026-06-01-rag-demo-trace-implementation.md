# RAG Demo Trace Visualization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an English-language standalone `/rag-demo` page that plays back a real RAG trace step by step for demos and project defense sessions.

**Architecture:** Add a focused backend trace builder service that reuses the current embedding, retrieval, context-building, and LLM functions, then expose it through `POST /api/rag-demo/trace`. Add focused Vue components for the demo page, with playback handled entirely on the frontend after the JSON trace returns.

**Tech Stack:** Django, pytest, Vue 3, Vite, existing Axios API helper, existing CSS design tokens.

---

## File Structure

- Create `app/services/rag_demo_trace.py`: builds presentation-friendly trace data and keeps trace formatting outside Django views.
- Create `django_app/views/rag_demo.py`: parses the HTTP request, validates input, calls the trace service, and returns JSON.
- Modify `django_app/views/__init__.py`: re-export the new view for `django_backend/urls.py`.
- Modify `django_backend/urls.py`: add `/api/rag-demo/trace` with and without trailing slash.
- Create `tests/test_rag_demo_trace_service.py`: service-level tests for trace shape, skipped generation, source filtering, and partial LLM failure.
- Create `tests/test_rag_demo_trace_view.py`: API tests for validation and service delegation.
- Modify `frontend/src/services/api.js`: add `getRagDemoTrace`.
- Create `frontend/src/components/demo/RagDemoView.vue`: owns query input, API state, playback state, replay, and Technical view.
- Create `frontend/src/components/demo/RagFlowTimeline.vue`: renders stages with completed, active, failed, and skipped states.
- Create `frontend/src/components/demo/RagStageDetail.vue`: renders the active stage explanation and technical details.
- Create `frontend/src/components/demo/RagEvidencePanel.vue`: renders retrieved chunks, context preview, and answer.
- Modify `frontend/src/components/layout/Topbar.vue`: add a topbar action that opens the demo page.
- Modify `frontend/src/App.vue`: render `RagDemoView` when the path is `/rag-demo` or when the topbar action is used.

---

### Task 1: Backend Trace Service Tests

**Files:**
- Create: `tests/test_rag_demo_trace_service.py`
- Planned create: `app/services/rag_demo_trace.py`

- [ ] **Step 1: Write failing service tests**

Create `tests/test_rag_demo_trace_service.py` with this content:

```python
import requests

import pytest


def _install_happy_path_mocks(monkeypatch: pytest.MonkeyPatch, trace_service):
    captured = {"source_filter": None, "generate_called": False}

    class FakeEmbeddingService:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def embed_query(self, query: str):
            return [0.1, 0.2, 0.3]

    class FakeVectorStore:
        chunks = [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
            },
            {
                "text": "Dense retrieval compares vector embeddings.",
                "source": "lecture-b.pdf",
                "page": 2,
            },
        ]

        def search_with_metadata(self, query_embedding, top_k: int):
            return [
                {
                    "text": "Retrieval augmented generation uses retrieved context.",
                    "source": "lecture-a.pdf",
                    "page": 1,
                    "distance": 0.2,
                },
                {
                    "text": "Dense retrieval compares vector embeddings.",
                    "source": "lecture-b.pdf",
                    "page": 2,
                    "distance": 0.8,
                },
            ][:top_k]

    monkeypatch.setattr(
        trace_service,
        "load_runtime_embedding_settings",
        lambda: {"model_id": "test-embedding", "embedding_dim": 3},
    )
    monkeypatch.setattr(
        trace_service,
        "load_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "test-llm",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )
    monkeypatch.setattr(
        trace_service.EmbeddingService,
        "__init__",
        lambda self, model_name: setattr(self, "model_name", model_name),
    )
    monkeypatch.setattr(
        trace_service.EmbeddingService,
        "embed_query",
        lambda self, query: [0.1, 0.2, 0.3],
    )
    monkeypatch.setattr(
        trace_service.VectorStore,
        "get_cached",
        lambda index_path, embedding_dim: FakeVectorStore(),
    )

    def fake_retrieve_with_faiss(query, top_k=5, source_filter=None):
        captured["source_filter"] = source_filter
        return [
            {
                "text": "Retrieval augmented generation uses retrieved context.",
                "source": "lecture-a.pdf",
                "page": 1,
                "distance": 0.2,
                "score": 0.9,
            }
        ]

    def fake_generate(
        query,
        context,
        model=None,
        temperature=0.7,
        timeout_seconds=60,
        return_log=False,
        return_thinking=False,
    ):
        captured["generate_called"] = True
        return "RAG answers by grounding generation in retrieved context."

    monkeypatch.setattr(trace_service, "retrieve_with_faiss", fake_retrieve_with_faiss)
    monkeypatch.setattr(
        trace_service,
        "build_context_from_sources",
        lambda sources: "[S1] lecture-a.pdf\nRetrieval augmented generation uses retrieved context.",
    )
    monkeypatch.setattr(trace_service, "generate", fake_generate)

    return captured


def test_build_rag_demo_trace_returns_ordered_english_stages(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="What is RAG?",
        source_filter=None,
        top_k=3,
        include_answer=True,
    )

    stage_ids = [stage["id"] for stage in trace["stages"]]
    assert stage_ids == [
        "user_question",
        "query_processing",
        "embedding_generation",
        "bm25_retrieval",
        "dense_retrieval",
        "hybrid_ranking",
        "context_building",
        "llm_generation",
        "final_answer",
    ]
    assert trace["query"] == "What is RAG?"
    assert trace["retrieved_chunks"][0]["source"] == "lecture-a.pdf"
    assert trace["context_preview"].startswith("[S1]")
    assert trace["answer"].startswith("RAG answers")
    assert all(stage["title"] for stage in trace["stages"])
    assert all(stage["summary"] for stage in trace["stages"])


def test_build_rag_demo_trace_skips_generation_when_include_answer_false(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    captured = _install_happy_path_mocks(monkeypatch, trace_service)

    trace = trace_service.build_rag_demo_trace(
        query="Explain dense retrieval",
        source_filter=None,
        top_k=2,
        include_answer=False,
    )

    llm_stage = next(stage for stage in trace["stages"] if stage["id"] == "llm_generation")
    final_stage = next(stage for stage in trace["stages"] if stage["id"] == "final_answer")
    assert llm_stage["status"] == "skipped"
    assert final_stage["status"] == "skipped"
    assert trace["answer"] == ""
    assert captured["generate_called"] is False


def test_build_rag_demo_trace_passes_source_filter_to_hybrid_retrieval(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    captured = _install_happy_path_mocks(monkeypatch, trace_service)

    trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=["lecture-a.pdf"],
        top_k=4,
        include_answer=False,
    )

    assert captured["source_filter"] == ["lecture-a.pdf"]


def test_build_rag_demo_trace_preserves_retrieval_when_llm_times_out(
    monkeypatch: pytest.MonkeyPatch,
):
    from app.services import rag_demo_trace as trace_service

    _install_happy_path_mocks(monkeypatch, trace_service)

    def timeout_generate(*args, **kwargs):
        raise requests.exceptions.Timeout("model timed out")

    monkeypatch.setattr(trace_service, "generate", timeout_generate)

    trace = trace_service.build_rag_demo_trace(
        query="Explain RAG",
        source_filter=None,
        top_k=3,
        include_answer=True,
    )

    llm_stage = next(stage for stage in trace["stages"] if stage["id"] == "llm_generation")
    final_stage = next(stage for stage in trace["stages"] if stage["id"] == "final_answer")
    assert llm_stage["status"] == "failed"
    assert "timed out" in llm_stage["summary"].lower()
    assert final_stage["status"] == "skipped"
    assert trace["retrieved_chunks"]
    assert trace["answer"] == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
pytest tests/test_rag_demo_trace_service.py -v
```

Expected: FAIL because `app.services.rag_demo_trace` does not exist.

- [ ] **Step 3: Commit the failing tests**

Run:

```bash
git add tests/test_rag_demo_trace_service.py
git commit -m "test: add rag demo trace service coverage"
```

Expected: commit succeeds with only the new test file staged.

---

### Task 2: Backend Trace Service Implementation

**Files:**
- Create: `app/services/rag_demo_trace.py`
- Test: `tests/test_rag_demo_trace_service.py`

- [ ] **Step 1: Implement the trace service**

Create `app/services/rag_demo_trace.py` with this content:

```python
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.local_rag import (
    LocalRAGError,
    build_context_from_sources,
    generate,
    retrieve_with_faiss,
)
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.runtime_llm import load_runtime_llm_settings
from app.services.vector_store import VectorStore, VectorStoreError

TraceStage = Dict[str, Any]
TracePayload = Dict[str, Any]


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _new_stage(
    stage_id: str,
    title: str,
    status: str,
    duration_ms: int,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    technical: Optional[Dict[str, Any]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None,
) -> TraceStage:
    stage: TraceStage = {
        "id": stage_id,
        "title": title,
        "status": status,
        "duration_ms": max(duration_ms, 0),
        "summary": summary,
    }
    if details is not None:
        stage["details"] = details
    if technical is not None:
        stage["technical"] = technical
    if results is not None:
        stage["results"] = results
    if error:
        stage["error"] = error
    return stage


def _clip_text(text: Any, limit: int = 320) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def _normalize_source_filter(source_filter: Any) -> Optional[List[str]]:
    if source_filter is None:
        return None
    if isinstance(source_filter, str):
        normalized = source_filter.strip()
        return [normalized] if normalized else None
    if isinstance(source_filter, list):
        values = [str(item).strip() for item in source_filter if str(item).strip()]
        return values or None
    return None


def _source_matches(source: Any, source_filter: Optional[List[str]]) -> bool:
    if not source_filter:
        return True
    normalized_source = str(source or "").lower().strip()
    for item in source_filter:
        normalized_filter = str(item).lower().strip()
        if (
            normalized_source == normalized_filter
            or normalized_source.startswith(normalized_filter)
            or normalized_filter in normalized_source
        ):
            return True
    return False


def _score_from_distance(distance: Any, max_distance: float) -> float:
    try:
        numeric_distance = float(distance)
    except (TypeError, ValueError):
        numeric_distance = max_distance
    return round(max(0.0, 1.0 - (numeric_distance / max_distance)), 3)


def _format_retrieved_chunks(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    distances = [float(item.get("distance", 0) or 0) for item in sources]
    max_distance = max(distances) if distances else 1.0
    max_distance = max(max_distance, 0.001)

    chunks: List[Dict[str, Any]] = []
    for item in sources:
        text = str(item.get("text") or "")
        distance = item.get("distance", 0)
        score = item.get("score")
        if score is None:
            score = _score_from_distance(distance, max_distance)
        chunks.append(
            {
                "text": text,
                "preview": _clip_text(text, 160),
                "score": round(float(score or 0), 3),
                "distance": round(float(distance or 0), 4),
                "source": str(item.get("source") or "unknown"),
                "page": item.get("page"),
            }
        )
    return chunks


def _build_bm25_stage(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int,
    source_filter: Optional[List[str]],
) -> TraceStage:
    started_at = time.perf_counter()
    try:
        from retrieval.bm25_index import BM25Index

        documents: List[Dict[str, str]] = []
        chunk_by_id: Dict[str, Dict[str, Any]] = {}
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                continue
            if not _source_matches(chunk.get("source"), source_filter):
                continue
            text = str(chunk.get("text") or "")
            if not text.strip():
                continue
            doc_id = f"chunk_{index}"
            documents.append({"id": doc_id, "text": text})
            chunk_by_id[doc_id] = chunk

        if not documents:
            return _new_stage(
                "bm25_retrieval",
                "BM25 Retrieval",
                "skipped",
                _duration_ms(started_at),
                "BM25 retrieval was skipped because no indexed text matched the selected sources.",
                technical={"candidate_count": 0},
                results=[],
            )

        bm25_index = BM25Index(documents)
        raw_results = bm25_index.search(query, top_k=top_k)
        results = []
        for rank, item in enumerate(raw_results, start=1):
            doc_id, score = item
            chunk = chunk_by_id.get(doc_id, {})
            results.append(
                {
                    "rank": rank,
                    "id": doc_id,
                    "score": round(float(score), 4),
                    "source": str(chunk.get("source") or "unknown"),
                    "page": chunk.get("page"),
                    "preview": _clip_text(chunk.get("text"), 160),
                }
            )

        return _new_stage(
            "bm25_retrieval",
            "BM25 Retrieval",
            "completed",
            _duration_ms(started_at),
            "Keyword retrieval finds chunks that share important words with the question.",
            technical={"candidate_count": len(documents), "top_k": top_k},
            results=results,
        )
    except Exception as exc:  # noqa: BLE001
        return _new_stage(
            "bm25_retrieval",
            "BM25 Retrieval",
            "skipped",
            _duration_ms(started_at),
            "BM25 retrieval was skipped because the keyword index could not be built.",
            technical={"reason": str(exc)},
            results=[],
        )


def _extract_answer(generation_result: Any) -> str:
    if isinstance(generation_result, tuple):
        return str(generation_result[0] or "")
    return str(generation_result or "")


def build_rag_demo_trace(
    query: str,
    source_filter: Any = None,
    top_k: int = 5,
    include_answer: bool = True,
) -> TracePayload:
    normalized_query = str(query or "").strip()
    normalized_sources = _normalize_source_filter(source_filter)
    bounded_top_k = min(max(int(top_k or 5), 1), 10)
    trace_id = f"trace_{int(time.time() * 1000)}"
    total_started_at = time.perf_counter()
    stages: List[TraceStage] = []
    retrieved_sources: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []
    context = ""
    answer = ""

    stages.append(
        _new_stage(
            "user_question",
            "User Question",
            "completed",
            0,
            "The demo starts from the user question and optional source filter.",
            details={"query": normalized_query, "sources": normalized_sources or []},
        )
    )

    query_started_at = time.perf_counter()
    tokens = normalized_query.lower().split()
    stages.append(
        _new_stage(
            "query_processing",
            "Query Processing",
            "completed",
            _duration_ms(query_started_at),
            "The question is normalized and split into searchable terms.",
            details={"processed_query": normalized_query.lower(), "tokens": tokens},
            technical={"token_count": len(tokens)},
        )
    )

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )
        chunks = vector_store.chunks if isinstance(vector_store.chunks, list) else []
        if not chunks:
            stages.append(
                _new_stage(
                    "embedding_generation",
                    "Embedding",
                    "failed",
                    0,
                    "No indexed document chunks are available. Upload and index PDFs before running the demo.",
                    error="No indexed chunks found",
                )
            )
            return {
                "trace_id": trace_id,
                "query": normalized_query,
                "stages": stages,
                "retrieved_chunks": [],
                "context_preview": "",
                "answer": "",
                "total_duration_ms": _duration_ms(total_started_at),
            }

        embedding_started_at = time.perf_counter()
        embedding_service = EmbeddingService(model_name=rt["model_id"])
        query_embedding = embedding_service.embed_query(normalized_query)
        stages.append(
            _new_stage(
                "embedding_generation",
                "Embedding",
                "completed",
                _duration_ms(embedding_started_at),
                "The question is converted into a vector so semantic matches can be found.",
                details={"model": rt["model_id"], "dimension": len(query_embedding)},
                technical={"embedding_dim": rt["embedding_dim"]},
            )
        )
    except (EmbeddingError, VectorStoreError, LocalRAGError, ValueError) as exc:
        stages.append(
            _new_stage(
                "embedding_generation",
                "Embedding",
                "failed",
                0,
                "The system could not generate the query embedding.",
                error=str(exc),
            )
        )
        return {
            "trace_id": trace_id,
            "query": normalized_query,
            "stages": stages,
            "retrieved_chunks": [],
            "context_preview": "",
            "answer": "",
            "total_duration_ms": _duration_ms(total_started_at),
        }

    stages.append(
        _build_bm25_stage(
            query=normalized_query,
            chunks=chunks,
            top_k=bounded_top_k,
            source_filter=normalized_sources,
        )
    )

    dense_started_at = time.perf_counter()
    search_k = bounded_top_k * 10 if normalized_sources else bounded_top_k
    dense_results = vector_store.search_with_metadata(query_embedding, top_k=search_k)
    if normalized_sources:
        dense_results = [
            item
            for item in dense_results
            if _source_matches(item.get("source"), normalized_sources)
        ][:bounded_top_k]
    distances = [float(item.get("distance", 0) or 0) for item in dense_results]
    max_distance = max(max(distances) if distances else 1.0, 0.001)
    stages.append(
        _new_stage(
            "dense_retrieval",
            "Dense Retrieval",
            "completed",
            _duration_ms(dense_started_at),
            "Vector retrieval finds chunks that are semantically close to the question.",
            technical={"top_k": bounded_top_k, "searched_k": search_k},
            results=[
                {
                    "rank": rank,
                    "source": str(item.get("source") or "unknown"),
                    "page": item.get("page"),
                    "score": _score_from_distance(item.get("distance"), max_distance),
                    "distance": round(float(item.get("distance", 0) or 0), 4),
                    "preview": _clip_text(item.get("text"), 160),
                }
                for rank, item in enumerate(dense_results[:bounded_top_k], start=1)
            ],
        )
    )

    hybrid_started_at = time.perf_counter()
    try:
        retrieved_sources = retrieve_with_faiss(
            query=normalized_query,
            top_k=bounded_top_k,
            source_filter=normalized_sources,
        )
        retrieved_chunks = _format_retrieved_chunks(retrieved_sources)
        stages.append(
            _new_stage(
                "hybrid_ranking",
                "Hybrid Ranking",
                "completed",
                _duration_ms(hybrid_started_at),
                "The system combines keyword and semantic signals to choose the strongest evidence.",
                technical={"top_k": bounded_top_k, "source_filter": normalized_sources or []},
                results=[
                    {
                        "rank": rank,
                        "source": chunk["source"],
                        "page": chunk["page"],
                        "score": chunk["score"],
                        "distance": chunk["distance"],
                        "preview": chunk["preview"],
                    }
                    for rank, chunk in enumerate(retrieved_chunks, start=1)
                ],
            )
        )
    except LocalRAGError as exc:
        stages.append(
            _new_stage(
                "hybrid_ranking",
                "Hybrid Ranking",
                "failed",
                _duration_ms(hybrid_started_at),
                "Hybrid retrieval could not return evidence for this question.",
                error=str(exc),
            )
        )
        return {
            "trace_id": trace_id,
            "query": normalized_query,
            "stages": stages,
            "retrieved_chunks": [],
            "context_preview": "",
            "answer": "",
            "total_duration_ms": _duration_ms(total_started_at),
        }

    context_started_at = time.perf_counter()
    context = build_context_from_sources(retrieved_sources)
    context_status = "completed" if context.strip() else "failed"
    context_summary = (
        "The selected chunks are formatted into a context block for the language model."
        if context.strip()
        else "No usable context was built from the retrieved chunks."
    )
    stages.append(
        _new_stage(
            "context_building",
            "Context Building",
            context_status,
            _duration_ms(context_started_at),
            context_summary,
            details={"context_preview": _clip_text(context, 500)},
            technical={"context_length": len(context), "chunks_used": len(retrieved_sources)},
        )
    )

    if include_answer and context.strip():
        llm_started_at = time.perf_counter()
        runtime_llm = load_runtime_llm_settings()
        try:
            generation_result = generate(
                query=normalized_query,
                context=context,
                timeout_seconds=20,
            )
            answer = _extract_answer(generation_result)
            stages.append(
                _new_stage(
                    "llm_generation",
                    "LLM Generation",
                    "completed",
                    _duration_ms(llm_started_at),
                    "The language model writes an answer grounded in the retrieved context.",
                    details={"provider": runtime_llm["provider"], "model": runtime_llm["model"]},
                    technical={"answer_length": len(answer)},
                )
            )
        except requests.exceptions.Timeout as exc:
            stages.append(
                _new_stage(
                    "llm_generation",
                    "LLM Generation",
                    "failed",
                    _duration_ms(llm_started_at),
                    "LLM generation timed out after retrieval and context building completed.",
                    details={"provider": runtime_llm["provider"], "model": runtime_llm["model"]},
                    error=str(exc),
                )
            )
        except (requests.exceptions.RequestException, LocalRAGError, ValueError) as exc:
            stages.append(
                _new_stage(
                    "llm_generation",
                    "LLM Generation",
                    "failed",
                    _duration_ms(llm_started_at),
                    "LLM generation failed after retrieval and context building completed.",
                    details={"provider": runtime_llm["provider"], "model": runtime_llm["model"]},
                    error=str(exc),
                )
            )
    else:
        stages.append(
            _new_stage(
                "llm_generation",
                "LLM Generation",
                "skipped",
                0,
                "LLM generation was skipped for this trace request.",
                technical={"include_answer": include_answer, "has_context": bool(context.strip())},
            )
        )

    final_status = "completed" if answer else "skipped"
    final_summary = (
        "The final answer is ready and can be shown with the supporting evidence."
        if answer
        else "No final answer was produced for this trace."
    )
    stages.append(
        _new_stage(
            "final_answer",
            "Final Answer",
            final_status,
            0,
            final_summary,
            details={"answer": answer, "source_count": len(retrieved_chunks)},
        )
    )

    return {
        "trace_id": trace_id,
        "query": normalized_query,
        "stages": stages,
        "retrieved_chunks": retrieved_chunks,
        "context_preview": _clip_text(context, 800),
        "answer": answer,
        "total_duration_ms": _duration_ms(total_started_at),
    }


__all__ = ["build_rag_demo_trace"]
```

- [ ] **Step 2: Run service tests**

Run:

```bash
pytest tests/test_rag_demo_trace_service.py -v
```

Expected: PASS.

- [ ] **Step 3: Commit service implementation**

Run:

```bash
git add app/services/rag_demo_trace.py tests/test_rag_demo_trace_service.py
git commit -m "feat: add rag demo trace service"
```

Expected: commit succeeds.

---

### Task 3: Backend API Endpoint

**Files:**
- Create: `tests/test_rag_demo_trace_view.py`
- Create: `django_app/views/rag_demo.py`
- Modify: `django_app/views/__init__.py`
- Modify: `django_backend/urls.py`

- [ ] **Step 1: Write failing API tests**

Create `tests/test_rag_demo_trace_view.py` with this content:

```python
import os

import django
import pytest
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_rag_demo_trace_rejects_empty_query(client: Client):
    response = client.post(
        "/api/rag-demo/trace",
        data='{"query": "   "}',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"


def test_rag_demo_trace_returns_service_payload(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    def fake_build_rag_demo_trace(query, source_filter=None, top_k=5, include_answer=True):
        captured["query"] = query
        captured["source_filter"] = source_filter
        captured["top_k"] = top_k
        captured["include_answer"] = include_answer
        return {
            "trace_id": "trace_test",
            "query": query,
            "stages": [
                {
                    "id": "user_question",
                    "title": "User Question",
                    "status": "completed",
                    "duration_ms": 0,
                    "summary": "The demo starts from the user question.",
                }
            ],
            "retrieved_chunks": [],
            "context_preview": "",
            "answer": "",
            "total_duration_ms": 1,
        }

    monkeypatch.setattr(
        "django_app.views.rag_demo.build_rag_demo_trace",
        fake_build_rag_demo_trace,
    )

    response = client.post(
        "/api/rag-demo/trace",
        data='{"query": "Explain RAG", "sources": ["lecture.pdf"], "top_k": 4, "include_answer": false}',
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace_test"
    assert captured == {
        "query": "Explain RAG",
        "source_filter": ["lecture.pdf"],
        "top_k": 4,
        "include_answer": False,
    }
```

- [ ] **Step 2: Run API tests to verify they fail**

Run:

```bash
pytest tests/test_rag_demo_trace_view.py -v
```

Expected: FAIL because `/api/rag-demo/trace` is not routed.

- [ ] **Step 3: Add the Django view**

Create `django_app/views/rag_demo.py` with this content:

```python
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.services.local_rag import LocalRAGError
from app.services.rag_demo_trace import build_rag_demo_trace

from django_app.views.helpers import _error_response, _get_json_body


@csrf_exempt
@require_http_methods(["POST"])
def rag_demo_trace(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or payload.get("question") or "").strip()
    if not query:
        return _error_response("Query cannot be empty", status=400)

    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    try:
        top_k = int(payload.get("top_k", 5))
    except (TypeError, ValueError):
        top_k = 5
    top_k = min(max(top_k, 1), 10)

    include_answer = bool(payload.get("include_answer", True))

    try:
        trace = build_rag_demo_trace(
            query=query,
            source_filter=source_filter,
            top_k=top_k,
            include_answer=include_answer,
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to build RAG demo trace: {str(exc)}", status=500)

    return JsonResponse(trace)


__all__ = ["rag_demo_trace"]
```

- [ ] **Step 4: Re-export the view**

Modify `django_app/views/__init__.py`.

Add this import after the RAG / Chat import block:

```python
from django_app.views.rag_demo import rag_demo_trace
```

Add this string to `__all__` in the RAG / Chat section:

```python
"rag_demo_trace",
```

- [ ] **Step 5: Add URL routes**

Modify `django_backend/urls.py`.

Add these routes after the existing `/api/chat` routes:

```python
path("api/rag-demo/trace", views.rag_demo_trace),
path("api/rag-demo/trace/", views.rag_demo_trace),
```

- [ ] **Step 6: Run API tests**

Run:

```bash
pytest tests/test_rag_demo_trace_view.py -v
```

Expected: PASS.

- [ ] **Step 7: Run backend trace tests together**

Run:

```bash
pytest tests/test_rag_demo_trace_service.py tests/test_rag_demo_trace_view.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit API endpoint**

Run:

```bash
git add django_app/views/rag_demo.py django_app/views/__init__.py django_backend/urls.py tests/test_rag_demo_trace_view.py
git commit -m "feat: expose rag demo trace api"
```

Expected: commit succeeds.

---

### Task 4: Frontend Demo Components

**Files:**
- Modify: `frontend/src/services/api.js`
- Create: `frontend/src/components/demo/RagFlowTimeline.vue`
- Create: `frontend/src/components/demo/RagStageDetail.vue`
- Create: `frontend/src/components/demo/RagEvidencePanel.vue`
- Create: `frontend/src/components/demo/RagDemoView.vue`

- [ ] **Step 1: Add frontend API helper**

Modify `frontend/src/services/api.js`.

Add this export near the chat API functions:

```javascript
export const getRagDemoTrace = async (payload) => {
  const response = await api.post('/rag-demo/trace', payload)
  return response.data
}
```

- [ ] **Step 2: Create timeline component**

Create `frontend/src/components/demo/RagFlowTimeline.vue` with this content:

```vue
<script setup>
defineProps({
  stages: {
    type: Array,
    default: () => [],
  },
  activeStageId: {
    type: String,
    default: '',
  },
})

defineEmits(['select-stage'])
</script>

<template>
  <aside class="rag-flow-timeline" aria-label="RAG flow timeline">
    <div class="timeline-header">
      <span class="eyebrow">Flow</span>
      <h2>RAG Pipeline</h2>
    </div>

    <button
      v-for="(stage, index) in stages"
      :key="stage.id"
      type="button"
      class="timeline-item"
      :class="[stage.status, { active: stage.id === activeStageId }]"
      @click="$emit('select-stage', index)"
    >
      <span class="stage-index">{{ index + 1 }}</span>
      <span class="stage-copy">
        <span class="stage-title">{{ stage.title }}</span>
        <span class="stage-status">{{ stage.status }}</span>
      </span>
      <span class="stage-time">{{ stage.duration_ms }}ms</span>
    </button>
  </aside>
</template>

<style scoped>
.rag-flow-timeline {
  min-width: 240px;
  padding: 18px;
  background: var(--surface-container-low);
  border-right: 1px solid rgba(69, 70, 83, 0.2);
  overflow-y: auto;
}

.timeline-header {
  margin-bottom: 16px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.timeline-header h2 {
  margin: 0;
  font-size: 18px;
  color: var(--on-surface);
}

.timeline-item {
  width: 100%;
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: 8px;
  background: transparent;
  color: var(--on-surface-variant);
  text-align: left;
}

.timeline-item:hover,
.timeline-item.active {
  background: rgba(129, 140, 248, 0.12);
  color: var(--on-surface);
  border-color: rgba(129, 140, 248, 0.35);
}

.timeline-item.failed {
  border-color: rgba(248, 113, 113, 0.4);
}

.timeline-item.skipped {
  opacity: 0.78;
}

.stage-index {
  width: 26px;
  height: 26px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface-container);
  font-size: 12px;
  font-weight: 700;
}

.timeline-item.completed .stage-index {
  background: rgba(34, 197, 94, 0.16);
  color: #86efac;
}

.timeline-item.failed .stage-index {
  background: rgba(239, 68, 68, 0.16);
  color: #fca5a5;
}

.stage-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.stage-title {
  font-size: 13px;
  font-weight: 700;
  color: inherit;
}

.stage-status,
.stage-time {
  font-size: 11px;
  color: var(--on-surface-variant);
  text-transform: capitalize;
}
</style>
```

- [ ] **Step 3: Create active stage detail component**

Create `frontend/src/components/demo/RagStageDetail.vue` with this content:

```vue
<script setup>
import { computed } from 'vue'

const props = defineProps({
  stage: {
    type: Object,
    default: null,
  },
  technicalView: {
    type: Boolean,
    default: false,
  },
})

const details = computed(() => props.stage?.details || {})
const technical = computed(() => props.stage?.technical || {})
const results = computed(() => props.stage?.results || [])

const formatJson = (value) => JSON.stringify(value, null, 2)
</script>

<template>
  <section class="stage-detail" aria-live="polite">
    <div v-if="!stage" class="empty-state">
      <span class="eyebrow">Ready</span>
      <h2>Run a demo trace</h2>
      <p>Enter a question to show how retrieval and generation work together.</p>
    </div>

    <template v-else>
      <div class="stage-heading">
        <span class="eyebrow">{{ stage.status }}</span>
        <h2>{{ stage.title }}</h2>
        <p>{{ stage.summary }}</p>
      </div>

      <div v-if="Object.keys(details).length" class="detail-block">
        <h3>What happened</h3>
        <pre>{{ formatJson(details) }}</pre>
      </div>

      <div v-if="results.length" class="result-list">
        <h3>Stage Results</h3>
        <div v-for="item in results" :key="`${stage.id}-${item.rank || item.id || item.source}`" class="result-item">
          <div class="result-meta">
            <span v-if="item.rank">Rank {{ item.rank }}</span>
            <span v-if="item.source">{{ item.source }}</span>
            <span v-if="item.page">Page {{ item.page }}</span>
            <span v-if="item.score !== undefined">Score {{ item.score }}</span>
          </div>
          <p>{{ item.preview || item.text || item.id }}</p>
        </div>
      </div>

      <div v-if="technicalView && Object.keys(technical).length" class="detail-block technical-block">
        <h3>Technical Data</h3>
        <pre>{{ formatJson(technical) }}</pre>
      </div>

      <div v-if="stage.error" class="error-block">
        <h3>Error</h3>
        <p>{{ stage.error }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.stage-detail {
  min-width: 0;
  padding: 24px;
  overflow-y: auto;
}

.empty-state,
.stage-heading,
.detail-block,
.result-list,
.error-block {
  margin-bottom: 18px;
}

.eyebrow {
  display: block;
  margin-bottom: 6px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

h2,
h3,
p {
  margin: 0;
}

h2 {
  margin-bottom: 8px;
  font-size: 28px;
  color: var(--on-surface);
}

h3 {
  margin-bottom: 10px;
  font-size: 14px;
  color: var(--on-surface);
}

p {
  color: var(--on-surface-variant);
  line-height: 1.6;
}

pre {
  margin: 0;
  padding: 14px;
  border-radius: 8px;
  background: var(--surface-container-lowest);
  color: var(--on-surface);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}

.result-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.result-item {
  padding: 12px;
  border-radius: 8px;
  background: var(--surface-container-low);
  border: 1px solid rgba(69, 70, 83, 0.22);
}

.result-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
}

.technical-block pre {
  border: 1px solid rgba(129, 140, 248, 0.24);
}

.error-block {
  padding: 14px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  border: 1px solid rgba(239, 68, 68, 0.28);
}
</style>
```

- [ ] **Step 4: Create evidence panel component**

Create `frontend/src/components/demo/RagEvidencePanel.vue` with this content:

```vue
<script setup>
defineProps({
  chunks: {
    type: Array,
    default: () => [],
  },
  contextPreview: {
    type: String,
    default: '',
  },
  answer: {
    type: String,
    default: '',
  },
  technicalView: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <aside class="evidence-panel" aria-label="Evidence panel">
    <section class="panel-section">
      <span class="eyebrow">Evidence</span>
      <h2>Retrieved Chunks</h2>
      <p v-if="chunks.length === 0" class="muted">No chunks retrieved yet.</p>

      <div v-for="(chunk, index) in chunks" :key="`${chunk.source}-${chunk.page}-${index}`" class="chunk-card">
        <div class="chunk-meta">
          <span>#{{ index + 1 }}</span>
          <span>{{ chunk.source }}</span>
          <span v-if="chunk.page">Page {{ chunk.page }}</span>
        </div>
        <p>{{ chunk.preview || chunk.text }}</p>
        <div v-if="technicalView" class="technical-row">
          <span>Score {{ chunk.score }}</span>
          <span>Distance {{ chunk.distance }}</span>
        </div>
      </div>
    </section>

    <section class="panel-section">
      <span class="eyebrow">Context</span>
      <h2>Prompt Context</h2>
      <pre>{{ contextPreview || 'Context will appear after retrieval completes.' }}</pre>
    </section>

    <section class="panel-section">
      <span class="eyebrow">Answer</span>
      <h2>Final Answer</h2>
      <p class="answer-text">{{ answer || 'The answer will appear after generation completes.' }}</p>
    </section>
  </aside>
</template>

<style scoped>
.evidence-panel {
  min-width: 300px;
  max-width: 360px;
  padding: 18px;
  background: var(--surface-container-low);
  border-left: 1px solid rgba(69, 70, 83, 0.2);
  overflow-y: auto;
}

.panel-section {
  margin-bottom: 22px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

h2,
p {
  margin: 0;
}

h2 {
  margin-bottom: 10px;
  font-size: 15px;
  color: var(--on-surface);
}

.muted,
.answer-text,
.chunk-card p {
  color: var(--on-surface-variant);
  font-size: 13px;
  line-height: 1.6;
}

.chunk-card {
  margin-bottom: 10px;
  padding: 12px;
  border-radius: 8px;
  background: var(--surface-container);
  border: 1px solid rgba(69, 70, 83, 0.24);
}

.chunk-meta,
.technical-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 8px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
}

.technical-row {
  margin-top: 10px;
  margin-bottom: 0;
  color: var(--tertiary);
}

pre {
  margin: 0;
  max-height: 220px;
  overflow-y: auto;
  padding: 12px;
  border-radius: 8px;
  background: var(--surface-container-lowest);
  color: var(--on-surface-variant);
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}
</style>
```

- [ ] **Step 5: Create main demo view**

Create `frontend/src/components/demo/RagDemoView.vue` with this content:

```vue
<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { getRagDemoTrace } from '../../services/api'
import RagEvidencePanel from './RagEvidencePanel.vue'
import RagFlowTimeline from './RagFlowTimeline.vue'
import RagStageDetail from './RagStageDetail.vue'

defineEmits(['close'])

const query = ref('What is retrieval augmented generation?')
const trace = ref(null)
const activeIndex = ref(0)
const isLoading = ref(false)
const isPlaying = ref(false)
const technicalView = ref(false)
const error = ref('')
const timers = []

const stages = computed(() => trace.value?.stages || [])
const activeStage = computed(() => stages.value[activeIndex.value] || null)
const activeStageId = computed(() => activeStage.value?.id || '')

const clearTimers = () => {
  while (timers.length) {
    clearTimeout(timers.pop())
  }
}

const stageDelay = (stage) => {
  const realDuration = Number(stage?.duration_ms || 0)
  return Math.min(Math.max(realDuration, 900), 1800)
}

const playTrace = () => {
  clearTimers()
  if (!stages.value.length) return
  activeIndex.value = 0
  isPlaying.value = true

  const scheduleNext = (index) => {
    if (index >= stages.value.length - 1) {
      isPlaying.value = false
      return
    }
    const timer = setTimeout(() => {
      activeIndex.value = index + 1
      scheduleNext(index + 1)
    }, stageDelay(stages.value[index]))
    timers.push(timer)
  }

  scheduleNext(0)
}

const runDemo = async () => {
  const trimmedQuery = query.value.trim()
  if (!trimmedQuery) {
    error.value = 'Enter a question to run the demo.'
    return
  }

  clearTimers()
  isLoading.value = true
  isPlaying.value = false
  error.value = ''

  try {
    trace.value = await getRagDemoTrace({
      query: trimmedQuery,
      top_k: 5,
      include_answer: true,
    })
    playTrace()
  } catch (err) {
    error.value = err.response?.data?.detail || err.message || 'Failed to run RAG demo.'
  } finally {
    isLoading.value = false
  }
}

const replay = () => {
  if (trace.value) {
    playTrace()
  }
}

const selectStage = (index) => {
  clearTimers()
  isPlaying.value = false
  activeIndex.value = index
}

onBeforeUnmount(() => {
  clearTimers()
})
</script>

<template>
  <section class="rag-demo-view">
    <header class="demo-header">
      <div>
        <span class="eyebrow">Live Demo</span>
        <h1>RAG Trace Visualization</h1>
        <p>Show how a lecture-note question moves through retrieval, context building, and answer generation.</p>
      </div>
      <button type="button" class="secondary-btn" @click="$emit('close')">Back to Workspace</button>
    </header>

    <div class="demo-controls">
      <label class="query-field">
        <span>Question</span>
        <input v-model="query" type="text" :disabled="isLoading" @keyup.enter="runDemo">
      </label>
      <button type="button" class="primary-btn" :disabled="isLoading" @click="runDemo">
        {{ isLoading ? 'Running' : 'Run Demo' }}
      </button>
      <button type="button" class="secondary-btn" :disabled="!trace || isLoading" @click="replay">
        {{ isPlaying ? 'Playing' : 'Replay' }}
      </button>
      <label class="toggle-field">
        <input v-model="technicalView" type="checkbox">
        <span>Technical view</span>
      </label>
    </div>

    <div v-if="error" class="demo-error" role="alert">{{ error }}</div>

    <div class="demo-body">
      <RagFlowTimeline
        :stages="stages"
        :active-stage-id="activeStageId"
        @select-stage="selectStage"
      />
      <RagStageDetail
        :stage="activeStage"
        :technical-view="technicalView"
      />
      <RagEvidencePanel
        :chunks="trace?.retrieved_chunks || []"
        :context-preview="trace?.context_preview || ''"
        :answer="trace?.answer || ''"
        :technical-view="technicalView"
      />
    </div>
  </section>
</template>

<style scoped>
.rag-demo-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  background: var(--surface);
}

.demo-header,
.demo-controls {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 18px 22px;
  border-bottom: 1px solid rgba(69, 70, 83, 0.18);
  background: var(--surface-container-low);
}

.demo-header h1,
.demo-header p {
  margin: 0;
}

.demo-header h1 {
  margin-bottom: 4px;
  font-size: 24px;
  color: var(--on-surface);
}

.demo-header p {
  color: var(--on-surface-variant);
  font-size: 13px;
}

.eyebrow {
  display: block;
  margin-bottom: 4px;
  color: var(--primary);
  font-size: 11px;
  font-weight: 700;
  text-transform: uppercase;
}

.demo-controls {
  justify-content: flex-start;
  flex-wrap: wrap;
  background: var(--surface-container-lowest);
}

.query-field {
  flex: 1;
  min-width: 280px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  color: var(--on-surface-variant);
  font-size: 12px;
  font-weight: 700;
}

.query-field input {
  width: 100%;
  height: 40px;
  border-radius: 8px;
  border: 1px solid rgba(69, 70, 83, 0.4);
  background: var(--surface-container);
  color: var(--on-surface);
  padding: 0 12px;
  font-size: 14px;
}

.primary-btn,
.secondary-btn {
  height: 40px;
  padding: 0 14px;
  border-radius: 8px;
  border: 1px solid transparent;
  font-weight: 700;
}

.primary-btn {
  background: var(--primary-container);
  color: var(--on-primary);
}

.secondary-btn {
  background: var(--surface-container);
  color: var(--on-surface);
  border-color: rgba(69, 70, 83, 0.4);
}

.primary-btn:disabled,
.secondary-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.toggle-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--on-surface-variant);
  font-size: 13px;
  font-weight: 700;
}

.demo-error {
  margin: 12px 22px 0;
  padding: 10px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.12);
  color: #fca5a5;
  border: 1px solid rgba(239, 68, 68, 0.28);
  font-size: 13px;
}

.demo-body {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 340px;
}

@media (max-width: 1100px) {
  .demo-body {
    grid-template-columns: 1fr;
  }
}
</style>
```

- [ ] **Step 6: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS, Vite writes assets to `django_app/static/frontend`.

- [ ] **Step 7: Commit frontend components**

Run:

```bash
git add frontend/src/services/api.js frontend/src/components/demo/RagDemoView.vue frontend/src/components/demo/RagFlowTimeline.vue frontend/src/components/demo/RagStageDetail.vue frontend/src/components/demo/RagEvidencePanel.vue django_app/static/frontend
git commit -m "feat: add rag demo frontend components"
```

Expected: commit succeeds.

---

### Task 5: App Navigation and Standalone Route

**Files:**
- Modify: `frontend/src/components/layout/Topbar.vue`
- Modify: `frontend/src/App.vue`

- [ ] **Step 1: Wire topbar event**

Modify `frontend/src/components/layout/Topbar.vue`.

Change the emit declaration to:

```javascript
const emit = defineEmits(['open-admin', 'open-chunkviz', 'open-llm-config', 'open-rag-demo'])
```

Add this button before the model configuration button:

```vue
<button
  type="button"
  class="icon-btn"
  aria-label="RAG demo"
  title="RAG demo"
  @click="emit('open-rag-demo')"
>
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M4 5h16v2H4V5zm0 6h10v2H4v-2zm0 6h16v2H4v-2zm13.5-7.5L22 12l-4.5 2.5v-5z"/>
  </svg>
</button>
```

- [ ] **Step 2: Wire app-level route state**

Modify `frontend/src/App.vue`.

Add this import:

```javascript
import RagDemoView from './components/demo/RagDemoView.vue'
```

Change the Vue import to include `onBeforeUnmount`:

```javascript
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
```

Add this state and functions after the existing refs:

```javascript
const showRagDemo = ref(window.location.pathname === '/rag-demo')

const syncRouteState = () => {
  showRagDemo.value = window.location.pathname === '/rag-demo'
}

const handleOpenRagDemo = () => {
  showRagDemo.value = true
  window.history.pushState({}, '', '/rag-demo')
}

const handleCloseRagDemo = () => {
  showRagDemo.value = false
  window.history.pushState({}, '', '/')
}
```

Update `onMounted` to register popstate:

```javascript
onMounted(() => {
  llmStore.loadProviders()
  window.addEventListener('popstate', syncRouteState)
})

onBeforeUnmount(() => {
  window.removeEventListener('popstate', syncRouteState)
})
```

Add the event to `<Topbar>`:

```vue
@open-rag-demo="handleOpenRagDemo"
```

Render the demo view before the normal main workspace:

```vue
<RagDemoView
  v-if="showRagDemo"
  @close="handleCloseRagDemo"
/>
<main v-else-if="!showLLMConfig" id="main-content" class="main" tabindex="-1">
```

Keep the existing `LLMConfigPanel` branch as:

```vue
<LLMConfigPanel
  v-if="showLLMConfig"
  @close="showLLMConfig = false"
/>
```

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Commit navigation wiring**

Run:

```bash
git add frontend/src/App.vue frontend/src/components/layout/Topbar.vue django_app/static/frontend
git commit -m "feat: expose rag demo page"
```

Expected: commit succeeds.

---

### Task 6: Final Verification

**Files:**
- Verify all files touched by Tasks 1 through 5.

- [ ] **Step 1: Run backend tests for the new feature**

Run:

```bash
pytest tests/test_rag_demo_trace_service.py tests/test_rag_demo_trace_view.py -v
```

Expected: PASS.

- [ ] **Step 2: Run focused regression tests around chat and admin trace**

Run:

```bash
pytest tests/test_django_ask_view.py tests/test_backend_regressions.py -v
```

Expected: PASS.

- [ ] **Step 3: Run frontend build**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

- [ ] **Step 4: Check git status**

Run:

```bash
git status --short
```

Expected: no unstaged changes from the implementation except known generated files that were committed in the frontend build tasks.

- [ ] **Step 5: Manual browser smoke test**

Start Django and Vite in the normal development setup:

```bash
python manage.py runserver 0.0.0.0:8000
```

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173/rag-demo`.

Expected:

- The page title is `RAG Trace Visualization`.
- The page text is English.
- `Run Demo` calls `/api/rag-demo/trace`.
- The timeline advances through the stages.
- `Replay` replays the same trace without another API call.
- `Technical view` reveals scores, distances, timings, and metadata.

- [ ] **Step 6: Final commit if verification changed built assets**

If `npm run build` changed files under `django_app/static/frontend`, run:

```bash
git add django_app/static/frontend
git commit -m "build: update frontend assets for rag demo"
```

Expected: commit succeeds only when generated assets changed after the earlier frontend commits.

---

## Self-Review Checklist

- Spec coverage: The plan includes the standalone `/rag-demo` page, English UI text, complete stage list, replay, Technical view, backend trace API, partial LLM failure, skipped generation, and frontend build verification.
- Scope: The plan does not add SSE, WebSocket streaming, new retrieval algorithms, or changes to the existing chat workflow.
- Type consistency: The backend uses `source_filter`, `top_k`, `include_answer`, `stages`, `retrieved_chunks`, `context_preview`, and `answer` consistently across tests, service, view, and frontend.
- Verification: Backend pytest commands and frontend Vite build commands are listed with expected outcomes.
