# OpenDataLoader PDF Integration Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add OpenDataLoader PDF as an alternative PDF parsing backend, keeping pypdf as default. Only switch when fully ready.

**Architecture:** Create a new service module `opendataloader_pdf_service.py` that mirrors the same function signatures as `pdf_chunking.py` (`read_pdf_text`, `read_pdf_pages`, `chunk_pdf_with_metadata`). Add a config setting `PDF_PARSER` to select between `pypdf` (default) and `opendataloader`. `pdf_indexing.py` uses a factory function to pick the correct parser at runtime.

**Tech Stack:** Python, opendataloader-pdf (PyPI), pypdf, pydantic-settings

---

## Task 1: Add PDF_PARSER config setting

**Files:**
- Modify: `app/config.py:23-25`

**Step 1: Write the failing test**

```python
# tests/test_config.py - add test for PDF_PARSER setting
def test_pdf_parser_defaults_to_pypdf():
    from app.config import Settings
    s = Settings()
    assert s.PDF_PARSER == "pypdf"

def test_pdf_parser_accepts_opendataloader():
    from app.config import Settings
    s = Settings(PDF_PARSER="opendataloader")
    assert s.PDF_PARSER == "opendataloader"

def test_pdf_parser_invalid_falls_back_to_pypdf():
    from app.config import Settings
    s = Settings(PDF_PARSER="invalid")
    assert s.PDF_PARSER == "pypdf"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py::test_pdf_parser_defaults_to_pypdf -v`
Expected: FAIL with "Settings has no PDF_PARSER attribute"

**Step 3: Implement the config setting**

Add to `app/config.py`:

```python
PDF_PARSER: str = "pypdf"  # "pypdf" or "opendataloader"

@field_validator("PDF_PARSER", mode="before")
@classmethod
def validate_pdf_parser(cls, value):
    parser = str(value).strip().lower()
    if parser not in {"pypdf", "opendataloader"}:
        return "pypdf"
    return parser
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -k pdf_parser -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/config.py tests/test_config.py
git commit -m "feat: add PDF_PARSER config setting (pypdf|opendataloader)"
```

---

## Task 2: Create OpenDataLoader PDF service module

**Files:**
- Create: `app/services/opendataloader_pdf_service.py`
- Create: `tests/test_opendataloader_pdf_service.py`

**Step 1: Write the failing tests**

```python
# tests/test_opendataloader_pdf_service.py
import pytest
from app.services.opendataloader_pdf_service import (
    OpenDataLoaderPDFError,
    read_pdf_text_opendataloader,
    read_pdf_pages_opendataloader,
    chunk_pdf_with_metadata_opendataloader,
    is_opendataloader_available,
)


def test_is_opendataloader_available_returns_bool():
    result = is_opendataloader_available()
    assert isinstance(result, bool)


def test_read_pdf_text_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_pdf_text_opendataloader("/nonexistent/file.pdf")


def test_read_pdf_pages_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_pdf_pages_opendataloader("/nonexistent/file.pdf")


def test_chunk_pdf_file_not_found():
    with pytest.raises(FileNotFoundError):
        chunk_pdf_with_metadata_opendataloader("/nonexistent/file.pdf")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_opendataloader_pdf_service.py -v`
Expected: FAIL with "ModuleNotFoundError"

**Step 3: Implement the service module**

Create `app/services/opendataloader_pdf_service.py`:

```python
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import settings

CHUNK_SIZE_DEFAULT = 500


class OpenDataLoaderPDFError(Exception):
    pass


def is_opendataloader_available() -> bool:
    """Check if opendataloader-pdf is installed."""
    try:
        import opendataloader_pdf  # noqa: F401
        return True
    except ImportError:
        return False


def _import_opendataloader():
    """Lazy import with helpful error message."""
    try:
        import opendataloader_pdf
        return opendataloader_pdf
    except ImportError:
        raise OpenDataLoaderPDFError(
            "opendataloader-pdf is not installed. "
            "Install it with: pip install opendataloader-pdf"
        )


def _normalize_path_arg(path: str) -> str:
    cleaned = str(path).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def read_pdf_text_opendataloader(pdf_path: str) -> str:
    """Read all text from a PDF using OpenDataLoader PDF."""
    pages = read_pdf_pages_opendataloader(pdf_path)
    return "\n".join([page["text"] for page in pages])


def read_pdf_pages_opendataloader(pdf_path: str) -> List[Dict[str, Any]]:
    """Read a PDF and return page-level text records using OpenDataLoader PDF."""
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {cleaned_path}")

    odl = _import_opendataloader()

    with tempfile.TemporaryDirectory() as tmp_dir:
        odl.convert(
            input_path=[str(pdf_file)],
            output_dir=tmp_dir,
            format="json",
        )

        json_file = Path(tmp_dir) / f"{pdf_file.stem}.json"
        if not json_file.exists():
            return []

        import json

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    pages: List[Dict[str, Any]] = []
    page_texts: Dict[int, List[str]] = {}

    elements = data if isinstance(data, list) else data.get("elements", data.get("pages", []))

    for element in elements:
        if isinstance(element, dict):
            page_num = element.get("page number", element.get("page", 1))
            content = element.get("content", "")
            if content and str(content).strip():
                page_texts.setdefault(page_num, []).append(str(content).strip())

    for page_num in sorted(page_texts.keys()):
        combined = "\n".join(page_texts[page_num])
        if combined:
            pages.append({"page": page_num, "text": combined})

    return pages


def chunk_pdf_with_metadata_opendataloader(
    pdf_path: str,
    chunk_size: int = 500,
    source_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Chunk a PDF using OpenDataLoader PDF with metadata."""
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    resolved_source = source_name or pdf_file.name
    page_records = read_pdf_pages_opendataloader(cleaned_path)

    chunk_records: List[Dict[str, Any]] = []
    for page_record in page_records:
        page_num = int(page_record["page"])
        page_text = str(page_record["text"])
        page_chunks = _split_text_into_chunks(page_text, chunk_size=chunk_size)

        char_position = 0
        for chunk in page_chunks:
            chunk_length = len(chunk)
            chunk_records.append(
                {
                    "text": chunk,
                    "source": resolved_source,
                    "page": page_num,
                    "char_start": char_position,
                    "char_end": char_position + chunk_length,
                    "bbox": None,
                }
            )
            char_position += chunk_length

    return chunk_records


def _split_text_into_chunks(text: str, chunk_size: int = 500) -> List[str]:
    """Split text into chunks, reusing the same logic as pdf_chunking.py."""
    from app.services.pdf_chunking import split_text_into_chunks
    return split_text_into_chunks(text, chunk_size=chunk_size)
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_opendataloader_pdf_service.py -v`
Expected: PASS (availability check and file-not-found tests pass; actual PDF parsing tests skip if opendataloader not installed)

**Step 5: Commit**

```bash
git add app/services/opendataloader_pdf_service.py tests/test_opendataloader_pdf_service.py
git commit -m "feat: add OpenDataLoader PDF service module with same interface as pdf_chunking"
```

---

## Task 3: Create parser factory in pdf_indexing.py

**Files:**
- Modify: `app/services/pdf_indexing.py:8`

**Step 1: Write the failing test**

```python
# tests/test_pdf_parser_factory.py
def test_get_pdf_parser_returns_pypdf_by_default(monkeypatch):
    monkeypatch.setattr("app.config.settings.PDF_PARSER", "pypdf")
    from app.services.pdf_indexing import get_pdf_parser
    parser = get_pdf_parser()
    assert parser["name"] == "pypdf"
    assert callable(parser["read_text"])
    assert callable(parser["read_pages"])
    assert callable(parser["chunk_with_metadata"])


def test_get_pdf_parser_returns_opendataloader(monkeypatch):
    monkeypatch.setattr("app.config.settings.PDF_PARSER", "opendataloader")
    from app.services.pdf_indexing import get_pdf_parser
    parser = get_pdf_parser()
    assert parser["name"] == "opendataloader"


def test_get_pdf_parser_unknown_falls_back_to_pypdf(monkeypatch):
    monkeypatch.setattr("app.config.settings.PDF_PARSER", "unknown")
    from app.services.pdf_indexing import get_pdf_parser
    parser = get_pdf_parser()
    assert parser["name"] == "pypdf"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_pdf_parser_factory.py -v`
Expected: FAIL with "cannot import get_pdf_parser"

**Step 3: Implement the factory**

Add to `app/services/pdf_indexing.py` (after imports, before `PDFIndexingError`):

```python
from typing import Any, Callable, Dict

def get_pdf_parser() -> Dict[str, Any]:
    """Return the configured PDF parser backend."""
    if settings.PDF_PARSER == "opendataloader":
        from app.services.opendataloader_pdf_service import (
            OpenDataLoaderPDFError,
            chunk_pdf_with_metadata_opendataloader,
            read_pdf_pages_opendataloader,
            read_pdf_text_opendataloader,
        )

        return {
            "name": "opendataloader",
            "read_text": read_pdf_text_opendataloader,
            "read_pages": read_pdf_pages_opendataloader,
            "chunk_with_metadata": chunk_pdf_with_metadata_opendataloader,
        }

    return {
        "name": "pypdf",
        "read_text": read_pdf_text,
        "read_pages": read_pdf_pages,
        "chunk_with_metadata": chunk_pdf_with_metadata,
    }
```

**Step 4: Update `index_pdf_file` to use factory**

Replace direct imports of `read_pdf_text` and `chunk_pdf_with_metadata` with factory calls:

```python
# In index_pdf_file():
parser = get_pdf_parser()

try:
    text = parser["read_text"](cleaned_pdf_path)
except FileNotFoundError as exc:
    raise PDFIndexingError(str(exc)) from exc
except OSError as exc:
    raise PDFIndexingError(
        f"Failed to read PDF '{cleaned_pdf_path}': {str(exc)}"
    ) from exc

# ...

chunk_records = parser["chunk_with_metadata"](
    pdf_path=cleaned_pdf_path,
    chunk_size=chunk_size,
    source_name=source_name,
)
```

**Step 5: Run tests**

Run: `pytest tests/test_pdf_parser_factory.py tests/test_pdf_indexing.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add app/services/pdf_indexing.py tests/test_pdf_parser_factory.py
git commit -m "feat: add PDF parser factory with config-driven backend selection"
```

---

## Task 4: Update requirements.txt

**Files:**
- Modify: `requirements.txt`

**Step 1: Add opendataloader-pdf as optional comment dependency**

Append to `requirements.txt`:

```
# Optional: OpenDataLoader PDF (requires Java 11+)
# opendataloader-pdf>=2.0.0
```

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "chore: add opendataloader-pdf as optional dependency comment"
```

---

## Task 5: Run full quality check

**Step 1: Lint and typecheck**

```bash
ruff check app/services/opendataloader_pdf_service.py app/services/pdf_indexing.py app/config.py
black --check app/services/opendataloader_pdf_service.py app/services/pdf_indexing.py app/config.py
mypy app/services/opendataloader_pdf_service.py app/services/pdf_indexing.py app/config.py
```

**Step 2: Run all tests**

```bash
pytest tests/ -v
```

**Step 3: Fix any issues, then commit**

```bash
git add -A
git commit -m "fix: resolve lint/type issues in opendataloader integration"
```

---

## How to Switch (When Ready)

1. Install: `pip install opendataloader-pdf`
2. Install Java 11+ (e.g., from Adoptium)
3. Set in `.env`: `PDF_PARSER=opendataloader`
4. Rebuild index: upload a PDF or trigger full rebuild
5. Verify output quality
6. If good, make `opendataloader` the default in config.py

## Rollback

Simply set `PDF_PARSER=pypdf` in `.env` — no code changes needed.
