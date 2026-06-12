# RAG Demo Trace Visualization Design

## Overview

Build a dedicated English-language demo page that visualizes the full Retrieval
Augmented Generation flow for this lecture note Q&A system. The page is designed
for presentations, demos, and project defense sessions where the audience needs
to understand how a question becomes a grounded answer.

The first version will use real backend RAG data, but the frontend will play the
trace back step by step after the backend returns the full trace. This gives the
demo a real-time feel without depending on streaming infrastructure or exposing
the presentation to model latency.

## Goals

- Show the complete RAG flow in a clear, demo-friendly sequence.
- Use real indexed documents, retrieval results, context, and generated answers.
- Keep the visible UI text in English.
- Support a simple default explanation for non-technical viewers.
- Provide a Technical view for scores, latency, ranks, distances, and metadata.
- Allow replaying the most recent trace without re-running the backend.

## Non-Goals

- No SSE or WebSocket streaming in the first version.
- No replacement of the existing chat experience.
- No changes to the core RAG answer prompt or LLM provider routing.
- No new retrieval algorithm beyond reusing the current BM25, dense, and hybrid
  retrieval paths already present in the project.

## User Experience

The page should be reachable as a standalone demo view at `/rag-demo` and also
from a topbar action. It should feel like a presentation console rather than a
normal chat page.

Layout:

```text
[Question input] [Run Demo] [Replay] [Technical view toggle]

Left: RAG flow timeline
  1. User Question
  2. Query Processing
  3. Embedding
  4. BM25 Retrieval
  5. Dense Retrieval
  6. Hybrid Ranking
  7. Context Building
  8. LLM Generation
  9. Final Answer

Center: Active stage explanation
  - Current stage highlighted
  - Short English explanation
  - Stage-specific values or previews

Right: Evidence and technical details
  - Default mode: sources, pages, selected snippets
  - Technical view: scores, distances, rank details, timings, context length
```

Playback behavior:

1. The user enters a question and clicks `Run Demo`.
2. The frontend calls the trace endpoint.
3. After the full trace returns, the frontend animates each stage in sequence.
4. Each stage remains visible for a minimum readable duration, even if the real
   backend step was very fast.
5. `Replay` replays the most recent trace without another backend call.
6. `Technical view` toggles detailed retrieval and performance fields.

## Backend API

Add a dedicated endpoint:

```text
POST /api/rag-demo/trace
```

Request shape:

```json
{
  "query": "What is retrieval augmented generation?",
  "sources": ["optional.pdf"],
  "top_k": 5,
  "include_answer": true
}
```

Response shape:

```json
{
  "trace_id": "trace_...",
  "query": "What is retrieval augmented generation?",
  "stages": [
    {
      "id": "query_processing",
      "title": "Query Processing",
      "status": "completed",
      "duration_ms": 2,
      "summary": "The question is normalized and prepared for retrieval.",
      "technical": {
        "tokens": ["what", "is", "retrieval", "augmented", "generation"]
      }
    }
  ],
  "retrieved_chunks": [],
  "context_preview": "...",
  "answer": "...",
  "total_duration_ms": 1234
}
```

The endpoint should reuse existing service functions where possible:

- `retrieve_with_faiss()` for the canonical retrieval path.
- `build_context_from_sources()` for context construction.
- `generate()` for LLM answer generation when `include_answer` is true.
- Existing admin trace ideas from `admin_retrieval_trace`, reshaped for a
  presentation-quality response.

The endpoint should return partial traces on recoverable failures. For example,
if retrieval succeeds but LLM generation times out, the response should include
completed retrieval and context stages, mark `llm_generation` as failed, and
include an English error summary.

## Trace Stages

Each stage should have a stable `id`, English `title`, `summary`, `status`, and
optional `technical` data.

Required stages:

- `user_question`: The submitted question and optional source filter.
- `query_processing`: Normalized text, tokens, and token count.
- `embedding_generation`: embedding model, dimension, and elapsed time.
- `bm25_retrieval`: keyword candidates and BM25 scores; if BM25 cannot be built,
  mark the stage as skipped with an English reason.
- `dense_retrieval`: vector candidates, distances, and converted match scores.
- `hybrid_ranking`: fused top candidates using the current hybrid retrieval path.
- `context_building`: selected chunks, source labels, and context length.
- `llm_generation`: provider, model, latency, and answer length.
- `final_answer`: final answer and source snippets.

## Frontend Components

Add focused Vue components instead of overloading existing chat components:

- `RagDemoView.vue`: owns query input, run state, replay state, selected stage,
  technical toggle, and playback timer.
- `RagFlowTimeline.vue`: renders the stage list and visual states.
- `RagStageDetail.vue`: renders the active stage explanation and payload preview.
- `RagEvidencePanel.vue`: renders retrieved chunks, source files, pages, match
  scores, and text previews.

The page should use the existing design tokens and restrained dashboard style.
Cards should remain compact, with clear hierarchy and no nested card layout.
The UI text should be English throughout.

## Error Handling

- Empty query returns HTTP 400 with `detail`.
- Missing index returns a trace with a failed retrieval stage and an English
  explanation that documents need to be uploaded and indexed first.
- LLM timeout returns a partial trace and marks `llm_generation` as failed.
- Unexpected backend errors return HTTP 500 with `detail`, while tests should
  cover expected partial-failure paths.

The frontend should show failed stages inline instead of replacing the whole page
with an error screen.

## Testing

Backend tests:

- Empty query validation.
- Successful trace response shape.
- Source filtering is passed through to retrieval.
- Partial LLM failure preserves earlier completed stages.
- `include_answer=false` skips generation and still returns retrieval/context
  trace data.

Frontend verification:

- Vite build succeeds.
- Demo page can render an empty state.
- Demo page can render and replay a mocked trace.
- Technical view toggle reveals detailed fields without changing playback state.

## Implementation Notes

The first implementation should favor reliability over maximum fidelity. A trace
that plays smoothly and uses true retrieval data is more useful for a demo than a
fully streamed trace that can stall during a presentation.

If a later version needs true streaming, the same stage schema can be reused for
SSE or WebSocket events.
