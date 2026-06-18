#!/usr/bin/env python
"""Evaluate Stage 1 evidence-copy LoRA adapters."""
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

from sft_curriculum_lib import build_curriculum_row, parse_train_sample  # noqa: E402
from sft_eval_metrics import (  # noqa: E402
    EvalCaseInput,
    GeneratedCase,
    extract_prompt_and_expected,
    parse_generated,
    utc_now_iso,
)
from stage1_eval_metrics import (  # noqa: E402
    build_stage1_markdown_report,
    evaluate_stage1_case,
    evaluate_stage1_gates,
    row_to_stage1_case,
    summarize_stage1_cases,
)

DEFAULT_TRAIN = (
    TRAINING_DIR / "curriculum" / "sft_v2_nodes_curriculum" / "stage1_evidence_copy" / "train.jsonl"
)
DEFAULT_EVAL = TRAINING_DIR / "curriculum" / "sft_v2_nodes_curriculum" / "eval.jsonl"
REPORT_JSON = TRAINING_DIR / "reports" / "stage1_evidence_copy_eval.json"
REPORT_MD = TRAINING_DIR / "reports" / "stage1_evidence_copy_eval.md"
FAILURE_JSONL = TRAINING_DIR / "reports" / "stage1_evidence_copy_failures.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validation_holdout_rows(
    rows: list[dict[str, Any]],
    *,
    seed: int = 42,
    validation_ratio: float = 0.1,
) -> list[dict[str, Any]]:
    shuffled = list(rows)
    random.Random(seed).shuffle(shuffled)
    validation_size = max(8, round(len(shuffled) * validation_ratio))
    validation_size = min(validation_size, len(shuffled))
    return shuffled[:validation_size]


def golden_to_stage1_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for row in rows:
        parsed = parse_train_sample(row)
        built = build_curriculum_row(parsed, stage="stage1_evidence_copy", stage_index=1)
        if built:
            built["id"] = f"{row.get('id') or 'golden'}::stage1_evidence_copy"
            converted.append(built)
    return converted


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
            "attention_mask": torch.ones((1, len(prompt_ids)), dtype=torch.long, device=model.device),
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


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Evaluate Stage 1 evidence-copy adapter")
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--train-dataset", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--golden-eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--max-length", type=int, default=1536)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--failure-jsonl", type=Path, default=FAILURE_JSONL)
    args = parser.parse_args()

    train_rows = load_jsonl(args.train_dataset)
    holdout_rows = validation_holdout_rows(train_rows)
    golden_stage1_rows = golden_to_stage1_rows(load_jsonl(args.golden_eval))

    suites: dict[str, list[EvalCaseInput]] = {
        "validation_holdout": [row_to_stage1_case(row, "validation_holdout") for row in holdout_rows],
        "golden_stage1": [row_to_stage1_case(row, "golden_stage1") for row in golden_stage1_rows],
    }
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
    case_results = [evaluate_stage1_case(case) for case in generated]
    by_case_id = {item["case_id"]: item for item in case_results}

    suite_reports: dict[str, Any] = {}
    for suite_name, suite_cases in suites.items():
        suite_results = [by_case_id[case.case_id] for case in suite_cases]
        suite_reports[suite_name] = {
            "aggregate": summarize_stage1_cases(suite_results),
            "cases": suite_results,
        }

    aggregate = summarize_stage1_cases(case_results)
    gates = evaluate_stage1_gates(aggregate)
    report = {
        "meta": {
            "evaluated_at": utc_now_iso(),
            "mode": "evidence_copy",
            "base_model": str(args.base_model),
            "adapter": str(args.adapter),
            "suites": list(suites.keys()),
            "case_count": len(case_results),
        },
        "aggregate": aggregate,
        "gates": gates,
        "suites": suite_reports,
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.report_md.write_text(build_stage1_markdown_report(report), encoding="utf-8")
    with args.failure_jsonl.open("w", encoding="utf-8") as handle:
        for case in case_results:
            for failure in case.get("failures") or []:
                handle.write(json.dumps(failure, ensure_ascii=False) + "\n")

    print(json.dumps({"aggregate": aggregate, "gates": gates}, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.report_json}")
    print(f"Wrote {args.report_md}")


if __name__ == "__main__":
    main()