# Methodology Flowchart Design

## Purpose

Create two matching deliverables that communicate the adapted CRISP-DM
methodology used by the AI-based lecture-note question-answering project:

- a high-resolution standalone PNG for insertion into reports or slides; and
- a Word document containing an editable diagram built from native shapes and
  text.

## Layout

The diagram uses an A4 portrait canvas with six vertically stacked stages.
Straight downward arrows show the main sequence. A curved feedback arrow runs
from Stage 6 back to Stage 1 to communicate iterative refinement without
obscuring the primary flow.

The title is `Adapted CRISP-DM Project Methodology Workflow`. The caption is
`Figure 2.1: Adapted CRISP-DM Project Methodology Workflow`.

## Stage Content

1. **Project and Problem Understanding**
   Define the educational problem, project objectives, user needs, scope and
   success criteria.
2. **Lecture-Note Data Understanding**
   Review PDF structure, page content, document quality and metadata required
   for source traceability.
3. **PDF Extraction and Text Preparation**
   Extract and normalise text, then create 500-character chunks with a
   100-character overlap.
4. **RAG Modelling and Application Development**
   Generate 384-dimensional MiniLM embeddings; build FAISS and BM25 retrieval;
   fuse top-20 candidate lists using RRF with `k = 60`; return the final top
   five chunks to the answer-generation workflow.
5. **Technical and Functional Evaluation**
   Evaluate retrieval, RAGAS answer quality, software behaviour, latency and
   end-to-end functionality without presenting project results.
6. **Deployment and Iterative Refinement**
   Deploy the application, monitor behaviour and use evaluation or user
   feedback to refine earlier stages.

## Visual System

- A4 portrait orientation with approximately 1-inch outer margins.
- Restrained academic palette: dark navy headings, medium blue stage bands,
  pale blue content areas, neutral grey connectors and a white background.
- Times New Roman for report compatibility.
- Stage numbers appear in compact circular markers.
- Stage titles are bold and visually dominant; activity text is concise and
  readable at normal report scale.
- The refinement arrow is visually secondary to the downward process arrows.
- No decorative icons, gradients, shadows or unrelated branding.

## Deliverables

### PNG

- File: `report/methodology_flowchart.png`
- High-resolution portrait image with sufficient detail for A4 printing.
- Includes the diagram title and figure caption.

### Editable Word Diagram

- File: `report/methodology_flowchart_editable.docx`
- A4 portrait document containing the same visual hierarchy and wording.
- Diagram elements remain editable as native Word drawing shapes and text.
- No cover page, running header or footer.

## Quality Checks

- Confirm all six stages and technical parameters match the implemented
  repository and the completed Section 2.3 methodology.
- Confirm the stage order, numbering and caption are consistent across both
  files.
- Check that arrows do not cross labels or overlap stage containers.
- Render the Word document and inspect every page for clipping, spacing,
  missing glyphs or unintended page breaks.
- Inspect the final PNG at full resolution for legibility and balanced spacing.
- Remove all temporary build and QA artifacts before delivery.
