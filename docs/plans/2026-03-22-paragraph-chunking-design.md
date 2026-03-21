# Design: Document Structure-Aware Paragraph Chunking

## Context

Current chunking in `pdf_chunking.py` uses sentence-level splitting (`split_text_into_chunks()`),
which groups sentences into fixed-size chunks (default 500 chars) without regard for paragraph
boundaries. This can split a logical paragraph across multiple chunks, losing semantic coherence.

The user's lecture notes are standard textbooks/chapters (one PDF per chapter, no sub-headings).
Paragraph-based chunking preserves natural text structure and improves retrieval quality.

## Chosen Approach: Paragraph-based Chunking (方案 1)

Split text by paragraph boundaries (`\n\n+`), merge small paragraphs into chunks ≤ chunk_size,
and fall back to sentence-level splitting for oversized paragraphs.

## Design

### 1. New function: `split_text_by_paragraphs()`

Location: `app/services/pdf_chunking.py`

```
def split_text_by_paragraphs(text: str, chunk_size: int = 500) -> List[str]:
```

Logic:
1. Normalize whitespace in text
2. Split by paragraph boundary: `re.split(r'\n\s*\n', text)`
3. Clean each paragraph (strip, remove internal excess whitespace)
4. Filter empty paragraphs
5. Merge consecutive small paragraphs:
   - If adding next paragraph keeps chunk ≤ chunk_size, merge
   - Otherwise flush current chunk, start new one
6. If a single paragraph exceeds chunk_size, fall back to existing `split_text_into_chunks()`
7. Return list of chunk strings

### 2. Modify `chunk_pdf_with_metadata()`

Change line 191 from:
```python
page_chunks = split_text_into_chunks(page_text, chunk_size=chunk_size)
```
to:
```python
page_chunks = split_text_by_paragraphs(page_text, chunk_size=chunk_size)
```

### 3. Keep existing `split_text_into_chunks()` unchanged

It serves as the fallback for oversized paragraphs.

### 4. New config option (optional)

In `app/config.py`:
```python
CHUNK_STRATEGY: str = "paragraph"  # "character" | "paragraph"
```

In `chunk_pdf_with_metadata()`, check `CHUNK_STRATEGY` to decide which splitter to use.

## Files to Modify

1. `app/services/pdf_chunking.py` - Add `split_text_by_paragraphs()`, update `chunk_pdf_with_metadata()`
2. `app/config.py` - Add `CHUNK_STRATEGY` setting

## Verification

1. Run existing tests: `pytest tests/ -v`
2. Test with a sample PDF to verify paragraph boundaries are respected
3. Verify chunk metadata (source, page, char_start, char_end) is still correct
