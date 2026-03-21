import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse

from app.config import settings

SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "settings.json"
RAG_CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "rag_config.json"
VALID_PROVIDERS = {"gemini", "openrouter"}
LOCAL_QWEN_MODELS = [
    "qwen2.5:0.5b",
    "qwen2.5:1.5b",
    "qwen2.5:3b",
    "qwen2.5:7b",
    "qwen2.5:14b",
]
INDEXING_STRATEGY_FULL_REBUILD = "full_rebuild"
INDEXING_STRATEGY_APPEND = "append"
VALID_INDEXING_STRATEGIES = {
    INDEXING_STRATEGY_FULL_REBUILD,
    INDEXING_STRATEGY_APPEND,
}
INDEXING_STATUS_IDLE = "idle"
INDEXING_STATUS_QUEUED = "queued"
INDEXING_STATUS_RUNNING = "running"
INDEXING_STATUS_COMPLETED = "completed"
INDEXING_STATUS_FAILED = "failed"
_INDEXING_STATE_LOCK = threading.Lock()
_INDEXING_WORKER_THREAD: Optional[threading.Thread] = None
_INDEXING_RERUN_REQUESTED = False
_INDEXING_STATE: Dict[str, Any] = {
    "status": INDEXING_STATUS_IDLE,
    "strategy": INDEXING_STRATEGY_FULL_REBUILD,
    "is_async": bool(settings.UPLOAD_INDEXING_ASYNC),
    "pending_requests": 0,
    "last_uploaded_filename": None,
    "last_started_at": None,
    "last_completed_at": None,
    "last_error": None,
    "last_stats": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _resolve_upload_indexing_strategy() -> str:
    strategy = str(settings.UPLOAD_INDEXING_STRATEGY).strip().lower()
    if strategy in VALID_INDEXING_STRATEGIES:
        return strategy
    return INDEXING_STRATEGY_FULL_REBUILD


def _get_upload_indexing_state() -> Dict[str, Any]:
    with _INDEXING_STATE_LOCK:
        return dict(_INDEXING_STATE)


def _enqueue_full_rebuild(uploaded_filename: str) -> Dict[str, Any]:
    global _INDEXING_WORKER_THREAD
    global _INDEXING_RERUN_REQUESTED

    should_start_worker = False
    with _INDEXING_STATE_LOCK:
        _INDEXING_RERUN_REQUESTED = True
        _INDEXING_STATE["status"] = INDEXING_STATUS_QUEUED
        _INDEXING_STATE["strategy"] = INDEXING_STRATEGY_FULL_REBUILD
        _INDEXING_STATE["is_async"] = True
        _INDEXING_STATE["pending_requests"] = (
            int(_INDEXING_STATE.get("pending_requests", 0)) + 1
        )
        _INDEXING_STATE["last_uploaded_filename"] = uploaded_filename
        _INDEXING_STATE["last_error"] = None

        if _INDEXING_WORKER_THREAD is None or not _INDEXING_WORKER_THREAD.is_alive():

            _INDEXING_WORKER_THREAD = threading.Thread(
                target=_full_rebuild_worker,
                daemon=True,
                name="full-rebuild-index-worker",
            )
            should_start_worker = True

    if should_start_worker:
        _INDEXING_WORKER_THREAD.start()

    return _get_upload_indexing_state()


def _full_rebuild_worker() -> None:
    global _INDEXING_RERUN_REQUESTED

    from app.services.pdf_indexing import index_pdf_directory

    while True:
        with _INDEXING_STATE_LOCK:
            if not _INDEXING_RERUN_REQUESTED:
                return

            _INDEXING_RERUN_REQUESTED = False
            _INDEXING_STATE["status"] = INDEXING_STATUS_RUNNING
            _INDEXING_STATE["pending_requests"] = 0
            _INDEXING_STATE["last_started_at"] = _utc_now_iso()
            _INDEXING_STATE["last_error"] = None

        try:
            index_stats = index_pdf_directory(
                data_source_dir=settings.DOCUMENTS_PATH,
                chunk_size=settings.CHUNK_SIZE,
                index_path=settings.FAISS_INDEX_PATH,
                model_name=settings.EMBEDDING_MODEL,
                clear_existing=True,
            )
            with _INDEXING_STATE_LOCK:
                _INDEXING_STATE["status"] = INDEXING_STATUS_COMPLETED
                _INDEXING_STATE["last_completed_at"] = _utc_now_iso()
                _INDEXING_STATE["last_stats"] = index_stats
                _INDEXING_STATE["last_error"] = None
        except Exception as exc:  # noqa: BLE001
            with _INDEXING_STATE_LOCK:
                _INDEXING_STATE["status"] = INDEXING_STATUS_FAILED
                _INDEXING_STATE["last_completed_at"] = _utc_now_iso()
                _INDEXING_STATE["last_error"] = str(exc)

        with _INDEXING_STATE_LOCK:
            should_rerun = bool(_INDEXING_RERUN_REQUESTED)
            if should_rerun:
                _INDEXING_STATE["status"] = INDEXING_STATUS_QUEUED

        if not should_rerun:
            return


def _error_response(detail: str, status: int) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status)


def _build_source_snippets(sources: Any) -> List[Dict[str, Any]]:
    snippets: List[Dict[str, Any]] = []
    if not isinstance(sources, list):
        return snippets

    for item in sources:
        if not isinstance(item, dict):
            continue
        snippets.append(
            {
                "source": str(item.get("source") or "unknown"),
                "page": item.get("page"),
                "text": str(item.get("text") or ""),
                "distance": item.get("distance"),
            }
        )
    return snippets


def _build_retrieved_chunks(sources: Any) -> List[Dict[str, Any]]:
    """Build retrieved chunks with similarity scores for visualization."""
    chunks: List[Dict[str, Any]] = []
    if not isinstance(sources, list):
        return chunks

    distances = [r.get("distance", 0) for r in sources if isinstance(r, dict)]
    max_distance = max(distances) if distances else 1.0
    max_distance = max(max_distance, 0.001)

    for r in sources:
        if not isinstance(r, dict):
            continue

        distance = r.get("distance", 0)
        similarity = max(0.0, 1.0 - (distance / max_distance))
        text = r.get("text", "")

        chunks.append(
            {
                "text": text,
                "preview": text[:100] + ("..." if len(text) > 100 else ""),
                "score": round(similarity, 3),
                "distance": round(distance, 4),
                "source": str(r.get("source", "unknown")),
                "page": r.get("page"),
            }
        )

    return chunks


def _get_json_body(request: HttpRequest) -> Dict[str, Any]:
    if not request.body:
        return {}

    try:
        parsed = json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise ValueError("Invalid JSON body")

    if not isinstance(parsed, dict):
        raise ValueError("JSON payload must be an object")

    return parsed


def _load_persisted_settings() -> Dict[str, Any]:
    if not SETTINGS_FILE.exists():
        return {}

    try:
        with SETTINGS_FILE.open("r", encoding="utf-8") as settings_file:
            data = json.load(settings_file)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        return {}

    return {}


def _load_rag_config() -> Dict[str, Any]:
    default_config = {
        "llm_model": settings.LOCAL_QWEN_MODEL,
        "top_k": 3,
        "temperature": 0.7,
    }
    if not RAG_CONFIG_FILE.exists():
        return default_config

    try:
        with RAG_CONFIG_FILE.open("r", encoding="utf-8") as config_file:
            data = json.load(config_file)
            if isinstance(data, dict):
                return {**default_config, **data}
    except (OSError, json.JSONDecodeError):
        return default_config

    return default_config


def _save_rag_config(config: Dict[str, Any]) -> None:
    RAG_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with RAG_CONFIG_FILE.open("w", encoding="utf-8") as config_file:
        json.dump(config, config_file)


def _build_runtime_llm_settings() -> Dict[str, Optional[str]]:
    persisted = _load_persisted_settings()

    provider = persisted.get("provider") or settings.LLM_PROVIDER
    if provider not in VALID_PROVIDERS:
        provider = settings.LLM_PROVIDER

    if provider == "gemini":
        default_model = settings.GEMINI_MODEL
        default_key = settings.GEMINI_API_KEY
    else:
        default_model = "anthropic/claude-3-haiku"
        default_key = settings.OPENROUTER_API_KEY

    model = persisted.get("model") or default_model
    api_key = persisted.get("api_key") or default_key

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }


def inject_citation_marks(answer: str, citations: List[Dict[str, Any]]) -> str:
    """
    Inject citation marks [1], [2], etc. into the answer text.
    Places citations at the end of sentences or paragraphs.
    """
    if not citations:
        return answer

    import re

    citation_ids = [c.get("citation_id", i + 1) for i, c in enumerate(citations)]

    sentences = re.split(r"([。！？.!?\n]+)", answer)
    result = []
    citation_idx = 0

    for i, part in enumerate(sentences):
        result.append(part)

        if i % 2 == 0 and part.strip() and citation_idx < len(citation_ids):
            if len(part.strip()) > 20:
                result.append(
                    f' <span class="inline-citation" data-citation-id="{citation_ids[citation_idx]}">[{citation_ids[citation_idx]}]</span>'
                )
                citation_idx += 1

    if citation_idx < len(citation_ids):
        result.append(
            ' <span class="inline-citations">'
            + " ".join(
                [
                    f'<span class="inline-citation" data-citation-id="{cid}">[{cid}]</span>'
                    for cid in citation_ids[citation_idx:]
                ]
            )
            + "</span>"
        )

    return "".join(result)


def analyze_differences(answers: List[str]) -> tuple:
    """
    Analyze differences between multiple answers.
    Returns (common_points, different_points).
    """
    if len(answers) < 2:
        return [], []

    import re

    def extract_sentences(text: str) -> List[str]:
        sentences = re.split(r"[。！？.!?\n]+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    all_sentences = [extract_sentences(a) for a in answers]

    sentence_counts: Dict[str, int] = {}
    for sentences in all_sentences:
        for s in sentences:
            normalized = s.lower()
            sentence_counts[normalized] = sentence_counts.get(normalized, 0) + 1

    common = [
        s for s, count in sentence_counts.items() if count == len(answers) and count > 1
    ]

    different = []
    for i, sentences in enumerate(all_sentences):
        for s in sentences:
            normalized = s.lower()
            if sentence_counts.get(normalized, 0) == 1:
                different.append(f"[{answers[i][:20]}...] {s[:80]}...")

    common_points = [s.capitalize() for s in common[:5]]
    different_points = different[:5]

    return common_points, different_points
