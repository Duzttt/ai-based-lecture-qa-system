# Hybrid RAG Pipeline Flowchart

This document provides a detailed visual representation and explanation of the hybrid Retrieval-Augmented Generation (RAG) pipeline implemented in this project.

## Workflow Flowchart

```mermaid
graph TD
    %% Styling
    classDef process fill:#DDEBF7,stroke:#2F75B5,stroke-width:2px,color:#000000;
    classDef database fill:#FFF2CC,stroke:#D6B656,stroke-width:2px,color:#000000;
    classDef io fill:#F8CECC,stroke:#B85450,stroke-width:2px,color:#000000;
    classDef fusion fill:#D5E8D4,stroke:#82B366,stroke-width:2px,color:#000000;

    subgraph Ingestion_Pipeline["Phase 1: Ingestion & Indexing (Offline)"]
        A[Raw Lecture Notes: PDF/PPT/Image]:::io --> B[Text Extraction: pdfplumber / OCR]:::process
        B --> C[Text Normalization & Cleaning]:::process
        C --> D["Smart Chunking: 500 chars (100 char overlap)"]:::process
        
        D --> E["Dense Vector Pipeline\n(MiniLM Embeddings - 384d)"]:::process
        D --> F["Sparse Keyword Pipeline\n(BM25 Text Tokenization)"]:::process
        
        E --> G["FAISS Vector Store\nindex.faiss + metadata.pkl"]:::database
        F --> H[BM25 Index Store]:::database
    end

    subgraph Query_Pipeline["Phase 2: Query & Retrieval (Online/Runtime)"]
        Q[User Question / Query]:::io --> Q_Emb["Query Vectorization\nMiniLM Embedding"]:::process
        Q --> R_Sparse["Sparse Retrieval\n(Top-20 Keyword Chunks)"]:::process
        Q_Emb --> R_Dense["Dense Retrieval\n(Top-20 Semantic Chunks)"]:::process
        
        G --> R_Dense
        H --> R_Sparse
        
        R_Dense --> RRF["Reciprocal Rank Fusion (RRF)\n(k = 60)"]:::fusion
        R_Sparse --> RRF
        
        RRF --> Top_5["Top-5 Re-ranked Chunks\nwith Source Citations"]:::process
        Top_5 --> Prompt["Prompt Construction\n(Context + Grounding Rules)"]:::process
        Q --> Prompt
        
        Prompt --> LLM["LLM Inference\n(Gemini / OpenRouter / llama.cpp)"]:::process
        LLM --> Ans["Grounded Answer + Page Citations\n(e.g., 'See Page 3')"]:::io
    end
```

## Detailed Phase Reference

### Phase 1: Ingestion & Indexing
1. **Raw Lecture Notes:** The pipeline supports digital/scanned PDFs and image formats.
2. **Text Extraction:** Implemented in [pdf_loader.py](../app/services/pdf_loader.py).
3. **Smart Chunking:** Text is split using character boundaries of 500 characters with a 100-character overlap to maximize recall and citation accuracy. Implemented in [chunker.py](../app/services/chunker.py) and [pdf_chunking.py](../app/services/pdf_chunking.py).
4. **Dense Vector Pipeline:** Embeddings are generated using `sentence-transformers` (`all-MiniLM-L6-v2`) in [embedding.py](../app/services/embedding.py) and saved to FAISS using [vector_store.py](../app/services/vector_store.py).
5. **Sparse Keyword Pipeline:** Chunks are indexed in a BM25 model implemented in [bm25_index.py](../retrieval/bm25_index.py).

### Phase 2: Query & Retrieval
1. **Query Vectorization:** Converts the user query to a 384d vector using [embedding.py](../app/services/embedding.py).
2. **Dense & Sparse Retrieval:** Executed in parallel in [dense_retriever.py](../retrieval/dense_retriever.py) and [bm25_index.py](../retrieval/bm25_index.py) (orchestrated by [hybrid_retriever.py](../retrieval/hybrid_retriever.py)).
3. **Reciprocal Rank Fusion (RRF):** Fuses ranking scores using $RRF = \frac{1}{60 + \text{rank}}$ implemented in [hybrid_retriever.py](../retrieval/hybrid_retriever.py).
4. **LLM Generation:** Uses system prompting constraints to limit hallucination and ensure grounded answers. Orchestrated via [local_rag.py](../app/services/local_rag.py) and [rag_pipeline.py](../app/services/rag_pipeline.py).
