# Spec: Hybrid RAG Pipeline Flowchart

## Goal
To document and visualize the end-to-end hybrid Retrieval-Augmented Generation (RAG) pipeline used in the AI-Based Lecture Note Q&A System, highlighting both the offline ingestion/indexing phase and the online query/retrieval phase.

## User Review Required
No breaking changes or significant deviations. The flowchart will be written using Mermaid markdown syntax in a dedicated document `docs/rag_flowchart.md` for easy viewing in Git platforms and Markdown renderers.

## Proposed Output File
### [NEW] [rag_flowchart.md](file:///C:/Users/wongs/Documents/GitHub/AI-Based-Lecture-Note-Question-Answering-System-Using-Retrieval-Augmented-Generation-RAG-/docs/rag_flowchart.md)

This file will contain:
1. A brief overview of the project's RAG system.
2. A unified Mermaid diagram showing Phase 1 (Ingestion) and Phase 2 (Query & Retrieval).
3. Stage-by-stage descriptions mapping to the actual code files (e.g., `app/services/` and `retrieval/`).

## Diagram Technical Details
- **Syntax:** Mermaid `graph TD` (top-down flowchart).
- **Styling:** restained color tokens mapping to the functional components (Process: `#DDEBF7`, Database: `#FFF2CC`, Input/Output: `#F8CECC`, Fusion: `#D5E8D4`).
- **Phases:** Clear visual separation using Mermaid subgraphs:
  - `subgraph Ingestion_Pipeline`
  - `subgraph Query_Pipeline`
