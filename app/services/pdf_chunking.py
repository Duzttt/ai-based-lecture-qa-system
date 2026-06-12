import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from pypdf import PdfReader


def _normalize_path_arg(path: str) -> str:
    cleaned = str(path).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {"'", '"'}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def read_pdf_text(pdf_path: str) -> str:
    """Read all text from a PDF file."""
    pages = read_pdf_pages(pdf_path)
    return "\n".join([page["text"] for page in pages])


def read_pdf_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """Read a PDF and return page-level text records with page number metadata."""
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {cleaned_path}")

    reader = PdfReader(str(pdf_file))
    pages: List[Dict[str, Any]] = []

    for page_idx, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        cleaned = page_text.strip()
        if cleaned:
            pages.append(
                {
                    "page": page_idx,
                    "text": cleaned,
                }
            )

    return pages


def extract_page_text_with_positions(
    pdf_path: str,
    page_number: int,
) -> List[Dict[str, Any]]:
    """
    Extract text from a specific page with position information.
    Returns list of text items with their approximate positions.
    """
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    if not pdf_file.exists():
        raise FileNotFoundError(f"PDF file not found: {cleaned_path}")

    reader = PdfReader(str(pdf_file))
    if page_number < 1 or page_number > len(reader.pages):
        return []

    page = reader.pages[page_number - 1]

    text_items: List[Dict[str, Any]] = []

    if hasattr(page, "extract_texts"):
        try:
            texts = page.extract_texts()
            for item in texts:
                if isinstance(item, dict):
                    text_items.append(
                        {
                            "text": item.get("text", ""),
                            "x": item.get("x", 0),
                            "y": item.get("y", 0),
                            "width": item.get("width", 0),
                            "height": item.get("height", 0),
                        }
                    )
                elif isinstance(item, str) and item.strip():
                    text_items.append(
                        {
                            "text": item,
                            "x": 0,
                            "y": 0,
                            "width": 0,
                            "height": 0,
                        }
                    )
        except Exception:
            pass

    if not text_items:
        page_text = page.extract_text() or ""
        if page_text.strip():
            text_items.append(
                {
                    "text": page_text.strip(),
                    "x": 0,
                    "y": 0,
                    "width": 0,
                    "height": 0,
                }
            )

    return text_items


def split_text_into_chunks(
    text: str, chunk_size: int = 500, overlap: int = 100
) -> List[str]:
    """
    Split text into <=chunk_size chunks while trying to preserve sentence boundaries.

    The last *overlap* characters of each chunk are repeated at the beginning of the
    next chunk to preserve context across boundaries.

    If a single sentence is longer than chunk_size, it is split on soft punctuation
    first, then by hard character boundary as a fallback.
    """
    if not text or not text.strip():
        return []

    normalized_text = re.sub(r"\s+", " ", text).strip()
    sentences = re.split(r"(?<=[。！？.!?])\s+", normalized_text)

    chunks: List[str] = []
    current_chunk = ""

    def flush_current() -> None:
        nonlocal current_chunk
        if current_chunk:
            chunks.append(current_chunk)
            current_chunk = ""

    def split_oversized_sentence(sentence: str) -> List[str]:
        parts: List[str] = []
        remaining = sentence.strip()

        while len(remaining) > chunk_size:
            split_at = -1
            for delimiter in ["，", "；", "：", ",", ";", ":", " "]:
                pos = remaining.rfind(delimiter, 0, chunk_size)
                split_at = max(split_at, pos)

            if split_at <= 0:
                parts.append(remaining[:chunk_size].strip())
                remaining = remaining[chunk_size:].strip()
            else:
                parts.append(remaining[: split_at + 1].strip())
                remaining = remaining[split_at + 1 :].strip()

        if remaining:
            parts.append(remaining)

        return parts

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_parts = (
            split_oversized_sentence(sentence)
            if len(sentence) > chunk_size
            else [sentence]
        )

        for part in sentence_parts:
            candidate = f"{current_chunk} {part}".strip() if current_chunk else part
            if len(candidate) <= chunk_size:
                current_chunk = candidate
            else:
                # Carry over the tail of the current chunk as overlap
                tail = current_chunk[-overlap:] if overlap > 0 else ""
                flush_current()
                current_chunk = f"{tail} {part}".strip() if tail else part

    flush_current()
    return chunks


_COURSE_CODE_RE = re.compile(
    r"""(?ixm)
    (?:course\s*code|kod\s*kursus)\s*[:\-]?\s*
    (?P<code>[A-Z]{2,5}\s*\d{3,4}[A-Z]?)
    |
    ^\s*(?P<bare>[A-Z]{2,5}\s*\d{3,4}[A-Z]?)\b
"""
)

_TITLE_SEPARATORS = ("\u2013", "\u2014", "-", ":", "|", "/", "\t")

_LECTURER_RE = re.compile(
    r"""(?ix)
    (?:^|\n)\s*
    (?:
        (?:course\s*(?:is\s*)?taught\s*by|
           lecturer|
           instructor|
           author|
           prepared\s*by|
           coordinator|
           pensyarah|
           disusun\s*oleh|
           disediakan\s*oleh)
        \s*[:\-]?\s*
    )
    (?P<name>
        (?:(?:Dr|Prof|Mr|Mrs|Ms|Madam)\.?\s+)?
        (?:(?:Assoc\.?\s*Prof\.?\s+)?|(?:Prof\.?\s+Madya\s+)?)?
        [A-Z][a-zA-Z\.'\-]+
        (?:\s+[A-Z][a-zA-Z\.'\-]+){1,4}
    )
    \s*(?:\n|$)
"""
)

# Matches a standalone name line such as "Dr. Nur Zareen Zulkarnain"
# even when no "Lecturer:" label precedes it.
_LECTURER_BARE_RE = re.compile(
    r"(?m)^\s*(?P<name>(?:Dr|Prof|Mr|Mrs|Ms|Madam)\.?\s+[A-Z][a-zA-Z\.'\-]+"
    r"(?:\s+[A-Z][a-zA-Z\.'\-]+){1,4})\s*(?:\([^)]+\))?\s*$"
)

_DEPARTMENT_RE = re.compile(
    r"""(?ix)
    (?:
        (?:department|jabatan)\s+of\s+
        |
        (?:undergraduate\s+)?department\s+of\s+
    )
    (?P<name>[A-Z][^\n;]+?(?:\s*\([A-Za-z0-9 &]+\))?)
    (?=\s*(?:\n|;|$))
"""
)

_FACULTY_RE = re.compile(
    r"""(?ix)
    (?:faculty|fakulti)\s+of\s+(?P<name>[A-Z][^\n,;]+?)
    (?=\s*(?:\n|,|;|\(|$|\s{2,}))
"""
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def _clean_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", name).strip()
    return cleaned.rstrip(".,;")


def _find_course_code(cover_text: str) -> str:
    for match in _COURSE_CODE_RE.finditer(cover_text):
        code = match.group("code") or match.group("bare") or ""
        code = re.sub(r"\s+", " ", code).strip()
        if code:
            return code
    return ""


def _find_course_title(
    cover_text: str, course_code: str, max_lines_after: int = 5
) -> str:
    if not course_code:
        return ""
    lines = [line.strip() for line in cover_text.splitlines() if line.strip()]
    for idx, line in enumerate(lines):
        if course_code not in line:
            continue
        for sep in _TITLE_SEPARATORS:
            if sep in line:
                _, _, after = line.partition(sep)
                title = re.sub(r"^[\s\-–—:]+", "", after).strip()
                title = re.split(r"[\n\.]", title, maxsplit=1)[0].strip()
                if 2 < len(title) < 120:
                    return title
        for offset in range(1, max_lines_after + 1):
            if idx + offset >= len(lines):
                break
            candidate = lines[idx + offset]
            if any(
                keyword in candidate.lower()
                for keyword in (
                    "department",
                    "jabatan",
                    "faculty",
                    "fakulti",
                    "lecturer",
                    "instructor",
                    "author",
                    "pensyarah",
                    "course",
                    "kod",
                )
            ):
                continue
            if re.match(r"^[\d\W]", candidate):
                continue
            if 2 < len(candidate) < 120:
                return candidate
    return ""


def _find_lecturer(cover_text: str) -> str:
    for match in _LECTURER_RE.finditer(cover_text):
        name = _clean_name(match.group("name"))
        if name and len(name) > 5:
            return name
    for match in _LECTURER_BARE_RE.finditer(cover_text):
        name = _clean_name(match.group("name"))
        if name and len(name) > 5:
            return name
    return ""


def _find_department(cover_text: str) -> str:
    match = _DEPARTMENT_RE.search(cover_text)
    if not match:
        return ""
    name = _clean_name(match.group("name"))
    name = re.sub(r"\s+", " ", name)
    return name


def _find_faculty(cover_text: str) -> str:
    match = _FACULTY_RE.search(cover_text)
    if not match:
        return ""
    return _clean_name(match.group("name"))


def extract_course_metadata(
    pages: List[Dict[str, Any]],
    max_pages: int = 3,
) -> Dict[str, str]:
    """Extract course-level metadata from the first few pages of a PDF.

    Returns a dict with the following keys (all strings, possibly empty):
        - course_code: e.g. "BAXI 3113"
        - course_title: e.g. "INTELLIGENT AGENT"
        - lecturer: e.g. "Dr. Nur Zareen Zulkarnain"
        - department: e.g. "Department of Intelligent Computing and Analytics (ICA)"
        - faculty: e.g. "Faculty of Computer Science"
    """
    empty: Dict[str, str] = {
        "course_code": "",
        "course_title": "",
        "lecturer": "",
        "department": "",
        "faculty": "",
    }
    if not pages:
        return empty

    cover_text = "\n".join(str(page.get("text", "")) for page in pages[:max_pages])
    if not cover_text.strip():
        return empty

    course_code = _find_course_code(cover_text)
    course_title = _find_course_title(cover_text, course_code)
    lecturer = _find_lecturer(cover_text)
    department = _find_department(cover_text)
    faculty = _find_faculty(cover_text)

    # Discard lecturer if it accidentally matched the department name.
    if department and lecturer and department.lower().startswith(lecturer.lower()):
        lecturer = ""

    return {
        "course_code": course_code,
        "course_title": course_title,
        "lecturer": lecturer,
        "department": department,
        "faculty": faculty,
    }


def _format_metadata_header(metadata: Dict[str, str]) -> str:
    parts: List[str] = []
    course = " ".join(
        part
        for part in (metadata.get("course_code"), metadata.get("course_title"))
        if part
    )
    if course:
        parts.append(f"Course: {course}")
    if metadata.get("lecturer"):
        parts.append(f"Lecturer/Author: {metadata['lecturer']}")
    if metadata.get("department"):
        parts.append(f"Department: {metadata['department']}")
    if metadata.get("faculty"):
        parts.append(f"Faculty: {metadata['faculty']}")
    if not parts:
        return ""
    return "[Course Metadata] " + "; ".join(parts) + "\n\n---\n\n"


def chunk_pdf_with_metadata(
    pdf_path: str,
    chunk_size: int = 500,
    overlap: int = 100,
    source_name: Optional[str] = None,
    prepend_course_metadata: bool = True,
) -> List[Dict[str, Any]]:
    """Chunk a PDF while preserving source filename and page number metadata.

    When ``prepend_course_metadata`` is True (the default), a compact header
    describing the course (code, title, lecturer, department, faculty) is
    prepended to every chunk. This is a contextual-retrieval technique that
    dramatically improves recall for questions about course-level metadata
    (e.g. "Who is the author?" or "What is the course code?") which would
    otherwise be confined to a single chunk on the cover page.
    """
    cleaned_path = _normalize_path_arg(pdf_path)
    pdf_file = Path(cleaned_path)
    resolved_source = source_name or pdf_file.name
    page_records = read_pdf_pages(cleaned_path)

    metadata_header = ""
    if prepend_course_metadata:
        course_metadata = extract_course_metadata(page_records)
        metadata_header = _format_metadata_header(course_metadata)

    chunk_records: List[Dict[str, Any]] = []
    for page_record in page_records:
        page_num = int(page_record["page"])
        page_text = str(page_record["text"])
        page_chunks = split_text_into_chunks(
            page_text, chunk_size=chunk_size, overlap=overlap
        )

        char_position = 0
        for chunk in page_chunks:
            chunk_length = len(chunk)
            final_text = f"{metadata_header}{chunk}" if metadata_header else chunk
            chunk_records.append(
                {
                    "text": final_text,
                    "source": resolved_source,
                    "page": page_num,
                    "char_start": char_position,
                    "char_end": char_position + chunk_length,
                    "bbox": estimate_bbox_from_position(
                        page_num, char_position, chunk_length, page_text
                    ),
                }
            )
            char_position += chunk_length

    return chunk_records


def estimate_bbox_from_position(
    page: int,
    char_start: int,
    char_end: int,
    page_text: str,
) -> Optional[List[float]]:
    """
    Estimate bounding box from character position.
    This is a rough approximation since pypdf doesn't provide precise bbox.
    Returns [x1, y1, x2, y2] normalized coordinates (0-1 range).
    """
    if not page_text or char_start >= len(page_text):
        return None

    total_chars = len(page_text)
    start_ratio = char_start / max(total_chars, 1)
    end_ratio = min(char_end / max(total_chars, 1), 1.0)

    x1 = 0.05
    x2 = 0.95
    y1 = start_ratio * 0.9 + 0.05
    y2 = end_ratio * 0.9 + 0.05

    return [x1, y1, x2, y2]


def preview_pdf_chunks(
    pdf_path: str,
    chunk_size: int = 500,
    overlap: int = 100,
    max_print_chunks: int = 8,
) -> List[str]:
    """Print chunk preview for manual inspection and return all chunks."""
    text = read_pdf_text(pdf_path)
    chunks = split_text_into_chunks(text, chunk_size=chunk_size, overlap=overlap)

    print(f"PDF: {pdf_path}")
    print(f"Total chars: {len(text)}")
    print(f"Total chunks: {len(chunks)}")
    print("-" * 80)

    for idx, chunk in enumerate(chunks[:max_print_chunks], start=1):
        print(f"[Chunk {idx}] length={len(chunk)}")
        print(chunk)
        print("-" * 80)

    return chunks
