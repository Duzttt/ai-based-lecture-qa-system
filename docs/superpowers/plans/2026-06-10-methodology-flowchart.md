# Methodology Flowchart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a high-resolution PNG and a matching editable Word flowchart for the six-stage adapted CRISP-DM methodology.

**Architecture:** A temporary PowerShell builder will hold one canonical stage-data array and one coordinate system. It will draw the PNG with `System.Drawing` at A4/300 DPI and create the Word version through Microsoft Word COM using native rounded rectangles, title bands, number circles, text boxes and connectors. The Word document will then be rendered to PDF and page PNG for visual inspection.

**Tech Stack:** PowerShell 7, System.Drawing, Microsoft Word COM, OOXML structural inspection, Poppler `pdftoppm`

---

## File Structure

- Create temporarily: `report/_build_methodology_flowchart.ps1`
  - Stores the canonical content and generates both deliverables.
- Create: `report/methodology_flowchart.png`
  - A4 portrait, 2480 x 3508 pixels, 300 DPI.
- Create: `report/methodology_flowchart_editable.docx`
  - A4 portrait Word document with native editable drawing shapes.
- Create temporarily: `report/_qa_methodology_flowchart/`
  - Contains the rendered PDF and page image used only for QA.

### Task 1: Build the Shared Flowchart Generator

**Files:**
- Create: `report/_build_methodology_flowchart.ps1`

- [ ] **Step 1: Define the canonical stage data**

Use six objects with the approved titles and activity text:

```powershell
$stages = @(
    @{ Number = "1"; Title = "Project and Problem Understanding"; Body = "Define the educational problem, project objectives, user needs, scope and success criteria." },
    @{ Number = "2"; Title = "Lecture-Note Data Understanding"; Body = "Review PDF structure, page content, document quality and metadata required for source traceability." },
    @{ Number = "3"; Title = "PDF Extraction and Text Preparation"; Body = "Extract and normalise text; create 500-character chunks with a 100-character overlap." },
    @{ Number = "4"; Title = "RAG Modelling and Application Development"; Body = "Create 384-dimensional MiniLM embeddings; retrieve top-20 FAISS and BM25 candidates; fuse with RRF (k = 60); supply the final top five chunks." },
    @{ Number = "5"; Title = "Technical and Functional Evaluation"; Body = "Evaluate retrieval, RAGAS answer quality, software behaviour, latency and end-to-end functionality." },
    @{ Number = "6"; Title = "Deployment and Iterative Refinement"; Body = "Deploy and monitor the application; use evaluation and user feedback to refine earlier stages." }
)
```

- [ ] **Step 2: Encode the approved visual tokens**

Use A4 portrait geometry, Times New Roman, white background, navy `#17365D`,
blue `#2F75B5`, pale blue `#DDEBF7`, connector grey `#667085`, and a muted
feedback blue `#5B9BD5`. Use 1-inch-equivalent margins and keep the feedback
connector outside the stage boxes.

- [ ] **Step 3: Implement PNG drawing**

Create a 2480 x 3508 bitmap at 300 DPI. Draw the title, six rounded stage
containers, title bands, number circles, downward arrows, the refinement loop
and the caption. Use measured word wrapping so no label is clipped.

- [ ] **Step 4: Implement editable Word drawing**

Create an A4 portrait Word document with no header or footer. Add each visual
element with `Document.Shapes.AddShape`, `AddTextbox` or `AddConnector`, set
positions relative to the page, and apply Times New Roman explicitly. Save as
`report/methodology_flowchart_editable.docx`.

### Task 2: Generate and Structurally Validate Both Deliverables

**Files:**
- Create: `report/methodology_flowchart.png`
- Create: `report/methodology_flowchart_editable.docx`

- [ ] **Step 1: Run the builder**

Run:

```powershell
pwsh -File report/_build_methodology_flowchart.ps1
```

Expected: both deliverables exist and are non-empty.

- [ ] **Step 2: Validate the PNG**

Use bundled Python and Pillow to assert:

```python
from PIL import Image

image = Image.open("report/methodology_flowchart.png")
assert image.size == (2480, 3508)
assert image.info.get("dpi", (0, 0))[0] >= 299
```

- [ ] **Step 3: Validate the Word structure**

Open the DOCX as a ZIP archive and assert that it is valid, contains
`word/document.xml`, includes all six stage titles, and contains at least 25
drawing objects so the diagram is not a flattened image.

### Task 3: Render and Visually Inspect

**Files:**
- Create temporarily: `report/_qa_methodology_flowchart/methodology_flowchart_editable.pdf`
- Create temporarily: `report/_qa_methodology_flowchart/page-1.png`

- [ ] **Step 1: Export the Word document to PDF**

Open the DOCX with hidden Microsoft Word COM and use `ExportAsFixedFormat` with
PDF format `17`.

- [ ] **Step 2: Rasterise the rendered PDF**

Run:

```powershell
C:\poppler-24.08.0\Library\bin\pdftoppm.exe -png -r 150 `
  report/_qa_methodology_flowchart/methodology_flowchart_editable.pdf `
  report/_qa_methodology_flowchart/page
```

Expected: one page image.

- [ ] **Step 3: Inspect both images**

Inspect the standalone PNG and rendered Word page at full resolution. Confirm
that all six stages are readable, connectors do not cross text, the refinement
loop is secondary, the title and caption are intact, and no object is clipped.
If a defect appears, adjust the shared layout and regenerate both files.

### Task 4: Final Audit and Cleanup

**Files:**
- Delete: `report/_build_methodology_flowchart.ps1`
- Delete: `report/_qa_methodology_flowchart/`

- [ ] **Step 1: Audit content**

Confirm that both outputs contain the same title, caption, stage order and
parameters: 500 characters, 100-character overlap, 384-dimensional MiniLM,
top-20 FAISS and BM25 candidates, RRF `k = 60`, and final top five chunks.

- [ ] **Step 2: Remove temporary artifacts**

Delete only the temporary builder and QA directory after resolving their
absolute paths inside the workspace.

- [ ] **Step 3: Run final integrity checks**

Assert that the PNG and DOCX remain non-empty, the PNG dimensions remain
2480 x 3508, and the DOCX ZIP archive has no corrupt members.
