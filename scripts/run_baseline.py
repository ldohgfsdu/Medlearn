#!/usr/bin/env python
"""
Phase 1: Establish Baseline
Run real LLM (medlearn-qwen3:8b) on Mini Golden Set.
Save first benchmark result as v4.5_baseline.json
"""
import json
from pathlib import Path
from prompt_system.prompt_evaluator import PromptEvaluator
from textbook_pipeline.llm_structurer import run_structuring

def load_golden(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def main():
    golden_path = Path("golden_dataset/mini_golden_set.json")
    output_dir = Path("artifacts/benchmarks")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("🚀 Phase 1: Establishing Baseline with Real LLM")
    print("=" * 70)
    print(f"Golden Set: {golden_path.name} ({len(load_golden(golden_path))} samples)")
    print("Model: medlearn-qwen3:8b (local)")
    print("=" * 70)
    
    golden = load_golden(golden_path)
    
    # Run real LLM structuring (using real model via llm_structurer)
    print("\nCalling real LLM (medlearn-qwen3:8b)...")
    structured_outputs = run_structuring(golden, golden)  # Pass golden as both for test
    
    # Evaluate
    evaluator = PromptEvaluator()
    results = evaluator.benchmark(structured_outputs, golden)
    
    # Save baseline
    baseline = {
        "prompt_version": "v4.5_baseline",
        "timestamp": "2026-06-12",
        "overall_score": results.get("overall_score", 0),
        "completeness": results.get("completeness", 0),
        "hallucination_risk": results.get("hallucination_risk", 0),
        "schema_compliance": results.get("schema_compliance", 0),
        "relation_quality": results.get("relation_quality", 0),
        "sample_count": len(golden),
        "model": "medlearn-qwen3:8b",
        "note": "First baseline. Hallucination > Completeness is priority."
    }
    
    baseline_path = output_dir / "v4.5_baseline.json"
    with open(baseline_path, 'w', encoding='utf-8') as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)
    
    print("\n" + "="*70)
    print("BASELINE ESTABLISHED")
    print("="*70)
    for k, v in baseline.items():
        if isinstance(v, (int, float)):
            print(f"{k.replace('_', ' ').title():<20}: {v}")
        else:
            print(f"{k.replace('_', ' ').title():<20}: {v}")
    print("="*70)
    print(f"Baseline saved to: {baseline_path}")
    print("\nNext Phase: Use this baseline to iteratively improve prompts.")
    print("Target: Overall > 85 | Hallucination > Completeness")

if __name__ == "__main__":
    main()
