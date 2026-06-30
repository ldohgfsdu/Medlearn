#!/usr/bin/env python
"""Evaluate Stage 3 full nodes-only smoke adapter with gates and old-adapter comparison."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for path in (SCRIPTS_DIR, TRAINING_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import importlib.util

_EVAL_SPEC = importlib.util.spec_from_file_location(
    "training_evaluate_sft_adapter_module",
    TRAINING_DIR / "evaluate_sft_adapter.py",
)
if _EVAL_SPEC is None or _EVAL_SPEC.loader is None:
    raise RuntimeError("Unable to load training/evaluate_sft_adapter.py")
_eval_module = importlib.util.module_from_spec(_EVAL_SPEC)
_EVAL_SPEC.loader.exec_module(_eval_module)

generate_cases = _eval_module.generate_cases
load_evidence_matched_cases = _eval_module.load_evidence_matched_cases
load_holdout_cases = _eval_module.load_holdout_cases
load_jsonl = _eval_module.load_jsonl
row_to_case = _eval_module.row_to_case
write_failure_cases = _eval_module.write_failure_cases
from sft_eval_metrics import (  # noqa: E402
    build_diagnosis,
    evaluate_case,
    summarize_cases,
    utc_now_iso,
)
from stage3_eval_metrics import (  # noqa: E402
    OLD_ADAPTER_BASELINE,
    build_comparison_markdown,
    build_stage3_markdown_report,
    enrich_stage3_aggregate,
    evaluate_stage3_gates,
)
from build_sft_dataset import compact_json, format_chat_text  # noqa: E402
from sft_curriculum_lib import (  # noqa: E402
    build_stage3_assistant,
    build_stage3_user_prompt,
    parse_train_sample,
)

DEFAULT_GOLDEN = TRAINING_DIR / "curriculum" / "sft_v2_nodes_curriculum" / "eval.jsonl"
DEFAULT_TRAIN = (
    TRAINING_DIR
    / "curriculum"
    / "sft_v2_nodes_curriculum"
    / "stage3_full_nodes_only"
    / "train.jsonl"
)
DEFAULT_OLD_ADAPTER = TRAINING_DIR / "checkpoints" / "qwen3-0.6b-medlearn-lora" / "final"
OLD_ADAPTER_REPORT = TRAINING_DIR / "reports" / "sft_eval_report.json"
REPORT_JSON = TRAINING_DIR / "reports" / "stage3_full_nodes_only_eval.json"
REPORT_MD = TRAINING_DIR / "reports" / "stage3_full_nodes_only_eval.md"
COMPARISON_MD = TRAINING_DIR / "reports" / "stage3_vs_old_adapter_comparison.md"
FAILURE_JSONL = TRAINING_DIR / "reports" / "stage3_full_nodes_only_failures.jsonl"


def align_golden_row_to_stage3(row: dict[str, Any]) -> dict[str, Any]:
    parsed = parse_train_sample(row)
    expected = build_stage3_assistant(parsed["nodes"])
    user_prompt = build_stage3_user_prompt(
        chapter_path=parsed["chapter_path"],
        source_text=parsed["source_text"],
    )
    aligned = dict(row)
    aligned["text"] = format_chat_text(user_prompt, compact_json(expected))
    aligned["expected"] = expected
    aligned["edge_count"] = 0
    aligned["stage3_prompt_aligned"] = True
    return aligned


def load_old_adapter_aggregate(path: Path) -> dict[str, Any]:
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        aggregate = dict(report.get("aggregate") or {})
        taxonomy = aggregate.get("failure_taxonomy") or {}
        case_count = aggregate.get("case_count") or 1
        aggregate["edge_missing"] = taxonomy.get("edge_missing", OLD_ADAPTER_BASELINE["edge_missing"])
        aggregate["single_summary_node_rate"] = round(
            taxonomy.get("single_summary_node", 0) / case_count,
            4,
        )
        aggregate["parent_entity_grounded_rate"] = None
        return aggregate
    return dict(OLD_ADAPTER_BASELINE)


def run_evaluation(
    *,
    base_model: Path,
    adapter: Path,
    golden: Path,
    train_dataset: Path,
    holdout_samples: int,
    evidence_matched_samples: int,
    max_length: int,
    max_new_tokens: int,
    align_golden_stage3: bool,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    golden_rows = load_jsonl(golden)
    if align_golden_stage3:
        golden_rows = [align_golden_row_to_stage3(row) for row in golden_rows]
    suites: dict[str, list[Any]] = {
        "golden_8": [row_to_case(row, "golden_8") for row in golden_rows],
    }
    if holdout_samples > 0:
        suites["holdout_3"] = load_holdout_cases(
            train_dataset,
            count=holdout_samples,
        )
    if evidence_matched_samples > 0:
        suites["evidence_matched"] = load_evidence_matched_cases(
            train_dataset,
            count=evidence_matched_samples,
        )

    all_cases = [case for cases in suites.values() for case in cases]
    tokenizer = AutoTokenizer.from_pretrained(base_model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        torch_dtype=torch.float16,
        local_files_only=True,
    )
    model = PeftModel.from_pretrained(model, adapter)
    model = model.to("cuda").eval()

    generated = generate_cases(
        all_cases,
        tokenizer=tokenizer,
        model=model,
        max_length=max_length,
        max_new_tokens=max_new_tokens,
    )
    case_results = [evaluate_case(case) for case in generated]
    by_case_id = {item["case_id"]: item for item in case_results}

    suite_reports: dict[str, Any] = {}
    for suite_name, suite_cases in suites.items():
        suite_results = [by_case_id[case.case_id] for case in suite_cases]
        suite_reports[suite_name] = {
            "aggregate": summarize_cases(suite_results),
            "cases": suite_results,
        }

    aggregate = summarize_cases(case_results)
    return (
        {
            "meta": {
                "evaluated_at": utc_now_iso(),
                "mode": (
                    "stage3_full_nodes_only_golden_prompt_aligned"
                    if align_golden_stage3
                    else "stage3_full_nodes_only"
                ),
                "base_model": str(base_model),
                "adapter": str(adapter),
                "suites": list(suites.keys()),
                "case_count": len(case_results),
                "golden_prompt_protocol": (
                    "stage3_full_nodes_only" if align_golden_stage3 else "dataset_original"
                ),
            },
            "aggregate": aggregate,
            "suites": suite_reports,
            "diagnosis": build_diagnosis(aggregate),
        },
        case_results,
    )


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate Stage 3 full nodes-only smoke adapter")
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--base-adapter", type=Path, default=None)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--train-dataset", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--old-adapter-report", type=Path, default=OLD_ADAPTER_REPORT)
    parser.add_argument("--holdout-samples", type=int, default=3)
    parser.add_argument("--evidence-matched-samples", type=int, default=10)
    parser.add_argument("--max-length", type=int, default=3072)
    parser.add_argument("--max-new-tokens", type=int, default=1280)
    parser.add_argument(
        "--align-golden-stage3",
        action="store_true",
        help="Rebuild golden prompts and expected payloads with the Stage 3 nodes-only protocol.",
    )
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--comparison-md", type=Path, default=COMPARISON_MD)
    parser.add_argument("--failure-jsonl", type=Path, default=FAILURE_JSONL)
    args = parser.parse_args()

    report, case_results = run_evaluation(
        base_model=args.base_model,
        adapter=args.adapter,
        golden=args.golden,
        train_dataset=args.train_dataset,
        holdout_samples=args.holdout_samples,
        evidence_matched_samples=args.evidence_matched_samples,
        max_length=args.max_length,
        max_new_tokens=args.max_new_tokens,
        align_golden_stage3=args.align_golden_stage3,
    )
    if args.base_adapter:
        report["meta"]["base_adapter"] = str(args.base_adapter)

    aggregate = enrich_stage3_aggregate(report["aggregate"], case_results)
    report["aggregate"] = aggregate
    old_aggregate = load_old_adapter_aggregate(args.old_adapter_report)
    gates = evaluate_stage3_gates(aggregate, old_baseline=old_aggregate)
    report["gates"] = gates
    report["old_adapter_baseline"] = old_aggregate

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_md.write_text(build_stage3_markdown_report(report), encoding="utf-8")
    args.comparison_md.write_text(
        build_comparison_markdown(
            stage3_aggregate=aggregate,
            old_aggregate=old_aggregate,
            stage3_gates=gates,
        ),
        encoding="utf-8",
    )
    write_failure_cases(args.failure_jsonl, case_results)

    print(json.dumps({"aggregate": aggregate, "gates": gates}, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.report_json}")
    print(f"Wrote {args.report_md}")
    print(f"Wrote {args.comparison_md}")


if __name__ == "__main__":
    main()
