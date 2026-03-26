# AGENTS.md - Development Guidelines

## Project Overview
AI-based Lecture Note Q&A System using RAG. Django backend with sentence-transformers
for embeddings, FAISS for vector storage, BM25 for keyword retrieval, and LLM
integration via Gemini/OpenRouter/Ollama.

## Build / Lint / Test Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running the Application
```bash
python manage.py runserver 0.0.0.0:8000
```

### Running Tests
```bash
pytest tests/                          # Run all tests
pytest tests/test_name.py              # Run specific test file
pytest tests/test_name.py::test_func   # Run single test
pytest -v                              # Verbose output
pytest --tb=short                      # Short traceback format
```

### Linting & Code Quality
```bash
ruff check app/ django_app/ django_backend/ manage.py
ruff check app/ django_app/ django_backend/ manage.py --fix
black app/ django_app/ django_backend/ manage.py
mypy app/ django_app/ django_backend/
```

### Combined Quality Check
```bash
ruff check app/ django_app/ django_backend/ manage.py && black --check app/ django_app/ django_backend/ manage.py && mypy app/ django_app/ django_backend/
```

## Code Style Guidelines

### Imports
- Use absolute imports (e.g., `from app.services.pdf_loader import PDFLoader`)
- Group: standard library, third-party, local application (blank line between groups)
- Use `__all__` in modules to declare public API

### Formatting
- Line length: 88 characters (Black default)
- 4 spaces indentation, trailing commas in multi-line constructs
- Use f-strings for string formatting

### Types
- Always use type hints for function arguments and return values
- Use `Optional[X]`, `List`, `Dict` from typing (Python 3.9 compatibility)

### Naming Conventions
- Variables/functions: `snake_case`
- Classes: `PascalCase` (e.g., `PDFLoader`, `RAGPipeline`)
- Constants: `UPPER_SNAKE_CASE`
- Private: prefix with underscore (e.g., `_private_method`)
- Django views: suffix with `_view` or descriptive (e.g., `upload_pdf`, `ask_question`)

### Error Handling
- Custom exceptions for domain errors (e.g., `PDFIndexingError`, `LocalRAGError`)
- Catch specific exceptions, never bare `except:`
- Return JSON errors with `detail` field using `_error_response(detail, status_code)`
- Pattern:
  ```python
  try:
      # business logic
  except SpecificError as exc:
      return _error_response(str(exc), status=400)
  except Exception as exc:  # noqa: BLE001
      return _error_response(f"Failed to process: {str(exc)}", status=500)
  ```

## Architecture & Module Structure

```text
django_backend/       # Django project settings/urls/asgi/wsgi
django_app/           # Django API views (views/, models.py, consumers.py)
app/
├── config.py         # Settings via pydantic-settings (.env)
├── models/           # Pydantic schemas
└── services/         # Core business logic
    ├── pdf_loader.py       # PDF text extraction
    ├── pdf_indexing.py     # PDF indexing to FAISS
    ├── chunker.py          # Text chunking
    ├── embedding.py        # Sentence embeddings
    ├── vector_store.py     # FAISS vector storage
    ├── local_rag.py        # RAG orchestration & LLM calls
    ├── rag_pipeline.py     # RAG pipeline
    ├── citation_rag.py     # Citation-aware RAG
    ├── summarizer.py       # Document summarization
    └── question_suggestions.py
retrieval/            # Hybrid retrieval (BM25 + dense)
├── bm25_index.py
├── dense_retriever.py
└── hybrid_retriever.py
chunking/             # Smart chunking strategies
evaluation/           # Retrieval evaluation & monitoring
config/               # Retrieval configuration
tests/                # pytest tests
scripts/              # Utility scripts
```

### Key Patterns
- Business logic in `app/services/`, called from Django views
- Configuration in `app/config.py` via pydantic-settings (no hardcoded values)
- Use `threading.Lock()` for shared state across requests
- Django views: `@csrf_exempt`, `_get_json_body(request)`, `_error_response()`
- Return `JsonResponse` for API, `HttpResponse` for HTML

### RAG Pipeline Flow
1. `retrieve_with_faiss(query, top_k, source_filter)` - search vector store
2. `build_context_from_sources(sources)` - format context for LLM
3. `generate(query, context)` - route to configured LLM provider

### File Upload Flow
1. Validate file type (PDF only) and size
2. Generate safe filename, save to documents directory
3. Index PDF to FAISS (full rebuild or append)
4. Return success response with stats

## Testing Guidelines
- pytest framework, tests in `tests/` mirroring app structure
- Mock external dependencies (LLM API, file system, FAISS)
- Use `monkeypatch` for function replacement, `unittest.mock` for complex mocks
- Test names: `test_<method>_<expected_behavior>`
- Django tests: use `django.test.Client`, set `DJANGO_SETTINGS_MODULE`

## API Design
- RESTful: POST for create, GET for retrieve
- 200 success, 400 validation, 500 server error, 503 service unavailable, 504 timeout
- Include `source_snippets` in ask responses for transparency
- `APPEND_SLASH = False` - endpoints work with/without trailing slash
