import json
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


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

        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)

    pages: List[Dict[str, Any]] = []
    page_texts: Dict[int, List[str]] = {}

    elements = (
        data if isinstance(data, list) else data.get("elements", data.get("pages", []))
    )

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
