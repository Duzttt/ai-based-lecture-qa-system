import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from django.http import HttpRequest, JsonResponse

logger = logging.getLogger(__name__)


def _normalize_path_arg(path: str) -> str:
    cleaned = str(path).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _error_response(detail: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"detail": detail}, status=status)


def _get_json_body(request: HttpRequest) -> Dict[str, Any]:
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return {}


def _load_json_config(file_path: Path) -> Dict[str, Any]:
    if file_path.exists():
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load config from %s: %s", file_path, e)
    return {}


def _save_json_config(file_path: Path, data: Dict[str, Any]) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        logger.error("Failed to save config to %s: %s", file_path, e)
