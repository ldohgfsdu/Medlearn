#!/usr/bin/env python
"""Repair SFT v2 B-tier candidates without training."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sft_dataset import write_jsonl  # noqa: E402
from sft_dataset_audit_lib import (  # noqa: E402
    audit_training_row,
    evaluate_decision_gate,
    extract_chapter_path,
    extract_source_text,
    load_cleaning_rules,
    load_jsonl,
    parse_row_payload,
    summarize_audit_results,
    utc_now_iso,
)
from sft_repair_lib import (  # noqa: E402
    build_repaired_row,
    repair_payload,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
DEFAULT_INPUT = TRAINING_DIR / "data" / "sft_v2" / "repair_candidates.jsonl"
DEFAULT_BASE_TRAIN = TRAINING_DIR / "data" / "sft_v2" / "train.jsonl"
DEFAULT_BASE_EVAL = TRAINING_DIR / "data" / "sft_v2" / "eval.jsonl"
DEFAULT_BASE_REJECTED = TRAINING_DIR / "data" / "sft_v2" / "rejected.jsonl"
DEFAULT_OUTPUT = TRAINING_DIR / "data" / "sft_v2_repaired"


def count_issue(results: list[dict[str, Any]], issue: str) -> int:
    return sum(1 for item in results if issue in (item.get("issues") or []))


def repair_one_row(
    row: dict[str, Any],
    *,
    rules: dict[str, Any],
    min_nodes: int,
) -> dict[str, Any]:
    source_text, chapter_path, payload, _ = parse_row_payload(row)
    if payload is None:
        return {
            "status": "manual_review",
            "reason": "invalid_json",
            "before_audit": None,
            "after_audit": None,
            "repair_actions": [],
            "row": row,
            "diff": {"sample_id": row.get("id"), "error": "invalid_json"},
        }

    before_audit = audit_training_row(row, rules=rules, source_file="repair_input")
    repaired_payload, repair_actions = repair_payload(
        {
            "nodes": payload.get("nodes") or [],
            "edges": [],
            "optional_edges": row.get("optional_edges") or payload.get("edges") or [],
        },
        source_text=source_text,
        chapter_path=chapter_path,
        min_nodes=min_nodes,
    )

    candidate_row = build_repaired_row(
        row,
        repaired_payload,
        repair_actions=repair_actions,
        audit_after={"tier": "B"},
    )
    after_audit = audit_training_row(candidate_row, rules=rules, source_file="repair_output")
    candidate_row = build_repaired_row(
        row,
        repaired_payload,
        repair_actions=repair_actions,
        audit_after=after_audit,
    )

    diff = {
        "sample_id": row.get("id"),
        "repair_actions": repair_actions,
        "tier_before": before_audit.get("tier"),
        "tier_after": after_audit.get("tier"),
        "issues_before": before_audit.get("issues"),
        "issues_after": after_audit.get("issues"),
        "node_count_before": before_audit.get("node_count"),
        "node_count_after": after_audit.get("node_count"),
        "content_equals_evidence_rate_before": before_audit.get("content_equals_evidence_rate"),
        "content_equals_evidence_rate_after": after_audit.get("content_equals_evidence_rate"),
        "evidence_exact_match_rate_after": after_audit.get("evidence_exact_match_rate"),
        "nodes_before": payload.get("nodes"),
        "nodes_after": repaired_payload.get("nodes"),
    }

    if after_audit.get("tier") == "A":
        status = "repaired"
    elif after_audit.get("tier") == "C":
        if after_audit.get("hard_reject_reasons"):
            status = "manual_review"
        else:
            status = "manual_review"
    elif repair_actions:
        status = "unrepaired"
    else:
        status = "manual_review"

    return {
        "status": status,
        "before_audit": before_audit,
        "after_audit": after_audit,
        "repair_actions": repair_actions,
        "row": candidate_row,
        "diff": diff,
    }


def build_repair_manifest(
    *,
    input_rows: list[dict[str, Any]],
    outcomes: list[dict[str, Any]],
    promoted_rows: list[dict[str, Any]],
    base_train_rows: list[dict[str, Any]],
    final_train_rows: list[dict[str, Any]],
    rules: dict[str, Any],
) -> dict[str, Any]:
    before_audits = [item["before_audit"] for item in outcomes if item.get("before_audit")]
    after_audits = [item["after_audit"] for item in outcomes if item.get("after_audit")]

    promoted_audits = [
        audit_training_row(row, rules=rules, source_file="promoted")
        for row in promoted_rows
    ]
    final_audits = [
        audit_training_row(row, rules=rules, source_file="final_train")
        for row in final_train_rows
    ]

    status_counts = {
        "repaired": sum(1 for item in outcomes if item["status"] == "repaired"),
        "unrepaired": sum(1 for item in outcomes if item["status"] == "unrepaired"),
        "manual_review": sum(1 for item in outcomes if item["status"] == "manual_review"),
    }

    aggregate_after = summarize_audit_results(promoted_audits) if promoted_audits else {}
    final_aggregate = summarize_audit_results(final_audits) if final_audits else {}
    decision = evaluate_decision_gate(
        {
            "tier_a_accepted": len(final_train_rows),
            "evidence_exact_match_rate_mean": final_aggregate.get(
                "evidence_exact_match_rate_mean",
                0.0,
            ),
            "content_equals_evidence_rate_mean": final_aggregate.get(
                "content_equals_evidence_rate_mean",
                0.0,
            ),
            "avg_nodes_per_sample": final_aggregate.get("avg_nodes_per_sample", 0.0),
        },
        rules,
    )

    return {
        "version": "sft_v2_repaired",
        "source_version": "sft_v2",
        "generated_at": utc_now_iso(),
        "input_repair_candidates": len(input_rows),
        "repaired_samples": status_counts["repaired"],
        "unrepaired_samples": status_counts["unrepaired"],
        "manual_review_samples": status_counts["manual_review"],
        "promoted_to_tier_a": status_counts["repaired"],
        "still_tier_b": status_counts["unrepaired"],
        "hard_rejected_after_repair": sum(
            1
            for item in outcomes
            if (item.get("after_audit") or {}).get("tier") == "C"
        ),
        "content_equals_evidence_before": count_issue(before_audits, "content_equals_evidence"),
        "content_equals_evidence_after": count_issue(after_audits, "content_equals_evidence"),
        "single_summary_node_before": count_issue(before_audits, "single_summary_node"),
        "single_summary_node_after": count_issue(after_audits, "single_summary_node"),
        "aspect_imbalance_before": count_issue(before_audits, "aspect_imbalance"),
        "aspect_imbalance_after": count_issue(after_audits, "aspect_imbalance"),
        "evidence_exact_match_rate_after": aggregate_after.get(
            "evidence_exact_match_rate_mean",
            0.0,
        ),
        "avg_nodes_per_sample_after": aggregate_after.get("avg_nodes_per_sample", 0.0),
        "avg_aspects_per_sample_after": aggregate_after.get("avg_aspects_per_sample", 0.0),
        "base_train_samples": len(base_train_rows),
        "final_train_samples": len(final_train_rows),
        "ready_for_training": decision.get("ready_for_training", False),
        "decision_gate_blockers": decision.get("blockers", []),
        "outputs": {},
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Repair SFT v2 B-tier candidates")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--base-train", type=Path, default=DEFAULT_BASE_TRAIN)
    parser.add_argument("--base-eval", type=Path, default=DEFAULT_BASE_EVAL)
    parser.add_argument("--base-rejected", type=Path, default=DEFAULT_BASE_REJECTED)
    parser.add_argument("--rules", type=Path, default=TRAINING_DIR / "data_cleaning_rules.yaml")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--min-nodes", type=int, default=3)
    args = parser.parse_args()

    rules = load_cleaning_rules(args.rules)
    input_rows = load_jsonl(args.input)
    base_train_rows = load_jsonl(args.base_train)
    base_eval_rows = load_jsonl(args.base_eval)
    base_rejected_rows = load_jsonl(args.base_rejected)

    outcomes = [
        repair_one_row(row, rules=rules, min_nodes=args.min_nodes) for row in input_rows
    ]

    repaired_rows = [item["row"] for item in outcomes if item["status"] == "repaired"]
    unrepaired_rows = [item["row"] for item in outcomes if item["status"] == "unrepaired"]
    manual_review_rows = [
        {**item["row"], "manual_review_reason": item.get("reason") or item["status"]}
        for item in outcomes
        if item["status"] == "manual_review"
    ]
    repair_diffs = [item["diff"] for item in outcomes]

    final_train_rows = base_train_rows + repaired_rows
    args.output_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(args.output_dir / "repaired_candidates.jsonl", repaired_rows)
    write_jsonl(args.output_dir / "unrepaired_candidates.jsonl", unrepaired_rows)
    write_jsonl(args.output_dir / "manual_review.jsonl", manual_review_rows)
    write_jsonl(args.output_dir / "repair_diff.jsonl", repair_diffs)
    write_jsonl(args.output_dir / "train.jsonl", final_train_rows)
    write_jsonl(args.output_dir / "eval.jsonl", base_eval_rows)
    write_jsonl(args.output_dir / "rejected.jsonl", base_rejected_rows)
    write_jsonl(args.output_dir / "repair_candidates.jsonl", unrepaired_rows)

    manifest = build_repair_manifest(
        input_rows=input_rows,
        outcomes=outcomes,
        promoted_rows=repaired_rows,
        base_train_rows=base_train_rows,
        final_train_rows=final_train_rows,
        rules=rules,
    )
    manifest["outputs"] = {
        "repaired_candidates": str(args.output_dir / "repaired_candidates.jsonl"),
        "unrepaired_candidates": str(args.output_dir / "unrepaired_candidates.jsonl"),
        "manual_review": str(args.output_dir / "manual_review.jsonl"),
        "repair_diff": str(args.output_dir / "repair_diff.jsonl"),
        "train": str(args.output_dir / "train.jsonl"),
        "eval": str(args.output_dir / "eval.jsonl"),
        "rejected": str(args.output_dir / "rejected.jsonl"),
        "repair_candidates": str(args.output_dir / "repair_candidates.jsonl"),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()