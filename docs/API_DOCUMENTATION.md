# RAG System Phase 1 Optimization - API Documentation & Integration Guide

## Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Quick Start](#quick-start)
4. [API Reference](#api-reference)
5. [Integration Guide](#integration-guide)
6. [Configuration](#configuration)
7. [Examples](#examples)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Phase 1 optimization adds **hybrid search** and **intelligent chunking** to the RAG system:

### New Components

| Component | File | Description |
|-----------|------|-------------|
| **BM25Index** | `retrieval/bm25_index.py` | Keyword-based retrieval with Chinese support |
| **DenseRetriever** | `retrieval/dense_retriever.py` | Vector-based semantic search using FAISS |
| **HybridRetriever** | `retrieval/hybrid_retriever.py` | Combined retrieval (RRF or Weighted fusion) |
| **SmartChunker** | `chunking/smart_chunker.py` | Semantic-aware document splitting |
| **RetrievalEvaluator** | `evaluation/retrieval_evaluator.py` | Evaluation metrics (Recall, MRR, NDCG) |
| **PerformanceMonitor** | `evaluation/performance_monitor.py` | Real-time performance tracking |

---

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

New dependencies added:
- `rank-bm25==0.2.2` - BM25 implementation
- `scikit-learn==1.3.2` - ML utilities

### 2. Verify Installation

```bash
python -c "from retrieval import HybridRetriever; print('Installation OK')"
```

---

## Quick Start

### Basic Hybrid Retrieval

```python
from retrieval import HybridRetriever, FusionMethod

# Sample documents
documents = [
    {"id": "doc1", "text": "机器学习是人工智能的一个分支"},
    {"id": "doc2", "text": "深度学习使用神经网络进行建模"},
    {"id": "doc3", "text": "自然语言处理涉及语言交互"},
]

# Initialize retriever
retriever = HybridRetriever(
    documents=documents,
    fusion_method=FusionMethod.RRF
)

# Search
results = retriever.retrieve("什么是机器学习", top_k=3)

for result in results:
    print(f"{result['id']}: {result['text'][:50]}... (score: {result['score']:.4f})")
```

### Smart Chunking

```python
from chunking import SmartChunker

# Initialize chunker
chunker = SmartChunker(chunk_size=500, overlap=100)

# Load document
with open("lecture_notes.txt", "r", encoding="utf-8") as f:
    text = f.read()

# Chunk document
chunks = chunker.chunk_document(
    text,
    metadata={"source": "lecture_notes.pdf"},
    extract_keywords=True
)

print(f"Created {len(chunks)} chunks")
print(f"First chunk keywords: {chunks[0]['keywords']}")
```

---

## API Reference

### BM25Index

```python
class BM25Index:
    """BM25 索引，支持中文分词"""
    
    def __init__(self, documents: List[Dict[str, Any]]):
        """
        Args:
            documents: List of dicts with 'id' and 'text' keys
        """
    
    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Search BM25 index.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            
        Returns:
            List of (doc_id, score) tuples
        """
    
    def get_scores(self, query: str) -> Dict[str, float]:
        """Get BM25 scores for all documents."""
    
    def get_document_count(self) -> int:
        """Get number of indexed documents."""
    
    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """Rebuild index with new documents."""
```

### DenseRetriever

```python
class DenseRetriever:
    """向量检索器，使用 FAISS"""
    
    def __init__(
        self,
        documents: List[Dict[str, Any]],
        embedder: SentenceTransformer = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    ):
        """
        Args:
            documents: List of dicts with 'id' and 'text' keys
            embedder: Optional pre-loaded SentenceTransformer model
            model_name: Model name if embedder not provided
        """
    
    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Search dense vector index.
        
        Args:
            query: Search query string
            top_k: Number of results to return
            
        Returns:
            List of (doc_id, cosine_similarity) tuples
        """
    
    def add_documents(self, new_documents: List[Dict[str, Any]]) -> None:
        """Add documents to existing index."""
    
    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """Rebuild index with new documents."""
```

### HybridRetriever

```python
class HybridRetriever:
    """混合检索器，结合 BM25 和向量检索"""
    
    def __init__(
        self,
        documents: List[Dict[str, Any]],
        embedder: SentenceTransformer = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        fusion_method: FusionMethod = FusionMethod.RRF
    ):
        """
        Args:
            documents: List of dicts with 'id', 'text', optional 'metadata'
            embedder: Optional pre-loaded SentenceTransformer model
            model_name: Model name if embedder not provided
            fusion_method: 'rrf' or 'weighted'
        """
    
    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        fusion_method: FusionMethod = None,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_k: int = 60,
        alpha: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Hybrid retrieval.
        
        Args:
            query: Search query
            top_k: Final number of results
            fusion_method: Override default fusion method
            bm25_top_k: BM25 candidate count
            dense_top_k: Dense retrieval candidate count
            rrf_k: RRF constant
            alpha: Dense weight for weighted fusion
            
        Returns:
            List of result dicts with keys:
            - id: Document ID
            - text: Document text
            - score: Fused score
            - source: Document source
            - metadata: Document metadata
        """
    
    def retrieve_with_scores(
        self,
        query: str,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Retrieve with detailed score breakdown.
        
        Returns:
            Dict with keys:
            - results: List of result documents
            - bm25_scores: Dict of BM25 scores
            - dense_scores: Dict of dense scores
            - fused_scores: Dict of fused scores
        """
```

### SmartChunker

```python
class SmartChunker:
    """智能文档分块器"""
    
    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 100,
        min_paragraph_size: int = 100,
        max_paragraph_size: int = 800
    ):
        """
        Args:
            chunk_size: Target chunk size in characters
            overlap: Overlap size in characters
            min_paragraph_size: Min paragraph size before merging
            max_paragraph_size: Max paragraph size before splitting
        """
    
    def chunk_document(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
        extract_keywords: bool = True,
        top_k_keywords: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Chunk a document.
        
        Args:
            text: Document text
            metadata: Document metadata
            extract_keywords: Whether to extract keywords
            top_k_keywords: Number of keywords to extract
            
        Returns:
            List of chunk dicts with keys:
            - text: Chunk text
            - metadata: Document metadata
            - position: Chunk position (0-indexed)
            - total_chunks: Total number of chunks
            - start_char: Start position in original text
            - end_char: End position in original text
            - headings: List of section headings
            - keywords: List of extracted keywords
        """
```

### RetrievalEvaluator

```python
class RetrievalEvaluator:
    """检索评估器"""
    
    def __init__(
        self,
        test_queries: List[Dict[str, Any]],
        relevant_docs: Dict[str, List[str]] = None
    ):
        """
        Args:
            test_queries: List of query dicts with 'id', 'query', 'expected_doc_ids'
            relevant_docs: Optional mapping of query_id to relevant doc_ids
        """
    
    def evaluate(
        self,
        retriever: Any,
        top_k: int = 10
    ) -> Tuple[AggregateMetrics, List[EvaluationResult]]:
        """
        Evaluate retriever performance.
        
        Returns:
            Tuple of (aggregate_metrics, per_query_results)
        """
    
    def compare(
        self,
        retrievers: Dict[str, Any]
    ) -> Dict[str, AggregateMetrics]:
        """Compare multiple retrievers."""
    
    def generate_report(
        self,
        aggregate: AggregateMetrics,
        results: List[EvaluationResult]
    ) -> str:
        """Generate text report."""
```

### PerformanceMonitor

```python
class PerformanceMonitor:
    """实时性能监控"""
    
    def __init__(self, window_size: int = 1000):
        """
        Args:
            window_size: Number of queries to track
        """
    
    def record_query(
        self,
        query: str,
        latency: float,
        cache_hit: bool = False,
        bm25_latency: float = 0.0,
        dense_latency: float = 0.0,
        fusion_latency: float = 0.0,
        num_results: int = 0
    ) -> QueryRecord:
        """Record a query's performance."""
    
    def get_metrics(self) -> PerformanceMetrics:
        """Get aggregated performance metrics."""
    
    def get_report(self) -> str:
        """Generate performance report."""
    
    def check_latency_threshold(
        self,
        threshold_ms: float = 200.0,
        percentile: float = 0.95
    ) -> bool:
        """Check if latency exceeds threshold."""
```

---

## Integration Guide

### Integrating with Existing RAG Pipeline

#### Step 1: Replace VectorStore with HybridRetriever

**Before** (existing code):
```python
from app.services.vector_store import VectorStore
from app.services.embedding import EmbeddingService

embedding_service = EmbeddingService()
vector_store = VectorStore.get_cached("data/faiss_index")

# Search
query_embedding = embedding_service.embed_query("question")
results = vector_store.search_with_metadata(query_embedding, top_k=5)
```

**After** (with hybrid retrieval):
```python
from retrieval import HybridRetriever, FusionMethod

# Prepare documents from your chunks
documents = [
    {"id": f"chunk_{i}", "text": chunk.text, "metadata": chunk.metadata}
    for i, chunk in enumerate(chunks)
]

# Initialize hybrid retriever
retriever = HybridRetriever(
    documents=documents,
    fusion_method=FusionMethod.RRF
)

# Search (no embedding needed - handled internally)
results = retriever.retrieve("question", top_k=5)
```

#### Step 2: Update Indexing Pipeline

**Before**:
```python
from app.services.pdf_indexing import index_pdf_file

result = index_pdf_file(
    pdf_path="lecture.pdf",
    chunk_size=400,
    index_path="data/faiss_index",
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    clear_existing=True
)
```

**After** (with smart chunking):
```python
from chunking import SmartChunker
from retrieval import HybridRetriever, FusionMethod
from app.services.pdf_loader import PDFLoader

# Load PDF
loader = PDFLoader()
text = loader.load("lecture.pdf")

# Smart chunking
chunker = SmartChunker(chunk_size=500, overlap=100)
chunks = chunker.chunk_document(
    text,
    metadata={"source": "lecture.pdf"},
    extract_keywords=True
)

# Build hybrid index
documents = [
    {"id": f"chunk_{i}", "text": c["text"], "metadata": c["metadata"]}
    for i, c in enumerate(chunks)
]

retriever = HybridRetriever(documents, fusion_method=FusionMethod.RRF)
# Retriever is ready to use (no separate index saving needed)
```

#### Step 3: Update Chat/Ask Endpoint

**Before**:
```python
# django_app/views.py
from app.services.embedding import EmbeddingService
from app.services.vector_store import VectorStore

def ask_question(request):
    query = request.json.get("query")
    
    embedding_service = EmbeddingService()
    vector_store = VectorStore.get_cached("data/faiss_index")
    
    query_embedding = embedding_service.embed_query(query)
    results = vector_store.search_with_metadata(query_embedding, top_k=5)
    
    context = "\n".join([r["text"] for r in results])
    # ... send to LLM
```

**After**:
```python
# django_app/views.py
from retrieval import HybridRetriever

# Global retriever (initialized once)
_retriever: HybridRetriever = None

def get_retriever():
    global _retriever
    if _retriever is None:
        # Load from your document store
        documents = load_documents()  # Your function
        _retriever = HybridRetriever(documents)
    return _retriever

def ask_question(request):
    query = request.json.get("query")
    
    retriever = get_retriever()
    results = retriever.retrieve(query, top_k=5)
    
    context = "\n".join([r["text"] for r in results])
    # ... send to LLM
```

### Integration with Django Backend

Create a new management command for building the hybrid index:

```python
# django_app/management/commands/build_hybrid_index.py
from django.core.management.base import BaseCommand
from retrieval import HybridRetriever, FusionMethod
from chunking import SmartChunker
import json
import os

class Command(BaseCommand):
    help = "Build hybrid retrieval index"

    def add_arguments(self, parser):
        parser.add_argument(
            "--documents-path",
            type=str,
            default="media/data_source",
        )
        parser.add_argument(
            "--output-path",
            type=str,
            default="data/hybrid_index.json",
        )

    def handle(self, *args, **options):
        documents_path = options["documents_path"]
        output_path = options["output_path"]

        # Load and chunk documents
        all_chunks = []
        for filename in os.listdir(documents_path):
            if filename.endswith(".pdf"):
                filepath = os.path.join(documents_path, filename)
                # Load and chunk
                # ... your loading logic
                chunks = chunk_document(filepath)  # Your function
                all_chunks.extend(chunks)

        # Build documents list
        documents = [
            {"id": f"chunk_{i}", "text": c["text"], "metadata": c["metadata"]}
            for i, c in enumerate(all_chunks)
        ]

        # Build retriever (this builds both BM25 and dense indices)
        retriever = HybridRetriever(documents, fusion_method=FusionMethod.RRF)

        # Save index metadata
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump({
                "num_documents": len(documents),
                "num_chunks": len(all_chunks),
            }, f, indent=2)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully built hybrid index with {len(documents)} documents"
            )
        )
```

---

## Configuration

### Configuration File

Create `config/retrieval_config.json`:

```json
{
  "chunking": {
    "chunk_size": 500,
    "overlap": 100,
    "min_paragraph_size": 100,
    "max_paragraph_size": 800,
    "extract_keywords": true,
    "top_k_keywords": 5
  },
  "retrieval": {
    "fusion_method": "rrf",
    "rrf_k": 60,
    "alpha": 0.3,
    "top_k": 10,
    "bm25_top_k": 20,
    "dense_top_k": 20,
    "embedding_model": "sentence-transformers/all-MiniLM-L6-v2"
  },
  "evaluation": {
    "compute_recall": true,
    "compute_precision": true,
    "compute_mrr": true,
    "compute_ndcg": true
  }
}
```

### Using Configuration Manager

```python
from config import ConfigManager

# Load configuration
config_manager = ConfigManager("config/retrieval_config.json")

# Get values
chunk_size = config_manager.get("chunking.chunk_size")
fusion_method = config_manager.get("retrieval.fusion_method")

# Update values
config_manager.set("retrieval.top_k", 15)
config_manager.save()
```

---

## Examples

### Example 1: Multi-Document Search

```python
from retrieval import HybridRetriever, FusionMethod
from chunking import SmartChunker

# Load multiple documents
documents = []
for i, pdf_path in enumerate(["lecture1.pdf", "lecture2.pdf", "lecture3.pdf"]):
    text = load_pdf(pdf_path)  # Your PDF loader
    
    chunker = SmartChunker(chunk_size=500, overlap=100)
    chunks = chunker.chunk_document(
        text,
        metadata={"source": pdf_path, "lecture": i + 1}
    )
    
    for chunk in chunks:
        documents.append({
            "id": f"lec{i+1}_chunk{chunk['position']}",
            "text": chunk["text"],
            "metadata": chunk["metadata"]
        })

# Build hybrid index
retriever = HybridRetriever(documents, fusion_method=FusionMethod.RRF)

# Search across all documents
results = retriever.retrieve("什么是梯度下降", top_k=10)

# Group results by source
from collections import defaultdict
by_source = defaultdict(list)
for r in results:
    by_source[r["metadata"].get("source", "unknown")].append(r)

for source, source_results in by_source.items():
    print(f"\n{source}: {len(source_results)} results")
```

### Example 2: Evaluation Pipeline

```python
from evaluation import RetrievalEvaluator
from retrieval import HybridRetriever, BM25Index, DenseRetriever

# Define test queries
test_queries = [
    {
        "id": "q1",
        "query": "什么是机器学习",
        "expected_doc_ids": ["doc1", "doc2"]
    },
    {
        "id": "q2",
        "query": "深度学习",
        "expected_doc_ids": ["doc3", "doc4"]
    },
    # ... more queries
]

# Initialize retrievers
bm25 = BM25Index(documents)
dense = DenseRetriever(documents)
hybrid = HybridRetriever(documents)

# Create evaluator
evaluator = RetrievalEvaluator(test_queries)

# Evaluate each retriever
print("Evaluating BM25...")
bm25_metrics, _ = evaluator.evaluate(bm25)

print("Evaluating Dense...")
dense_metrics, _ = evaluator.evaluate(dense)

print("Evaluating Hybrid...")
hybrid_metrics, _ = evaluator.evaluate(hybrid)

# Compare
print("\nComparison:")
print(f"BM25 Recall@5:   {bm25_metrics.avg_recall_at_5:.4f}")
print(f"Dense Recall@5:  {dense_metrics.avg_recall_at_5:.4f}")
print(f"Hybrid Recall@5: {hybrid_metrics.avg_recall_at_5:.4f}")
```

### Example 3: Performance Monitoring

```python
from evaluation import PerformanceMonitor, LatencyTracker
from retrieval import HybridRetriever

# Initialize
retriever = HybridRetriever(documents)
monitor = PerformanceMonitor(window_size=1000)

# Monitor queries
queries = ["query1", "query2", "query3"]

for query in queries:
    with LatencyTracker() as tracker:
        results = retriever.retrieve(query, top_k=5)
    
    monitor.record_query(
        query=query,
        latency=tracker.elapsed_ms,
        num_results=len(results)
    )

# Get report
print(monitor.get_report())

# Check if latency is acceptable
if monitor.check_latency_threshold(threshold_ms=200.0, percentile=0.95):
    print("WARNING: P95 latency exceeds 200ms!")
```

---

## Troubleshooting

### Common Issues

#### Issue 1: BM25 Search Returns Poor Results

**Symptom**: BM25 search returns poor results for queries

**Solution**:
```bash
# Verify rank-bm25 installation
python -c "from rank_bm25 import BM25Okapi; print('OK')"
```

#### Issue 2: FAISS Index Build Fails

**Symptom**: `DenseRetrieverError: Failed to build dense index`

**Solution**:
```bash
# Verify FAISS installation
python -c "import faiss; print(faiss.__version__)"

# Check embedding model
python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('all-MiniLM-L6-v2'); print(m.get_sentence_embedding_dimension())"
```

#### Issue 3: Hybrid Retrieval Too Slow

**Symptom**: Query latency > 500ms

**Solution**:
1. Reduce `bm25_top_k` and `dense_top_k` (e.g., from 20 to 10)
2. Enable caching for frequent queries
3. Use GPU for dense retrieval if available

```python
# Optimized configuration
retriever = HybridRetriever(
    documents,
    bm25_top_k=10,
    dense_top_k=10,
    top_k=5
)
```

#### Issue 4: Out of Memory

**Symptom**: Memory error when building index for large document sets

**Solution**:
```python
# Use incremental indexing
from retrieval import DenseRetriever

# Start with empty index
retriever = DenseRetriever(documents[:1000])

# Add more documents in batches
for i in range(1000, len(documents), 1000):
    batch = documents[i:i+1000]
    retriever.add_documents(batch)
```

### Performance Tuning Guide

| Parameter | Increase | Decrease | Effect |
|-----------|----------|----------|--------|
| `chunk_size` | More context per chunk | Less context | Affects retrieval granularity |
| `overlap` | Better context preservation | Less memory | Affects information completeness |
| `bm25_top_k` | Better recall | Faster | More candidates for fusion |
| `dense_top_k` | Better recall | Faster | More candidates for fusion |
| `rrf_k` | More weight to lower ranks | More weight to top ranks | Affects fusion behavior |
| `alpha` | More dense influence | More BM25 influence | Balance between methods |

---

## Support

For issues or questions:
1. Check the [EVALUATION_REPORT.md](./EVALUATION_REPORT.md) for performance benchmarks
2. Run the benchmark script: `python tests/benchmark.py`
3. Review unit tests for usage examples

---

**Documentation Version**: 1.0.0  
**Last Updated**: March 9, 2026
