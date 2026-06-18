#!/usr/bin/env python
"""Hard evaluation harness for MedLearn SFT LoRA adapters."""
from __future__ import annotations

import argparse
import json
import random
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

from sft_eval_metrics import (  # noqa: E402
    EvalCaseInput,
    GeneratedCase,
    build_diagnosis,
    build_markdown_report,
    evaluate_case,
    extract_prompt_and_expected,
    extract_source_text,
    parse_generated,
    summarize_cases,
    utc_now_iso,
)
from sft_quality_gates import validate_extraction_payload  # noqa: E402

DEFAULT_GOLDEN = TRAINING_DIR / "sft_smoke_eval.jsonl"
DEFAULT_TRAIN = TRAINING_DIR / "sft_train.jsonl"
REPORT_DIR = TRAINING_DIR / "reports"
REPORT_JSON = REPORT_DIR / "sft_eval_report.json"
REPORT_MD = REPORT_DIR / "sft_eval_report.md"
FAILURE_JSONL = REPORT_DIR / "sft_failure_cases.jsonl"
LEGACY_REPORT = REPORT_DIR / "adapter_generation_eval.json"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def row_to_case(row: dict[str, Any], suite: str) -> EvalCaseInput:
    prompt, expected = extract_prompt_and_expected(row)
    source_text = extract_source_text(row.get("text") or prompt)
    return EvalCaseInput(
        case_id=str(row.get("id") or suite),
        suite=suite,
        source_text=source_text,
        prompt=prompt,
        expected=expected,
        golden_title=row.get("golden_title"),
        metadata={
            key: value
            for key, value in row.items()
            if key not in {"text", "expected"}
        },
    )


def load_holdout_cases(dataset_path: Path, *, count: int, seed: int = 42) -> list[EvalCaseInput]:
    rows = load_jsonl(dataset_path)
    random.Random(seed).shuffle(rows)
    validation_size = max(8, round(len(rows) * 0.1))
    holdout_rows = rows[:validation_size][:count]
    return [row_to_case(row, "holdout_3") for row in holdout_rows]


def load_evidence_matched_cases(
    dataset_path: Path,
    *,
    count: int,
    seed: int = 42,
) -> list[EvalCaseInput]:
    matched_rows: list[dict[str, Any]] = []
    for row in load_jsonl(dataset_path):
        source_text = extract_source_text(row.get("text") or "")
        _, expected = extract_prompt_and_expected(row)
        if not expected:
            continue
        accepted, _, metrics = validate_extraction_payload(expected, source_text)
        if (
            accepted
            and metrics.get("node_count", 0) > 0
            and metrics.get("evidence_matched", 0) == metrics.get("node_count", 0)
        ):
            matched_rows.append(row)

    random.Random(seed).shuffle(matched_rows)
    selected = matched_rows[:count]
    return [row_to_case(row, "evidence_matched") for row in selected]


def generate_cases(
    cases: list[EvalCaseInput],
    *,
    tokenizer: Any,
    model: Any,
    max_length: int,
    max_new_tokens: int,
) -> list[GeneratedCase]:
    generated_cases: list[GeneratedCase] = []
    for case in cases:
        prompt_ids = tokenizer(case.prompt, add_special_tokens=False)["input_ids"]
        if len(prompt_ids) > max_length:
            prompt_ids = prompt_ids[:384] + prompt_ids[-(max_length - 384) :]
        inputs = {
            "input_ids": torch.tensor([prompt_ids], device=model.device),
            "attention_mask": torch.ones(
                (1, len(prompt_ids)),
                dtype=torch.long,
                device=model.device,
            ),
        }
        end_token_id = tokenizer.convert_tokens_to_ids("<|im_end|>")
        with torch.inference_mode():
            output = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                eos_token_id=end_token_id,
                pad_token_id=tokenizer.eos_token_id,
            )
        generated_text = tokenizer.decode(
            output[0][inputs["input_ids"].shape[1] :],
            skip_special_tokens=False,
        )
        payload, raw = parse_generated(generated_text)
        generated_cases.append(
            GeneratedCase(
                case_id=case.case_id,
                suite=case.suite,
                source_text=case.source_text,
                expected=case.expected,
                generated=payload,
                raw_text=raw,
                json_valid=payload is not None,
                golden_title=case.golden_title,
            )
        )
    return generated_cases


def write_failure_cases(path: Path, case_results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for case in case_results:
            for failure in case.get("failures") or []:
                handle.write(json.dumps(failure, ensure_ascii=False) + "\n")


def build_legacy_adapter_report(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "sample_count": len(case_results),
        "json_valid_count": sum(1 for item in case_results if item["json_valid"]),
        "schema_valid_count": sum(
            1
            for item in case_results
            if item["json_valid"] and item["has_nodes"] and item["has_edges"]
        ),
        "results": [
            {
                "id": item["case_id"],
                "json_valid": item["json_valid"],
                "has_nodes_and_edges": item["has_nodes"] and item["has_edges"],
                "expected_node_count": item["expected_node_count"],
                "generated_node_count": item["actual_node_count"],
                "generated_preview": item.get("generated_preview"),
            }
            for item in case_results
        ],
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Hard evaluation for MedLearn SFT adapters")
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--train-dataset", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--holdout-samples", type=int, default=3)
    parser.add_argument("--evidence-matched-samples", type=int, default=10)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--failure-jsonl", type=Path, default=FAILURE_JSONL)
    parser.add_argument("--legacy-report", type=Path, default=LEGACY_REPORT)
    args = parser.parse_args()

    suites: dict[str, list[EvalCaseInput]] = {
        "golden_8": [row_to_case(row, "golden_8") for row in load_jsonl(args.golden)],
    }
    if args.holdout_samples > 0:
        suites["holdout_3"] = load_holdout_cases(
            args.train_dataset,
            count=args.holdout_samples,
        )
    if args.evidence_matched_samples > 0:
        suites["evidence_matched"] = load_evidence_matched_cases(
            args.train_dataset,
            count=args.evidence_matched_samples,
        )

    all_cases = [case for cases in suites.values() for case in cases]

    tokenizer = AutoTokenizer.from_pretrained(args.base_model, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(
        args.base_model,
        torch_dtype=torch.float16,
        local_files_only=True,
    )
    model = PeftModel.from_pretrained(model, args.adapter)
    model = model.to("cuda").eval()

    generated = generate_cases(
        all_cases,
        tokenizer=tokenizer,
        model=model,
        max_length=args.max_length,
        max_new_tokens=args.max_new_tokens,
    )

    case_results = [evaluate_case(case) for case in generated]
    by_case_id = {item["case_id"]: item for item in case_results}

    suite_reports: dict[str, Any] = {}
    for suite_name, suite_cases in suites.items():
        suite_case_results = [by_case_id[case.case_id] for case in suite_cases]
        suite_reports[suite_name] = {
            "aggregate": summarize_cases(suite_case_results),
            "cases": suite_case_results,
        }

    aggregate = summarize_cases(case_results)
    report = {
        "meta": {
            "evaluated_at": utc_now_iso(),
            "base_model": str(args.base_model),
            "adapter": str(args.adapter),
            "suites": list(suites.keys()),
            "case_count": len(case_results),
            "aspect_coverage_mode": "heuristic",
            "node_matching_mode": "heuristic",
            "inputs": {
                "golden": str(args.golden),
                "train_dataset": str(args.train_dataset),
                "holdout_samples": args.holdout_samples,
                "evidence_matched_samples": args.evidence_matched_samples,
            },
        },
        "aggregate": aggregate,
        "suites": suite_reports,
        "diagnosis": build_diagnosis(aggregate),
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.report_md.write_text(build_markdown_report(report), encoding="utf-8")
    write_failure_cases(args.failure_jsonl, case_results)
    args.legacy_report.write_text(
        json.dumps(
            build_legacy_adapter_report(
                [by_case_id[case.case_id] for case in suites.get("holdout_3", [])]
                or case_results[: args.holdout_samples],
            ),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(json.dumps(report["aggregate"], ensure_ascii=False, indent=2))
    print(f"\nWrote {args.report_json}")
    print(f"Wrote {args.report_md}")
    print(f"Wrote {args.failure_jsonl}")


if __name__ == "__main__":
    main()
