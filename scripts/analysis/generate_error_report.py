#!/usr/bin/env python
"""
Error Analysis for V4.5 - Error-driven Prompt Optimization
Compares model output vs Golden Dataset, classifies errors.
Generates structured report for prompt improvement.
"""
import json
from pathlib import Path
from collections import defaultdict
from prompt_system.prompt_evaluator import PromptEvaluator

class ErrorAnalyzer:
    def __init__(self):
        self.errors = defaultdict(list)
        self.evaluator = PromptEvaluator()
    
    def analyze_sample(self, golden: dict, model_output: dict) -> dict:
        """Analyze one sample and classify errors."""
        title = golden["title"]
        sample_errors = {
            "missing": [],
            "extra": [],
            "wrong_relation": [],
            "hallucination": [],
            "completeness_score": 0.0
        }
        
        golden_content = golden.get("expected_content", {})
        model_content = model_output.get("content", {})
        
        # Check missing fields
        for field, golden_val in golden_content.items():
            model_val = model_content.get(field, {})
            if not model_val or not model_val.get("content"):
                sample_errors["missing"].append(field)
        
        # Check hallucination (forbidden terms)
        forbidden = golden.get("forbidden_terms", [])
        for field in model_content.values():
            content = field.get("content", "") if isinstance(field, dict) else str(field)
            for term in forbidden:
                if term.lower() in content.lower():
                    sample_errors["hallucination"].append(term)
        
        # Check wrong relations
        golden_rel = golden.get("expected_relations", [])
        model_rel = model_output.get("relations", [])
        for gr in golden_rel:
            if gr not in model_rel:
                sample_errors["wrong_relation"].append(gr)
        
        # Overall classification
        if sample_errors["missing"]:
            self.errors["low_completeness"].append(title)
        if sample_errors["hallucination"]:
            self.errors["hallucination"].append(title)
        if sample_errors["wrong_relation"]:
            self.errors["low_relation_quality"].append(title)
        
        sample_errors["completeness_score"] = round(100 * (1 - len(sample_errors["missing"]) / max(len(golden_content), 1)), 1)
        
        return sample_errors
    
    def generate_report(self, golden_set: list, model_outputs: list) -> dict:
        """Generate full error report."""
        report = {
            "version": "v4.5_error_analysis",
            "total_samples": len(golden_set),
            "summary": {},
            "detailed_errors": {}
        }
        
        for g, m in zip(golden_set, model_outputs):
            title = g["title"]
            analysis = self.analyze_sample(g, m)
            report["detailed_errors"][title] = analysis
        
        # Summary
        for category, items in self.errors.items():
            report["summary"][category] = len(items)
        
        print("\n" + "="*80)
        print("ERROR ANALYSIS REPORT (V4.5)")
        print("="*80)
        for category, count in report["summary"].items():
            print(f"{category.replace('_', ' ').title():<25}: {count} samples")
        print("="*80)
        
        # Save report
        Path("analysis").mkdir(exist_ok=True)
        with open("analysis/error_report_v4.5.json", "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print("Report saved to: analysis/error_report_v4.5.json")
        return report

if __name__ == "__main__":
    print("Error Analyzer ready.")
    print("Run with real golden and model outputs to generate detailed error report.")
