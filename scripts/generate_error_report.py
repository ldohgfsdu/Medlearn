#!/usr/bin/env python
"""
V4.5 Error Report Generator
Generates detailed error analysis for each sample in Mini Golden Set.
"""
import json
from pathlib import Path
from typing import Dict, List

def generate_error_report(golden_path: Path, structured_path: Path):
    golden = json.loads(golden_path.read_text(encoding='utf-8'))
    structured = json.loads(structured_path.read_text(encoding='utf-8'))
    
    report = {
        "version": "v4.5.1",
        "timestamp": "2026-06-12",
        "total_samples": len(golden),
        "samples": []
    }
    
    for g in golden:
        sample = {
            "id": g["id"],
            "title": g["title"],
            "type": g["type"],
            "errors": {
                "missing_terms": [],
                "extra_terms": [],
                "wrong_relations": [],
                "hallucination": []
            }
        }
        
        # Check must_have_terms
        content = structured[0].get("content", {}) if structured else {}
        for term in g.get("must_have_terms", []):
            found = any(term.lower() in str(v).lower() for v in content.values())
            if not found:
                sample["errors"]["missing_terms"].append(term)
        
        # Check forbidden_terms
        for term in g.get("forbidden_terms", []):
            found = any(term.lower() in str(v).lower() for v in content.values())
            if found:
                sample["errors"]["hallucination"].append(term)
        
        # Check expected_relations
        expected = [r["target_name"] for r in g.get("expected_relations", [])]
        actual = [r.get("target_name") for r in structured[0].get("relations", []) if isinstance(r, dict)]
        for r in expected:
            if r not in actual:
                sample["errors"]["wrong_relations"].append(r)
        
        report["samples"].append(sample)
    
    output_path = Path("analysis/error_report_v4.5.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    
    print(f"Error Report generated: {output_path}")
    print(f"Total samples: {report['total_samples']}")
    return report

if __name__ == "__main__":
    generate_error_report(
        Path("golden_dataset/mini_golden_set.json"),
        Path("output_v4/test_structured.json")
    )
