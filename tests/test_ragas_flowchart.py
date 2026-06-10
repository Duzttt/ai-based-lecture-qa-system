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
