# RAGAS Evaluation Flowchart Design

## Purpose

Create a detailed, editable Draw.io flowchart (.drawio format) that illustrates the RAGAS evaluation pipeline of the educational Lecture Note Q&A system. This flowchart will serve as documentation in academic/technical reports and show the sequence of operations from initial inputs to the final RAGAS metrics output.

## Layout

The diagram uses a portrait layout with a top-to-bottom vertical flow. It contains eight distinct stages connected by clear directional connectors.

## Stage Details

1. **Input Sources** (Input/Output color)
   - Inputs: Raw PDF Lecture Notes (in `media/data_source/`) OR pre-defined evaluation dataset in JSONL format.
2. **Text Preparation & Smart Chunking** (Preparation color)
   - Processes: Text extraction via `PDFLoader` -> Split into 500-character chunks with 100-character overlap.
3. **QA Pair Generation (LLM-based)** (Preparation color)
   - Processes: Prompt generator LLM (Gemini/Qwen) to generate `{question, ground_truth}` pairs -> Export as JSONL.
4. **Hybrid Retrieval Engine** (RAG Pipeline color)
   - Processes: Dense retrieval (FAISS) + Sparse keyword retrieval (BM25) -> Reciprocal Rank Fusion (RRF, `k=60`) -> Extract top `top_k` chunks as context.
5. **Answer Generation** (RAG Pipeline color)
   - Processes: Format retrieved context and question -> Query generator LLM (local Llama.cpp / Gemini) -> Generate answer.
6. **Dataset Assembly** (RAG Pipeline color)
   - Processes: Compile matching `question`, `contexts` (retrieved chunks), `answer` (generated response), and `ground_truth` into Hugging Face Dataset format.
7. **RAGAS Evaluation Engine** (Evaluation color)
   - Processes: Initialize RAGAS `evaluate()` -> Wrap judge LLM (DeepSeek/Gemini/local Llama.cpp via `ChatOpenAI`) and local MiniLM embeddings. Calculate four RAGAS metrics:
     - **Faithfulness**: Grounding of answer in retrieved contexts.
     - **Answer Relevancy**: Relevance of answer to question.
     - **Context Precision**: Correct ranking of retrieved contexts.
     - **Context Recall**: Alignment of contexts with ground truth.
8. **Evaluation Output Reports** (Input/Output color)
   - Outputs: Write full results to CSV report + Print overall metrics summary.

## Visual Design System (Draw.io XML Style)

- **Canvas**: Portrait layout.
- **Font**: Arial or Helvetica, clean and readable.
- **Colors**:
  - **Input/Output (Stages 1 & 8)**: Muted Grey (`fillColor=#F5F5F7`, `strokeColor=#86868B`).
  - **Preparation (Stages 2 & 3)**: Muted Orange/Yellow (`fillColor=#FEF3C7`, `strokeColor=#F59E0B`).
  - **RAG System (Stages 4, 5 & 6)**: Muted Blue (`fillColor=#DDEBF7`, `strokeColor=#2F75B5`).
  - **RAGAS Evaluation (Stage 7)**: Muted Teal/Green (`fillColor=#CCFBF1`, `strokeColor=#0D9488`).
- **Connectors**: Dark grey solid arrows pointing downwards (`strokeColor=#667085`, `strokeWidth=2`).

## Deliverable

- File: `report/ragas_evaluation_flowchart.drawio`
- Editable XML diagram loadable directly in Draw.io (online or desktop app).
