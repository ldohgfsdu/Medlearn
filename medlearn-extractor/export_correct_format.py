"""Export structured.json to correct 9-dimension JSON format."""

import json
from pathlib import Path

import config


def export_correct_format():
    """Export structured data to correct 9-dimension format."""
    # Load structured data
    with open(config.STRUCTURED_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    kps = data.get("knowledge_points", [])

    # Convert to correct format
    formatted_nodes = []

    for kp in kps:
        if kp.get("structurize_status") != "success":
            continue

        structured = kp.get("structured", {})
        if not structured:
            continue

        # Build correct 9-dimension format
        node = {
            "name": kp.get("name", ""),
            "system": kp.get("_system", ""),
            "chapter": kp.get("_chapter", ""),
            "type": kp.get("type", "disease"),
            "aliases": structured.get("aliases", []),
            "keywords": structured.get("keywords", []),
            "definition": structured.get("definition", ""),
            "etiology": structured.get("etiology", ""),
            "pathogenesis": structured.get("pathogenesis", ""),
            "pathology": structured.get("pathology", ""),
            "manifestation": structured.get("manifestation", ""),
            "examination": structured.get("examination", ""),
            "diagnosis": structured.get("diagnosis", ""),
            "treatment": structured.get("treatment", ""),
            "prognosis": structured.get("prognosis", ""),
            "vindicate": structured.get("vindicate", {
                "vascular": "",
                "infectious": "",
                "neoplastic": "",
                "drug": "",
                "inflammatory": "",
                "congenital": "",
                "autoimmune": "",
                "traumatic": "",
                "endocrine": ""
            })
        }

        formatted_nodes.append(node)

    # Save to correct format
    output_path = config.OUTPUT_DIR / "knowledge_nodes_formatted.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(formatted_nodes, f, ensure_ascii=False, indent=2)

    print(f"✓ Exported {len(formatted_nodes)} knowledge nodes to: {output_path}")

    # Show example
    if formatted_nodes:
        print("\n示例数据结构:")
        example = formatted_nodes[0]
        for key in example:
            value = example[key]
            if isinstance(value, str) and len(value) > 50:
                print(f"  {key}: {value[:50]}...")
            elif isinstance(value, list) and len(value) > 3:
                print(f"  {key}: {value[:3]}...")
            elif isinstance(value, dict):
                print(f"  {key}: {{...}}")
            else:
                print(f"  {key}: {value}")


if __name__ == "__main__":
    export_correct_format()
