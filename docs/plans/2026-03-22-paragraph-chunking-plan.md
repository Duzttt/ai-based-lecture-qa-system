# Paragraph-Based Chunking Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add paragraph-based document structure-aware chunking to the PDF processing pipeline.

**Architecture:** New `split_text_by_paragraphs()` function in `pdf_chunking.py` that splits text by paragraph boundaries (`\n\n+`), merges small paragraphs into chunks ≤ chunk_size, and falls back to sentence-level splitting for oversized paragraphs. A `CHUNK_STRATEGY` config option allows switching between "character" (legacy) and "paragraph" (new).

**Tech Stack:** Python, regex, existing pypdf dependency

---

## Task 1: Add CHUNK_STRATEGY config

**Files:**
- Modify: `app/config.py`
- Test: `tests/test_config_chunking_strategy.py`

**Step 1: Write the failing test**

```python
from app.config import Settings


def test_default_chunk_strategy_is_paragraph():
    settings = Settings(_env_file=None)
    assert settings.CHUNK_STRATEGY == "paragraph"


def test_chunk_strategy_accepts_character():
    settings = Settings(_env_file=None, CHUNK_STRATEGY="character")
    assert settings.CHUNK_STRATEGY == "character"


def test_chunk_strategy_invalid_falls_back_to_paragraph():
    settings = Settings(_env_file=None, CHUNK_STRATEGY="invalid")
    assert settings.CHUNK_STRATEGY == "paragraph"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_config_chunking_strategy.py -v`
Expected: FAIL with "CHUNK_STRATEGY" attribute error

**Step 3: Add CHUNK_STRATEGY to Settings class**

In `app/config.py`, add after line 25 (`CHUNK_OVERLAP: int = 50`):

```python
CHUNK_STRATEGY: str = "paragraph"  # "character" | "paragraph"
```

Add a validator after the existing `UPLOAD_INDEXING_STRATEGY` validator:

```python
@field_validator("CHUNK_STRATEGY", mode="before")
@classmethod
def validate_chunk_strategy(cls, value):
    strategy = str(value).strip().lower()
    allowed = {"character", "paragraph"}
    if strategy not in allowed:
        return "paragraph"
    return strategy
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_config_chunking_strategy.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/config.py tests/test_config_chunking_strategy.py
git commit -m "feat: add CHUNK_STRATEGY config option"
```

---

## Task 2: Add split_text_by_paragraphs() function

**Files:**
- Modify: `app/services/pdf_chunking.py`
- Test: `tests/test_paragraph_chunking.py`

**Step 1: Write the failing test**

```python
from app.services.pdf_chunking import split_text_by_paragraphs


def test_empty_text_returns_empty():
    assert split_text_by_paragraphs("") == []


def test_none_text_returns_empty():
    assert split_text_by_paragraphs(None) == []


def test_single_paragraph_fits_in_one_chunk():
    text = "This is a short paragraph."
    chunks = split_text_by_paragraphs(text, chunk_size=200)
    assert len(chunks) == 1
    assert chunks[0] == "This is a short paragraph."


def test_two_paragraphs_merge_into_one_chunk():
    text = "First paragraph.\n\nSecond paragraph."
    chunks = split_text_by_paragraphs(text, chunk_size=200)
    assert len(chunks) == 1
    assert "First paragraph." in chunks[0]
    assert "Second paragraph." in chunks[0]


def test_two_paragraphs_split_when_exceeds_chunk_size():
    text = "First paragraph is here.\n\nSecond paragraph is here."
    chunks = split_text_by_paragraphs(text, chunk_size=30)
    assert len(chunks) == 2
    assert "First paragraph" in chunks[0]
    assert "Second paragraph" in chunks[1]


def test_long_paragraph_falls_back_to_sentence_splitting():
    text = "Sentence one is short. Sentence two is a bit longer. Sentence three is also here."
    chunks = split_text_by_paragraphs(text, chunk_size=40)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 40


def test_multiple_newlines_treated_as_paragraph_boundary():
    text = "Para one.\n\n\n\nPara two."
    chunks = split_text_by_paragraphs(text, chunk_size=200)
    assert len(chunks) == 1
    assert "Para one." in chunks[0]
    assert "Para two." in chunks[0]


def test_internal_whitespace_normalized():
    text = "Para  with   extra    spaces.\n\nAnother  para."
    chunks = split_text_by_paragraphs(text, chunk_size=200)
    assert "  " not in chunks[0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_paragraph_chunking.py -v`
Expected: FAIL with "split_text_by_paragraphs" not defined

**Step 3: Add split_text_by_paragraphs() to pdf_chunking.py**

Add after `split_text_into_chunks()` (after line 173):

```python
def split_text_by_paragraphs(text: str, chunk_size: int = 500) -> List[str]:
    """
    Split text by paragraph boundaries, merging small paragraphs into chunks.
    Falls back to sentence-level splitting for oversized paragraphs.
    """
    if not text or not str(text).strip():
        return []

    cleaned = re.sub(r"\s*\n\s*\n\s*", "\n\n", str(text)).strip()
    paragraphs = re.split(r"\n\n+", cleaned)
    paragraphs = [re.sub(r"\s+", " ", p).strip() for p in paragraphs if p.strip()]

    if not paragraphs:
        return []

    chunks: List[str] = []
    current_chunk = ""

    for para in paragraphs:
        if len(para) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            chunks.extend(split_text_into_chunks(para, chunk_size))
            continue

        candidate = f"{current_chunk}\n\n{para}".strip() if current_chunk else para
        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = para

    if current_chunk:
        chunks.append(current_chunk)

    return [c for c in chunks if c.strip()]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_paragraph_chunking.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/pdf_chunking.py tests/test_paragraph_chunking.py
git commit -m "feat: add paragraph-based chunking with sentence fallback"
```

---

## Task 3: Integrate CHUNK_STRATEGY into chunk_pdf_with_metadata()

**Files:**
- Modify: `app/services/pdf_chunking.py`
- Test: `tests/test_chunk_pdf_with_metadata.py`

**Step 1: Write the failing test**

```python
import os
import tempfile
from unittest.mock import patch

from app.services.pdf_chunking import chunk_pdf_with_metadata


def _create_minimal_pdf(path: str):
    """Create a minimal PDF with two paragraphs for testing."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 6, "First paragraph of text here.")
    pdf.ln(6)
    pdf.multi_cell(0, 6, "Second paragraph of text here.")
    pdf.output(path)


def test_chunk_pdf_uses_paragraph_strategy_by_default():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        _create_minimal_pdf(f.name)
        pdf_path = f.name
    try:
        chunks = chunk_pdf_with_metadata(pdf_path, chunk_size=200)
        assert len(chunks) > 0
        for chunk in chunks:
            assert "source" in chunk
            assert "page" in chunk
    finally:
        os.unlink(pdf_path)


@patch("app.services.pdf_chunking.settings")
def test_chunk_pdf_respects_character_strategy(mock_settings):
    mock_settings.CHUNK_STRATEGY = "character"
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        _create_minimal_pdf(f.name)
        pdf_path = f.name
    try:
        chunks = chunk_pdf_with_metadata(pdf_path, chunk_size=200)
        assert len(chunks) > 0
    finally:
        os.unlink(pdf_path)
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_chunk_pdf_with_metadata.py -v`
Expected: FAIL or import error

**Step 3: Modify chunk_pdf_with_metadata() to use CHUNK_STRATEGY**

In `app/services/pdf_chunking.py`, modify the `chunk_pdf_with_metadata()` function.
Change line 191:
```python
page_chunks = split_text_into_chunks(page_text, chunk_size=chunk_size)
```
to:
```python
from app.config import settings as app_settings

strategy = getattr(app_settings, "CHUNK_STRATEGY", "paragraph")
if strategy == "paragraph":
    page_chunks = split_text_by_paragraphs(page_text, chunk_size=chunk_size)
else:
    page_chunks = split_text_into_chunks(page_text, chunk_size=chunk_size)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_chunk_pdf_with_metadata.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/pdf_chunking.py tests/test_chunk_pdf_with_metadata.py
git commit -m "feat: integrate CHUNK_STRATEGY into chunk_pdf_with_metadata"
```

---

## Task 4: Run full test suite and lint

**Files:**
- No file changes

**Step 1: Run all tests**

Run: `pytest tests/ -v`
Expected: All PASS

**Step 2: Run linting**

Run: `ruff check app/services/pdf_chunking.py app/config.py`
Expected: No errors

**Step 3: Run type checking**

Run: `mypy app/services/pdf_chunking.py app/config.py`
Expected: No errors
