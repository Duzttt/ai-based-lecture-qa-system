# RAG Architecture Documentation - Lecture Note Q&A System

**Generated:** 2026-03-09  
**Purpose:** Comprehensive architecture map for RAG feature implementation

---

## 1. Architecture Overview

### System Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND (Vue 3 + Vite)                        │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │   Topbar    │  │ SourcesPanel │  │  ChatPanel  │  │  StudioPanel    │   │
│  └─────────────┘  └──────────────┘  └─────────────┘  └─────────────────┘   │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────┐  ┌─────────────────┐   │
│  │ComparisonVw │  │DashboardPanel│  │SettingsModal│  │QuestionSuggestions│ │
│  └─────────────┘  └──────────────┘  └─────────────┘  └─────────────────┘   │
│         │                  │                │                  │            │
│         └──────────────────┴────────────────┴──────────────────┘            │
│                                    │                                        │
│                            api.js (Axios)                                   │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │ HTTP/REST + WebSocket
┌────────────────────────────────────┼────────────────────────────────────────┐
│                         DJANGO BACKEND (5.2)                                │
│  ┌─────────────────────────────────┴──────────────────────────────────┐    │
│  │                      django_backend/ (Project Config)               │    │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌──────────────┐ │    │
│  │  │ settings.py│  │  urls.py   │  │  asgi.py   │  │ routing.py   │ │    │
│  │  └────────────┘  └────────────┘  └────────────┘  └──────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────┴──────────────────────────────────┐    │
│  │                        django_app/ (App Layer)                      │    │
│  │  ┌──────────────────────────────────────────────────────────────┐  │    │
│  │  │                    views.py (API Endpoints)                   │  │    │
│  │  └──────────────────────────────────────────────────────────────┘  │    │
│  │  ┌────────────┐  ┌──────────────────────────────────────────────┐ │    │
│  │  │ models.py  │  │              consumers.py                     │ │    │
│  │  └────────────┘  └──────────────────────────────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│         ┌──────────────────────────┴──────────────────────────┐             │
│         │                                                     │             │
│  ┌──────┴──────────┐                               ┌─────────┴─────────┐   │
│  │  app/services/  │                               │   retrieval/      │   │
│  │  (RAG Pipeline) │                               │ (Hybrid Retrieval)│   │
│  └─────────────────┘                               └───────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Upload Pipeline

```
User → POST /api/upload (FormData)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ django_app/views.py: upload_pdf()                                           │
│  1. Validate file (type, size)                                              │
│  2. Save PDF to media/data_source/                                          │
│  3. Trigger indexing (sync or async background thread)                      │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ app/services/pdf_indexing.py: index_pdf_file() / index_pdf_directory()      │
│  1. read_pdf_text() → pypdf.PdfReader                                       │
│  2. chunk_pdf_with_metadata() → split into chunks with page info            │
│  3. EmbeddingService.embed_texts() → sentence-transformers                  │
│  4. VectorStore.add_embeddings() → FAISS index                              │
│  5. VectorStore.save() → data/faiss_index/{index.faiss, chunks.npy}         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Query Pipeline

```
User → POST /api/chat {query: "...", sources?: [...]}
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ django_app/views.py: ask_qwen()                                             │
│  1. Load RAG config (top_k, llm_model, temperature)                         │
│  2. Call retrieve_with_faiss()                                              │
│  3. Build context from sources                                              │
│  4. Call generate_with_local_qwen()                                         │
│  5. Return {answer, sources, source_snippets, retrieved_chunks}             │
└─────────────────────────────────────────────────────────────────────────────┘
         │
         ├──────────────────────────────────────────────┐
         ▼                                              ▼
┌──────────────────────────┐              ┌──────────────────────────────┐
│ app/services/local_rag.py│              │ app/services/rag_pipeline.py │
│ retrieve_with_faiss():   │              │ RAGPipeline.query():         │
│  1. EmbeddingService     │              │  (Alternative implementation)│
│     .embed_query()       │              │  1. retrieve() → FAISS       │
│  2. VectorStore          │              │  2. generate_answer()        │
│     .search_with_metadata│              │     - Gemini API             │
│  3. Filter by source     │              │     - OpenRouter API         │
│  4. Return top_k results │              └──────────────────────────────┘
└──────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│ app/services/local_rag.py: generate_with_local_qwen()                       │
│  1. Build prompt with context + question                                    │
│  2. Call llama.cpp API (http://localhost:8080/v1/chat/completions)           │
│  3. Parse response                                                          │
│  4. Return answer string                                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory

### Backend RAG Services (`app/services/`)

| File | Class/Function | Responsibility | Connections |
|------|---------------|----------------|-------------|
| **`rag_pipeline.py`** | `RAGPipeline` | Main RAG orchestration | → `EmbeddingService`, `VectorStore`, Gemini/OpenRouter |
| **`vector_store.py`** | `VectorStore` | FAISS vector store | → `faiss`, `numpy` |
| **`embedding.py`** | `EmbeddingService` | Sentence Transformers | → `sentence-transformers` |
| **`embedding_manager.py`** | `EmbeddingModelManager` | Multi-model LRU cache | → `EmbeddingModelCache` |
| **`pdf_indexing.py`** | `index_pdf_file()` | PDF indexing pipeline | → PDF loaders, chunking, embeddings |
| **`pdf_loader.py`** | `PDFLoader` | PDF file handling | → `PyPDFLoader` |
| **`pdf_chunking.py`** | `chunk_pdf_with_metadata()` | Sentence-aware chunking | → Regex sentence splitting |
| **`chunker.py`** | `TextChunker` | LangChain splitter | → `RecursiveCharacterTextSplitter` |
| **`local_rag.py`** | `retrieve_with_faiss()` | FAISS retrieval | → `EmbeddingService`, `VectorStore` |
| **`summarizer.py`** | `DocumentSummarizer` | LLM summarization | → Local Qwen, Gemini |
| **`question_suggestions.py`** | `QuestionSuggestionService` | Generate suggestions | → TF-IDF, LLM |
| **`config.py`** | `Settings` | Pydantic config | → `.env` |

### Retrieval Module (`retrieval/`) - NOT YET INTEGRATED

| File | Class | Status |
|------|-------|--------|
| `dense_retriever.py` | `DenseRetriever` | ✅ Implemented, ❌ Not in views |
| `bm25_index.py` | `BM25Index` | ✅ Implemented, ❌ Not in views |
| `hybrid_retriever.py` | `HybridRetriever` | ✅ Implemented, ❌ Not in views |

### Django API Endpoints (`django_app/views.py`)

| Endpoint | Method | Handler | Purpose |
|----------|--------|---------|---------|
| `/api/upload` | POST | `upload_pdf()` | Upload & index PDF |
| `/api/chat` | POST | `ask_qwen()` | **Primary Q&A endpoint** |
| `/api/ask` | POST | `ask_question()` | Legacy Q&A |
| `/api/files` | GET | `list_files()` | List uploaded PDFs |
| `/api/settings` | GET/POST | `settings_handler()` | LLM config |
| `/api/rag-config` | GET/POST | `get_rag_config()` / `update_rag_config()` | RAG params |
| `/api/dashboard/stats` | GET | `dashboard_stats()` | Index statistics |
| `/api/suggestions` | GET | `get_question_suggestions()` | AI questions |
| `/api/summary/generate` | POST | `generate_summary()` | Summarize docs |

### Frontend Components (`frontend/src/`)

| Component | File | Purpose |
|-----------|------|---------|
| `App.vue` | `src/App.vue` | Main layout |
| `ChatPanel.vue` | `src/components/ChatPanel.vue` | Chat interface |
| `RetrievalChunks.vue` | `src/components/RetrievalChunks.vue` | Show retrieved chunks |
| `SourcesPanel.vue` | `src/components/SourcesPanel.vue` | Document selection |
| `QuestionSuggestions.vue` | `src/components/QuestionSuggestions.vue` | AI suggestions |
| `DashboardPanel.vue` | `src/components/DashboardPanel.vue` | Index status |
| `api.js` | `src/services/api.js` | Axios API client |

---

## 3. Critical Integration Points

### Primary Integration Files

| Integration | Files | Data Flow |
|-------------|-------|-----------|
| **PDF Upload** | `views.upload_pdf()` → `pdf_indexing.index_pdf_file()` → `pdf_chunking.chunk_pdf_with_metadata()` → `embedding.EmbeddingService` → `vector_store.VectorStore` | File → Text → Chunks → Embeddings → FAISS |
| **Query Processing** | `views.ask_qwen()` → `local_rag.retrieve_with_faiss()` → `embedding.EmbeddingService` + `vector_store.VectorStore` | Query → Embedding → FAISS Search → Chunks |
| **Answer Generation** | `views.ask_qwen()` → `local_rag.generate_with_local_qwen()` → llama.cpp API | Context + Query → Prompt → LLM → Answer |
| **Embedding Model Switch** | `views.switch_embedding_model()` → `embedding_manager.EmbeddingModelManager` → Reindex | Model ID → Load → Validate → Reindex |
| **Question Suggestions** | `views.get_question_suggestions()` → `question_suggestions.QuestionSuggestionService` → LLM | Docs → Keywords → Candidates → LLM → Questions |
| **WebSocket Updates** | `consumers.DashboardConsumer` ↔ `views._get_upload_indexing_state()` | State → JSON → WS → Frontend |

---

## 4. Configuration Files

| File | Purpose | Modified By |
|------|---------|-------------|
| `.env` | Environment variables | Manual / `.env.example` |
| `data/rag_config.json` | Runtime RAG params | `/api/rag-config/update` |
| `data/settings.json` | LLM provider config | `/api/settings` POST |
| `data/embedding_model_settings.json` | Active embedding model | `/api/settings/embedding-model/switch` |
| `data/summary_history.json` | Summary history (max 50) | `/api/summary/generate` |
| `django_backend/settings.py` | Django config | Manual |
| `frontend/vite.config.js` | Vite + proxy config | Manual |

---

## 5. TODOs & Incomplete Implementations

### High Priority

1. **Hybrid Retrieval Integration** - `retrieval/` module exists but NOT used by views
   - **Action:** Integrate `HybridRetriever` into `views.ask_qwen()`
   
2. **RAGPipeline Usage** - `app/services/rag_pipeline.py` not used by main views
   - **Action:** Migrate `views.ask_qwen()` to use `RAGPipeline`

3. **Redis Configuration** - Using in-memory channels
   - **Action:** Uncomment Redis config for production

### Medium Priority

4. **Podcast Generation** - Placeholder at line 797 in `views.py`
5. **Quality Metrics** - Requires test set for accuracy
6. **Notebook CRUD** - Model exists, no endpoints
7. **Feedback Collection** - `feedback_score` field unused

### Test Coverage Gaps

- `app/services/summarizer.py` - No tests
- `app/services/question_suggestions.py` - Partial
- `app/services/embedding_manager.py` - No tests
- Dashboard endpoints - No tests
- WebSocket consumers - No tests

---

## 6. Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| **Recall@5** | >75% | ~65% (dense only) |
| **Latency p95** | <200ms | TBD |
| **Cache hit rate** | >60% | TBD |

---

## 7. Key Directories

```
project_root/
├── app/services/          # Core RAG services
├── retrieval/             # Hybrid retrieval (BM25 + Dense) - NOT INTEGRATED
├── chunking/              # Smart chunking module
├── evaluation/            # Metrics & performance monitoring
├── config/                # Configuration management
├── django_app/            # Django app (views, models, consumers)
├── django_backend/        # Django project config
├── frontend/src/          # Vue 3 components
├── data/                  # Runtime data (FAISS, configs, DB)
└── media/data_source/     # Uploaded PDFs
```

---

## 8. Next Steps for Feature Implementation

Before implementing new RAG features:

1. **Decide integration approach:**
   - Use `local_rag.py` (current) or migrate to `rag_pipeline.py`?
   - Integrate hybrid retrieval from `retrieval/` module?

2. **Create todo list** with discrete tasks (backend → frontend → tests)

3. **Check frontend architecture:**
   - Vue 3 components in `frontend/src/components/`
   - Pinia stores for state
   - Axios client in `frontend/src/services/api.js`

4. **Reference existing patterns:**
   - Dashboard panel for real-time stats
   - QuestionSuggestions for AI-generated content
   - SettingsModal for configuration

5. **Run tests after changes:**
   ```bash
   pytest tests/test_hybrid_retrieval.py -v
   python tests/check_retrieval_quality.py "your query"
   ```

---

**End of Architecture Document**
