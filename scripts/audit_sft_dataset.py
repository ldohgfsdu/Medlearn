#!/usr/bin/env python
"""Audit SFT training data quality and derive A/B/C tier classifications."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sft_dataset import iter_pipeline_chunks  # noqa: E402
from sft_dataset_audit_lib import (  # noqa: E402
    audit_metadata_only_row,
    audit_training_row,
    bridge_eval_failures,
    build_audit_markdown,
    discover_dataset_files,
    evaluate_decision_gate,
    load_cleaning_rules,
    load_jsonl,
    recommendation_text,
    summarize_audit_results,
    utc_now_iso,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
DEFAULT_SOURCES = [
    TRAINING_DIR / "sft_train.jsonl",
    TRAINING_DIR / "sft_smoke_eval.jsonl",
    TRAINING_DIR / "rejected_samples.jsonl",
]
REPORT_JSON = TRAINING_DIR / "reports" / "sft_dataset_audit_report.json"
REPORT_MD = TRAINING_DIR / "reports" / "sft_dataset_audit_report.md"
FAILURE_JSONL = TRAINING_DIR / "reports" / "sft_dataset_failure_cases.jsonl"
EVAL_REPORT = TRAINING_DIR / "reports" / "sft_eval_report.json"
EVAL_FAILURES = TRAINING_DIR / "reports" / "sft_failure_cases.jsonl"


def audit_pipeline_raw(
    pipeline_dir: Path,
    *,
    rules: dict[str, Any],
) -> list[dict[str, Any]]:
    from build_sft_dataset import build_user_prompt, clean_source_text, compact_json, format_chat_text

    results: list[dict[str, Any]] = []
    for sample in iter_pipeline_chunks(pipeline_dir):
        source_text = clean_source_text(sample["content"])
        payload = {"nodes": sample["nodes"], "edges": sample["edges"]}
        user_prompt = build_user_prompt(sample["headings"], source_text)
        row = {
            "id": f"{sample['source_file']}::{sample['chunk_id']}",
            "text": format_chat_text(user_prompt, compact_json(payload)),
            "source_file": sample["source_file"],
            "chunk_id": sample["chunk_id"],
        }
        audited = audit_training_row(row, rules=rules, source_file="generated/pipeline_v3")
        audited["origin"] = "pipeline_raw"
        results.append(audited)
    return results


def write_failure_jsonl(path: Path, results: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for sample in results:
            for failure in sample.get("failures") or []:
                handle.write(
                    json.dumps(
                        {
                            "sample_id": sample.get("sample_id"),
                            "source_file": sample.get("source_file"),
                            "tier": sample.get("tier"),
                            **failure,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )


def collect_source_files(args: argparse.Namespace) -> list[tuple[Path, str]]:
    sources: list[tuple[Path, str]] = []
    for path in args.sources or []:
        if path.exists():
            sources.append((path, str(path.relative_to(PROJECT_ROOT))))

    data_dir = TRAINING_DIR / "data"
    for path in discover_dataset_files(data_dir):
        rel = str(path.relative_to(PROJECT_ROOT))
        if (path, rel) not in sources:
            sources.append((path, rel))

    return sources


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Audit SFT dataset quality")
    parser.add_argument(
        "--rules",
        type=Path,
        default=TRAINING_DIR / "data_cleaning_rules.yaml",
    )
    parser.add_argument(
        "--sources",
        type=Path,
        nargs="*",
        default=DEFAULT_SOURCES,
    )
    parser.add_argument(
        "--pipeline-dir",
        type=Path,
        default=PROJECT_ROOT / "generated" / "pipeline_v3",
    )
    parser.add_argument("--include-pipeline-raw", action="store_true")
    parser.add_argument("--eval-report", type=Path, default=EVAL_REPORT)
    parser.add_argument("--eval-failures", type=Path, default=EVAL_FAILURES)
    parser.add_argument("--report-json", type=Path, default=REPORT_JSON)
    parser.add_argument("--report-md", type=Path, default=REPORT_MD)
    parser.add_argument("--failure-jsonl", type=Path, default=FAILURE_JSONL)
    args = parser.parse_args()

    rules = load_cleaning_rules(args.rules)
    source_files = collect_source_files(args)

    per_source_results: dict[str, list[dict[str, Any]]] = {}
    all_results: list[dict[str, Any]] = []

    for path, rel_name in source_files:
        rows = load_jsonl(path)
        audited = []
        for row in rows:
            if row.get("text"):
                audited.append(
                    audit_training_row(row, rules=rules, source_file=rel_name)
                )
            else:
                audited.append(
                    audit_metadata_only_row(row, source_file=rel_name)
                )
        per_source_results[rel_name] = audited
        all_results.extend(audited)

    pipeline_raw_results: list[dict[str, Any]] = []
    if args.include_pipeline_raw and args.pipeline_dir.exists():
        pipeline_raw_results = audit_pipeline_raw(args.pipeline_dir, rules=rules)

    train_results = []
    for key, value in per_source_results.items():
        if key.endswith("sft_train.jsonl"):
            train_results = value
            break
    train_aggregate = summarize_audit_results(train_results)
    aggregate = summarize_audit_results(all_results)
    eval_bridge = bridge_eval_failures(args.eval_report, args.eval_failures)
    decision = evaluate_decision_gate(train_aggregate, rules)

    report = {
        "meta": {
            "generated_at": utc_now_iso(),
            "rules_version": rules.get("version"),
            "rules_path": str(args.rules),
            "sources": [name for _, name in source_files],
            "include_pipeline_raw": args.include_pipeline_raw,
        },
        "aggregate": aggregate,
        "train_v1_aggregate": train_aggregate,
        "per_source": {
            name: {
                "aggregate": summarize_audit_results(items),
                "samples": items,
            }
            for name, items in per_source_results.items()
        },
        "pipeline_raw_aggregate": summarize_audit_results(pipeline_raw_results)
        if pipeline_raw_results
        else None,
        "eval_failure_bridge": eval_bridge,
        "decision_gate": decision,
        "recommendation": recommendation_text(decision, train_aggregate),
    }

    args.report_json.parent.mkdir(parents=True, exist_ok=True)
    args.report_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    args.report_md.write_text(build_audit_markdown(report), encoding="utf-8")
    write_failure_jsonl(args.failure_jsonl, all_results)

    print(json.dumps(train_aggregate, ensure_ascii=False, indent=2))
    print(f"\nDecision gate ready_for_training: {decision['ready_for_training']}")
    print(f"Recommendation: {report['recommendation']}")
    print(f"\nWrote {args.report_json}")
    print(f"Wrote {args.report_md}")
    print(f"Wrote {args.failure_jsonl}")


if __name__ == "__main__":
    main()