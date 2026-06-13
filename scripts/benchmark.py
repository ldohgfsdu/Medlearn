#!/usr/bin/env python
"""
V4.5.1 Benchmark System - Evaluator Reliability Fix
Uses deterministic matching with synonym map.
"""
import argparse
import json
from pathlib import Path
from prompt_system.prompt_evaluator import PromptEvaluator

def load_golden(path: Path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_outputs(path: Path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        print("Warning: No real output file. Using golden as placeholder for demo.")
        return load_golden(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--golden", default="golden_dataset/mini_golden_set.json")
    parser.add_argument("--output", default="output_v4/test_structured.json")
    parser.add_argument("--prompt_version", default="v4.5.1")
    args = parser.parse_args()

    print(f"\n📊 Benchmarking Prompt Version: {args.prompt_version} (Evaluator Reliability Fix)")
    print(f"Golden Dataset: {args.golden}")
    print("=" * 80)

    golden = load_golden(Path(args.golden))
    outputs = load_outputs(Path(args.output))

    evaluator = PromptEvaluator()
    results = evaluator.run_benchmark(outputs, golden)

    print("\n" + "="*80)
    print("Next Step Suggestion:")
    print("1. If Completeness is still low → improve evidence_span extraction")
    print("2. If Relation Quality is low → improve relation prompt")
    print("3. Expand to 30-sample golden set once evaluator is stable.")
    print("="*80)

if __name__ == "__main__":
    main()
