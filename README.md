# AI-Based Lecture Note Q&A System (RAG)

An end-to-end Retrieval-Augmented Generation (RAG) application for asking
questions over lecture notes in PDF format.

The system lets you:

- Upload lecture PDFs
- Parse and split content into chunks (LangChain-powered)
- Embed chunks into vectors
- Retrieve relevant chunks for a question
- Generate grounded answers using Gemini, OpenRouter, or Local Qwen models

## Architecture Overview

### Backend pipeline

1. `POST /api/upload` receives a PDF.
2. `PDFLoader` parses the PDF text using LangChain `PyPDFLoader`.
3. `TextChunker` splits text with LangChain
  `RecursiveCharacterTextSplitter`.
4. `EmbeddingService` creates embeddings with
  `sentence-transformers/all-MiniLM-L6-v2`.
5. `VectorStore` stores vectors in a FAISS index (`data/faiss_index`).
6. `POST /api/chat` retrieves top chunks and sends context + question to the
  configured LLM provider.

### Frontend flow

- Vue 3 + Vite UI with dark glassmorphic design
- Features: PDF upload, real-time chat, settings panel, document management
- API calls proxied through Vite dev server to Django backend

## Tech Stack

| Layer | Technologies |
|-------|-------------|
| **Backend** | Django 5.2, Pydantic, Requests |
| **RAG** | LangChain, Sentence Transformers, FAISS |
| **Frontend** | Vue 3, Vite, TailwindCSS |
| **LLM** | Gemini, OpenRouter, Local Qwen (llama.cpp) |
| **Testing** | Pytest, Ruff, Black, MyPy |

## Repository Structure

```text
AI-Based-Lecture-Note-Question-Answering-System/
├── app/                          # Core RAG services
│   ├── config.py                 # Pydantic settings
│   └── services/
│       ├── chunker.py            # Text chunking
│       ├── embedding.py          # Sentence Transformers
│       ├── pdf_loader.py         # PDF parsing
│       ├── pdf_indexing.py       # PDF indexing pipeline
│       └── vector_store.py       # FAISS vector store
│
├── django_app/                   # Django app
│   ├── templates/                # HTML templates
│   ├── views.py                  # API endpoints
│   └── consumers.py              # WebSocket handlers
│
├── django_backend/               # Django project config
│   ├── settings.py               # Django settings
│   ├── urls.py                   # URL routing
│   ├── asgi.py                   # ASGI/WebSocket entry
│   └── wsgi.py                   # WSGI entry
│
├── frontend/                     # Vue 3 frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── App.vue
│   │   │   ├── Topbar.vue
│   │   │   ├── SourcesPanel.vue
│   │   │   ├── ChatPanel.vue
│   │   │   ├── StudioPanel.vue
│   │   │   └── SettingsModal.vue
│   │   ├── services/
│   │   │   └── api.js
│   │   ├── main.js
│   │   └── style.css
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
│
├── data/                         # Runtime data
│   ├── faiss_index/              # FAISS index files
│   ├── rag_config.json           # RAG configuration
│   └── settings.json             # LLM settings
│
├── media/data_source/            # Uploaded PDFs
├── tests/                        # Pytest tests
├── .env                          # Environment variables
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
└── manage.py                     # Django management
```

## Prerequisites

- Python 3.11+ recommended
- Node.js 18+ (for frontend)
- pip / virtual environment

## Setup

### 1. Backend dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment variables

Create `.env` in the project root:

```env
# App
APP_NAME=Lecture Note Q&A System
APP_VERSION=1.0.0
DJANGO_SECRET_KEY=change-me-in-production
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Chunking
CHUNK_SIZE=400
CHUNK_OVERLAP=50

# Embeddings / Vector store
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
FAISS_INDEX_PATH=data/faiss_index
DOCUMENTS_PATH=media/data_source
MAX_UPLOAD_SIZE=10485760
UPLOAD_INDEXING_STRATEGY=full_rebuild
UPLOAD_INDEXING_ASYNC=true

# LLM provider config
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
```

Notes:

- `DEBUG` accepts `true/false`, and also `dev/debug` or `release/prod`.
- You can also set provider/model/API key from the UI settings panel.

### 3. Run backend

```bash
python manage.py runserver 0.0.0.0:8000
```

Backend endpoints:

- API root: `http://localhost:8000/`
- Health: `http://localhost:8000/health`

### 4. Run frontend (optional)

```bash
cd frontend
npm install
npm run dev
```

The frontend dev server runs at `http://localhost:5173` and proxies `/api` requests to the Django backend.

**Production build:**

```bash
cd frontend
npm run build
```

Build output is configured to `django_app/static/frontend/` for Django integration.

## API Reference

### `POST /api/upload`

Upload a PDF, save it to disk, and trigger indexing.

- Content type: `multipart/form-data`
- Field: `file` (PDF only, max 10MB by default)
- Default mode: full rebuild in background (`UPLOAD_INDEXING_STRATEGY=full_rebuild`)

Success response:

```json
{
  "success": true,
  "message": "File uploaded. Full reindex is running in background.",
  "filename": "uuid_original.pdf",
  "saved_path": "/abs/path/to/media/data_source/uuid_original.pdf",
  "indexing_mode": "full_rebuild",
  "indexing_status": "queued"
}
```

Synchronous mode response (when `UPLOAD_INDEXING_ASYNC=false`):

```json
{
  "success": true,
  "message": "PDF uploaded and indexed successfully",
  "filename": "uuid_original.pdf",
  "saved_path": "/abs/path/to/media/data_source/uuid_original.pdf",
  "indexing_mode": "full_rebuild",
  "indexing_status": "completed",
  "chunks_created": 42,
  "total_chunks_in_index": 420
}
```

### `GET /api/upload/status`

Check background indexing progress.

### `GET /api/files`

List all uploaded PDF files.

Response:

```json
{
  "files": [
    {
      "name": "lecture1.pdf",
      "size": 1234567,
      "created_at": "2024-01-15T10:30:00+00:00"
    }
  ]
}
```

### `POST /api/documents/delete`

Delete a PDF file and rebuild the index.

Request:

```json
{
  "filename": "lecture1.pdf"
}
```

### `POST /api/chat`

Ask a question against indexed lecture content.

Request:

```json
{
  "query": "What is gradient descent?"
}
```

Response:

```json
{
  "answer": "Gradient descent is ...",
  "sources": ["lecture1.pdf", "lecture2.pdf"]
}
```

### `POST /api/ask`

Alternative chat endpoint (legacy, same as `/api/chat`).

### `GET /api/settings`

Returns persisted UI settings (provider/model, API key presence).

### `POST /api/settings`

Update LLM settings.

Request:

```json
{
  "provider": "gemini",
  "model": "gemini-2.0-flash",
  "api_key": "optional_key"
}
```

### `GET /api/rag-config`

Get RAG configuration (top_k, temperature, etc.).

### `POST /api/rag-config/update`

Update RAG configuration.

### `POST /api/index/reset`

Reset/clear the FAISS index.

## Development Commands

### Backend

```bash
# Run server
python manage.py runserver 0.0.0.0:8000

# Tests
pytest tests/
pytest tests/test_services.py

# Lint / format / type-check
ruff check app/ django_app/ django_backend/ manage.py
black app/ django_app/ django_backend/ manage.py
mypy app/ django_app/ django_backend/
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Development server
npm run dev

# Production build
npm run build

# Lint
npm run lint
```

## Data and Persistence

- **Uploaded files**: `media/data_source/`
- **Vector index**: `data/faiss_index/`
  - `index.faiss` - FAISS index file
  - `chunks.npy` - Chunk metadata
- **Settings**: `data/settings.json`, `data/rag_config.json`
- **Database**: `data/db.sqlite3` (Django SQLite)

## Configuration

### Environment Variables (.env)

```bash
# App
APP_NAME=Lecture Note Q&A System
APP_VERSION=1.0.0
DJANGO_SECRET_KEY=change-me-in-production
HOST=0.0.0.0
PORT=8000
DEBUG=true

# Chunking
CHUNK_SIZE=400
CHUNK_OVERLAP=50

# Embeddings / Vector store
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
EMBEDDING_DIM=384
FAISS_INDEX_PATH=data/faiss_index
DOCUMENTS_PATH=media/data_source
MAX_UPLOAD_SIZE=10485760
UPLOAD_INDEXING_STRATEGY=full_rebuild
UPLOAD_INDEXING_ASYNC=true

# LLM provider config
LLM_PROVIDER=gemini
GEMINI_API_KEY=your_gemini_key
GEMINI_MODEL=gemini-2.5-flash
GEMINI_BASE_URL=https://generativelanguage.googleapis.com/v1beta

OPENROUTER_API_KEY=your_openrouter_key
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1

# Local Qwen (llama.cpp)
LOCAL_QWEN_MODEL=qwen2.5:3b
LOCAL_QWEN_BASE_URL=http://localhost:8080
LOCAL_QWEN_TIMEOUT_SECONDS=300
LOCAL_QWEN_KEEP_ALIVE=30m
```

### RAG Configuration (data/rag_config.json)

```json
{
  "llm_model": "qwen2.5:3b",
  "top_k": 3,
  "temperature": 0.7
}
```

## Notes and Limitations

- PDFs must be text-based (no image-only PDFs)
- FAISS uses `IndexFlatL2` for cosine-like similarity
- Default indexing strategy: full rebuild on upload
- Async indexing supported via background thread
- Settings can be configured via UI or environment variables

## License

Add your project license here (for example, MIT).