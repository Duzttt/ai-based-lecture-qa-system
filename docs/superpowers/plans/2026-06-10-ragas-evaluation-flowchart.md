# RAGAS Evaluation Flowchart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate a detailed, editable Draw.io flowchart illustrating the RAGAS evaluation pipeline in this project.

**Architecture:** Create a Python script `scripts/generate_ragas_flowchart.py` that generates a `.drawio` XML file using Python's `xml.etree.ElementTree`. The flowchart will have 8 sequential boxes, color-coded by process phase, connected by downward arrows, styled using exact style attributes. We will verify the XML structure with a pytest unit test.

**Tech Stack:** Python 3.9+, XML ElementTree, Pytest

---

## File Structure

- Create: `scripts/generate_ragas_flowchart.py`
  - Generates the `.drawio` XML document containing nodes and edges.
- Create: `tests/test_ragas_flowchart.py`
  - Tests the generator logic and validates the XML output.
- Create: `report/ragas_evaluation_flowchart.drawio`
  - The final generated editable flowchart.

---

### Task 1: Write Unit Test for Flowchart Generation

**Files:**
- Create: `tests/test_ragas_flowchart.py`

- [ ] **Step 1: Write the test code**

Create `tests/test_ragas_flowchart.py` to assert that the script runs, creates the output file, and that the output file contains valid XML with 8 vertex cells and 7 edge cells.

```python
import os
import xml.etree.ElementTree as ET
from scripts.generate_ragas_flowchart import generate_flowchart

def test_generate_flowchart(tmp_path):
    output_file = tmp_path / "ragas_flowchart.drawio"
    generate_flowchart(str(output_file))
    
    assert output_file.exists()
    
    # Parse and validate XML
    tree = ET.parse(output_file)
    root = tree.getroot()
    
    assert root.tag == "mxfile"
    diagram = root.find("diagram")
    assert diagram is not None
    graph_model = diagram.find("mxGraphModel")
    assert graph_model is not None
    root_node = graph_model.find("root")
    assert root_node is not None
    
    # Check cells
    cells = root_node.findall("mxCell")
    # Should contain default parent cells (id=0, id=1) plus 8 boxes and 7 arrows
    assert len(cells) >= 17
    
    vertices = [c for c in cells if c.get("vertex") == "1"]
    edges = [c for c in cells if c.get("edge") == "1"]
    
    assert len(vertices) == 8
    assert len(edges) == 7
    
    # Check that stage labels match the specification
    stages = [v.get("value") for v in vertices]
    assert any("Input Sources" in s for s in stages)
    assert any("Smart Chunking" in s for s in stages)
    assert any("QA Pair Generation" in s for s in stages)
    assert any("Hybrid Retrieval Engine" in s for s in stages)
    assert any("Answer Generation" in s for s in stages)
    assert any("Dataset Assembly" in s for s in stages)
    assert any("RAGAS Evaluation Engine" in s for s in stages)
    assert any("Evaluation Output Reports" in s for s in stages)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_ragas_flowchart.py -v`
Expected: FAIL due to `ModuleNotFoundError: No module named 'scripts.generate_ragas_flowchart'`

- [ ] **Step 3: Commit initial test**

```bash
git add tests/test_ragas_flowchart.py
git commit -m "test: add unit test for RAGAS flowchart generation"
```

---

### Task 2: Implement the Flowchart Generator

**Files:**
- Create: `scripts/generate_ragas_flowchart.py`

- [ ] **Step 1: Implement the generator**

Create the generator script at `scripts/generate_ragas_flowchart.py` containing:

```python
import xml.etree.ElementTree as ET
from xml.dom import minidom

def generate_flowchart(output_path: str) -> None:
    # Root: mxfile
    mxfile = ET.Element("mxfile", host="Electron", version="24.0.0", type="device")
    diagram = ET.SubElement(mxfile, "diagram", id="RagasEvalPage", name="RAGAS Evaluation Flow")
    graph_model = ET.SubElement(
        diagram,
        "mxGraphModel",
        dx="1000",
        dy="1200",
        grid="1",
        gridSize="10",
        guides="1",
        tooltips="1",
        connect="1",
        arrows="1",
        fold="1",
        page="1",
        pageScale="1",
        pageWidth="827",
        pageHeight="1169",
        math="0",
        shadow="0",
    )
    root = ET.SubElement(graph_model, "root")
    
    # Default layer cells
    ET.SubElement(root, "mxCell", id="0")
    ET.SubElement(root, "mxCell", id="1", parent="0")
    
    # 8 boxes data: (id, label, style, width, height, y)
    # Styles include custom colors mapping to stages
    style_io = "rounded=1;whiteSpace=wrap;html=1;fillColor=#F5F5F7;strokeColor=#86868B;fontColor=#1D1D1F;fontFamily=Helvetica;fontSize=12;fontStyle=1;align=center;strokeWidth=2;"
    style_prep = "rounded=1;whiteSpace=wrap;html=1;fillColor=#FEF3C7;strokeColor=#F59E0B;fontColor=#78350F;fontFamily=Helvetica;fontSize=12;fontStyle=1;align=center;strokeWidth=2;"
    style_rag = "rounded=1;whiteSpace=wrap;html=1;fillColor=#DDEBF7;strokeColor=#2F75B5;fontColor=#1E3A8A;fontFamily=Helvetica;fontSize=12;fontStyle=1;align=center;strokeWidth=2;"
    style_eval = "rounded=1;whiteSpace=wrap;html=1;fillColor=#CCFBF1;strokeColor=#0D9488;fontColor=#115E59;fontFamily=Helvetica;fontSize=12;fontStyle=1;align=center;strokeWidth=2;"
    
    boxes = [
        (
            "step1",
            "1. Input Sources\n\nPDF Lecture Notes (media/data_source/)\nOR pre-defined dataset (JSONL format)",
            style_io, 260, 70, 40
        ),
        (
            "step2",
            "2. Text Preparation & Smart Chunking\n\nExtract text via PDFLoader\nSplit into 500-char chunks (100-char overlap)",
            style_prep, 260, 70, 150
        ),
        (
            "step3",
            "3. QA Pair Generation (LLM-based)\n\nPrompt generator LLM to output JSON array of\n{question, ground_truth} -> Export to JSONL",
            style_prep, 260, 75, 260
        ),
        (
            "step4",
            "4. Hybrid Retrieval Engine\n\nQuery FAISS (dense) + BM25 (sparse)\nFuse via RRF (k=60) -> Extract top top_k chunks",
            style_rag, 260, 70, 370
        ),
        (
            "step5",
            "5. Answer Generation\n\nFormat context + question\nQuery LLM generator to produce response",
            style_rag, 260, 70, 480
        ),
        (
            "step6",
            "6. Dataset Assembly\n\nCompile matched question, contexts,\nanswer, and ground_truth into HF Dataset format",
            style_rag, 260, 70, 590
        ),
        (
            "step7",
            "7. RAGAS Evaluation Engine\n\nRun evaluate() with ChatOpenAI & _LocalRagasEmbeddings\nCalculate metrics:\n- Faithfulness    - Answer Relevancy\n- Context Precision    - Context Recall",
            style_eval, 260, 100, 700
        ),
        (
            "step8",
            "8. Evaluation Output Reports\n\nWrite full results to CSV report\n& Log aggregate metrics overall score report",
            style_io, 260, 70, 840
        ),
    ]
    
    center_x = 400
    for id_val, label, style, w, h, y in boxes:
        x = center_x - (w / 2)
        cell = ET.SubElement(root, "mxCell", id=id_val, value=label, style=style, vertex="1", parent="1")
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y), width=str(w), height=str(h), as_="geometry")
        
    # Connections data: (id, source, target)
    style_arrow = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;strokeColor=#667085;strokeWidth=2;"
    
    connections = [
        ("arrow1", "step1", "step2"),
        ("arrow2", "step2", "step3"),
        ("arrow3", "step3", "step4"),
        ("arrow4", "step4", "step5"),
        ("arrow5", "step5", "step6"),
        ("arrow6", "step6", "step7"),
        ("arrow7", "step7", "step8"),
    ]
    
    for id_val, src, tgt in connections:
        cell = ET.SubElement(
            root, "mxCell", id=id_val, value="", style=style_arrow,
            edge="1", parent="1", source=src, target=tgt
        )
        ET.SubElement(cell, "mxGeometry", relative="1", as_="geometry")
        
    # Write pretty XML
    xml_str = minidom.parseString(ET.tostring(mxfile, encoding="utf-8")).toprettyxml(indent="  ")
    # minidom prepends a declaration like <?xml version="1.0" ?>. Draw.io files usually don't need it or tolerate it. Let's write it cleanly.
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(xml_str)

if __name__ == "__main__":
    import sys
    out = sys.argv[1] if len(sys.argv) > 1 else "report/ragas_evaluation_flowchart.drawio"
    generate_flowchart(out)
    print(f"Flowchart successfully generated at: {out}")
```

- [ ] **Step 2: Run tests to verify it passes**

Run: `pytest tests/test_ragas_flowchart.py -v`
Expected: PASS

- [ ] **Step 3: Generate the actual deliverable**

Run: `python scripts/generate_ragas_flowchart.py`
Expected: File `report/ragas_evaluation_flowchart.drawio` is generated.

- [ ] **Step 4: Commit code & output**

```bash
git add scripts/generate_ragas_flowchart.py report/ragas_evaluation_flowchart.drawio
git commit -m "feat: implement RAGAS flowchart generator and output drawio file"
```

---

### Task 3: Visual Inspection of XML

- [ ] **Step 1: Check output drawio file size and format**

Validate that the generated file contains `<mxfile>` and all correct vertex IDs by viewing the first 50 lines.

```bash
powershell -Command "Get-Content report/ragas_evaluation_flowchart.drawio -Head 50"
```

Expected: XML format matches the draw.io schema.
