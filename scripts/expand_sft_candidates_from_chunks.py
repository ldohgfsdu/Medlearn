#!/usr/bin/env python
"""Expand Tier A SFT dataset from pipeline chunks without lowering quality gates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sft_dataset import write_jsonl  # noqa: E402
from repair_sft_candidates import repair_one_row  # noqa: E402
from sft_candidate_generation_lib import (  # noqa: E402
    audit_manual_review_row,
    chunk_sample_to_row,
    generate_candidate_payload,
    load_chunk_index,
    make_sample_id,
    triage_unrepaired_row,
)
from sft_dataset_audit_lib import (  # noqa: E402
    audit_training_row,
    evaluate_decision_gate,
    load_cleaning_rules,
    load_jsonl,
    summarize_audit_results,
    utc_now_iso,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
DEFAULT_BASE_TRAIN = TRAINING_DIR / "data" / "sft_v2_repaired" / "train.jsonl"
DEFAULT_BASE_EVAL = TRAINING_DIR / "data" / "sft_v2_repaired" / "eval.jsonl"
DEFAULT_MANUAL_REVIEW = TRAINING_DIR / "data" / "sft_v2_repaired" / "manual_review.jsonl"
DEFAULT_UNREPAIRED = TRAINING_DIR / "data" / "sft_v2_repaired" / "unrepaired_candidates.jsonl"
DEFAULT_PIPELINE = PROJECT_ROOT / "generated" / "pipeline_v3"
DEFAULT_OUTPUT = TRAINING_DIR / "data" / "sft_v2_expanded"
DEFAULT_BASE_104 = TRAINING_DIR / "data" / "sft_v2_expanded" / "train.jsonl"
DEFAULT_OUTPUT_120 = TRAINING_DIR / "data" / "sft_v2_expanded_120"


def load_existing_ids(*paths: Path) -> set[str]:
    ids: set[str] = set()
    for path in paths:
        for row in load_jsonl(path):
            if row.get("id"):
                ids.add(str(row["id"]))
    return ids


def try_generate_accepted_row(
    sample: dict[str, Any],
    *,
    rules: dict[str, Any],
    min_nodes: int,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    payload, meta = generate_candidate_payload(sample, min_nodes=min_nodes)
    if payload is None:
        return None, meta
    row = chunk_sample_to_row(sample, payload)
    audit = audit_training_row(row, rules=rules, source_file="generated_chunk")
    row["tier"] = audit.get("tier")
    row["tier_label"] = audit.get("tier_label")
    row["audit_issues"] = audit.get("issues")
    row["evidence_exact_match_rate"] = audit.get("evidence_exact_match_rate")
    row["content_equals_evidence_rate"] = audit.get("content_equals_evidence_rate")
    row["generation_meta"] = meta
    if audit.get("tier") == "A":
        return row, meta
    row["generation_meta"] = {**meta, "post_audit_tier": audit.get("tier")}
    return None, row["generation_meta"]


def train_eval_overlap_count(train_rows: list[dict[str, Any]], eval_rows: list[dict[str, Any]]) -> int:
    train_ids = {str(row.get("id") or "") for row in train_rows if row.get("id")}
    eval_ids = {str(row.get("id") or "") for row in eval_rows if row.get("id")}
    return len(train_ids & eval_ids)


def build_frozen_markdown(
    manifest: dict[str, Any],
    *,
    version_name: str,
    rollback_version: str = "",
) -> str:
    rollback_ref = rollback_version or version_name
    lines = [
        f"# Frozen dataset: {version_name}",
        "",
        f"frozen_version: {version_name}",
        f"previous_version: {manifest.get('previous_version', '')}",
        f"frozen_at: {manifest.get('generated_at', '')}",
        f"accepted_samples: {manifest.get('total_accepted_samples', 0)}",
        f"golden_eval_samples: {manifest.get('golden_eval_samples', 0)}",
        (
            "evidence_exact_match_rate: "
            f"{manifest.get('evidence_exact_match_rate', 0.0) * 100:.2f}%"
        ),
        (
            "content_equals_evidence_rate: "
            f"{manifest.get('content_equals_evidence_rate', 0.0) * 100:.2f}%"
        ),
        f"avg_nodes_per_sample: {manifest.get('avg_nodes_per_sample', 0.0):.2f}",
        f"avg_aspects_per_sample: {manifest.get('avg_aspects_per_sample', 0.0):.2f}",
        f"ready_for_training: {str(manifest.get('ready_for_training', False)).lower()}",
        (
            "ready_for_training_recommended: "
            f"{str(manifest.get('ready_for_training_recommended', False)).lower()}"
        ),
        f"train_eval_overlap_count: {manifest.get('train_eval_overlap_count', 0)}",
        f"training_status: {manifest.get('training_status', 'not_started')}",
        "",
        "## Rollback",
        "",
        f"Baseline train: `training/data/{rollback_ref}/train.jsonl`",
    ]
    return "\n".join(lines) + "\n"


def evaluate_recommended_gate(aggregate: dict[str, Any], total_accepted: int) -> dict[str, Any]:
    blockers: list[str] = []
    if total_accepted < 100:
        blockers.append(f"accepted_samples={total_accepted}<100")
    if total_accepted < 120:
        blockers.append(f"accepted_samples={total_accepted}<120_recommended")
    evidence = aggregate.get("evidence_exact_match_rate_mean", 0.0)
    if evidence < 0.95:
        blockers.append(f"evidence_exact_match_rate={evidence}<0.95")
    content_eq = aggregate.get("content_equals_evidence_rate_mean", 0.0)
    if content_eq > 0.05:
        blockers.append(f"content_equals_evidence_rate={content_eq}>0.05")
    avg_nodes = aggregate.get("avg_nodes_per_sample", 0.0)
    if avg_nodes < 3.5:
        blockers.append(f"avg_nodes_per_sample={avg_nodes}<3.5")
    avg_aspects = aggregate.get("avg_aspects_per_sample", 0.0)
    if avg_aspects < 3.5:
        blockers.append(f"avg_aspects_per_sample={avg_aspects}<3.5")
    min_ready = total_accepted >= 100 and evidence >= 0.9 and content_eq <= 0.1 and avg_nodes >= 3
    return {
        "ready_for_training_minimum": min_ready,
        "ready_for_training_recommended": not blockers,
        "blockers": blockers,
    }


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Expand Tier A dataset from pipeline chunks")
    parser.add_argument("--base-train", type=Path, default=DEFAULT_BASE_TRAIN)
    parser.add_argument("--base-eval", type=Path, default=DEFAULT_BASE_EVAL)
    parser.add_argument("--manual-review", type=Path, default=DEFAULT_MANUAL_REVIEW)
    parser.add_argument("--unrepaired", type=Path, default=DEFAULT_UNREPAIRED)
    parser.add_argument("--pipeline-dir", type=Path, default=DEFAULT_PIPELINE)
    parser.add_argument("--rules", type=Path, default=TRAINING_DIR / "data_cleaning_rules.yaml")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dataset-version", type=str, default="")
    parser.add_argument("--previous-version", type=str, default="")
    parser.add_argument("--min-nodes", type=int, default=3)
    parser.add_argument("--max-new-chunks", type=int, default=0, help="0 means all unused chunks")
    parser.add_argument("--write-frozen", action="store_true")
    parser.add_argument("--training-status", type=str, default="not_started")
    args = parser.parse_args()

    dataset_version = args.dataset_version or (
        "sft_v2_expanded_120" if args.output_dir.name == "sft_v2_expanded_120" else "sft_v2_expanded"
    )
    previous_version = args.previous_version or (
        "sft_v2_expanded_104" if dataset_version == "sft_v2_expanded_120" else "sft_v2_repaired"
    )

    rules = load_cleaning_rules(args.rules)
    base_train_rows = load_jsonl(args.base_train)
    base_eval_rows = load_jsonl(args.base_eval)
    manual_rows = load_jsonl(args.manual_review)
    unrepaired_rows = load_jsonl(args.unrepaired)
    chunk_index = load_chunk_index(args.pipeline_dir)

    baseline_ids = load_existing_ids(args.base_train)
    processed_ids = load_existing_ids(
        args.base_train,
        TRAINING_DIR / "data" / "sft_v2_repaired" / "repair_candidates.jsonl",
        args.manual_review,
        args.unrepaired,
    )

    manual_review_resolved: list[dict[str, Any]] = []
    accepted_manual: list[dict[str, Any]] = []
    for row in manual_rows:
        audit = audit_manual_review_row(row, chunk_index)
        manual_review_resolved.append(audit)
        if audit["disposition"] != "rescuable_truncation":
            continue
        sample = chunk_index.get(audit["sample_id"])
        if not sample:
            continue
        accepted_row, _ = try_generate_accepted_row(
            sample,
            rules=rules,
            min_nodes=args.min_nodes,
        )
        if accepted_row:
            audit["resolution"] = "promoted_to_tier_a"
            accepted_manual.append(accepted_row)

    unrepaired_triage: list[dict[str, Any]] = []
    accepted_unrepaired: list[dict[str, Any]] = []
    repair_candidates_new: list[dict[str, Any]] = []
    for row in unrepaired_rows:
        triage = triage_unrepaired_row(row, chunk_index)
        unrepaired_triage.append(triage)
        sample_id = triage["sample_id"]
        sample = chunk_index.get(sample_id)

        if triage["triage_bucket"] == "B1_deterministic_repair":
            outcome = repair_one_row(row, rules=rules, min_nodes=args.min_nodes)
            if outcome.get("status") == "repaired" and outcome.get("after_audit", {}).get("tier") == "A":
                accepted_unrepaired.append(outcome["row"])
                triage["resolution"] = "promoted_via_b1_repair"
            else:
                repair_candidates_new.append(row)
                triage["resolution"] = "still_repair_candidate"
        elif triage["triage_bucket"] == "B2_reextract_from_chunk" and sample:
            accepted_row, _ = try_generate_accepted_row(
                sample,
                rules=rules,
                min_nodes=args.min_nodes,
            )
            if accepted_row:
                accepted_unrepaired.append(accepted_row)
                triage["resolution"] = "promoted_via_b2_reextract"
            else:
                repair_candidates_new.append(row)
                triage["resolution"] = "reextract_failed"
        else:
            triage["resolution"] = "discarded_b3"

    new_candidates: list[dict[str, Any]] = []
    accepted_new: list[dict[str, Any]] = []
    rejected_new: list[dict[str, Any]] = []
    manual_review_new: list[dict[str, Any]] = []

    unused_samples = [
        sample
        for sample_id, sample in chunk_index.items()
        if sample_id not in baseline_ids
    ]
    if args.max_new_chunks > 0:
        unused_samples = unused_samples[: args.max_new_chunks]

    for sample in unused_samples:
        sample_id = make_sample_id(sample["source_file"], sample["chunk_id"])
        row, meta = try_generate_accepted_row(sample, rules=rules, min_nodes=args.min_nodes)
        candidate_record = {
            "id": sample_id,
            "generation_meta": meta,
            "processed_before": sample_id in processed_ids,
        }
        new_candidates.append(candidate_record)
        if row:
            accepted_new.append(row)
        elif meta.get("reject_reason"):
            rejected_new.append({**candidate_record, "reject_reason": meta["reject_reason"]})
        else:
            manual_review_new.append(candidate_record)

    def dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            sample_id = str(row.get("id") or "")
            if not sample_id or sample_id in seen:
                continue
            seen.add(sample_id)
            deduped.append(row)
        return deduped

    incremental_accepted = dedupe_rows(accepted_manual + accepted_unrepaired + accepted_new)
    base_train_ids = {str(row.get("id") or "") for row in base_train_rows if row.get("id")}
    incremental_only = [
        row for row in incremental_accepted if str(row.get("id") or "") not in base_train_ids
    ]
    final_train_rows = dedupe_rows(base_train_rows + incremental_accepted)
    manual_ids = {str(row.get("id") or "") for row in accepted_manual}
    unrepaired_ids = {str(row.get("id") or "") for row in accepted_unrepaired}
    expansion_diff = []
    for row in incremental_only:
        sample_id = str(row.get("id") or "")
        if sample_id in manual_ids:
            source = "manual_review"
        elif sample_id in unrepaired_ids:
            source = "unrepaired"
        else:
            source = "new_chunks"
        expansion_diff.append(
            {
                "id": sample_id,
                "source": source,
                "generation_method": row.get("generation_method"),
                "node_count": row.get("node_count"),
            }
        )

    final_audits = [
        audit_training_row(row, rules=rules, source_file="final_train") for row in final_train_rows
    ]
    final_aggregate = summarize_audit_results(final_audits)
    minimum_gate = evaluate_decision_gate(
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
    recommended_gate = evaluate_recommended_gate(final_aggregate, len(final_train_rows))

    overlap_count = train_eval_overlap_count(final_train_rows, base_eval_rows)
    accepted_from_existing = len(base_train_rows) if previous_version.startswith("sft_v2_expanded") else 0

    manifest = {
        "version": dataset_version,
        "previous_version": previous_version,
        "source_version": previous_version if accepted_from_existing else "sft_v2_repaired",
        "generated_at": utc_now_iso(),
        "previous_tier_a": len(base_train_rows),
        "accepted_from_existing_104": accepted_from_existing,
        "accepted_from_manual_review": len(accepted_manual),
        "accepted_from_unrepaired": len(accepted_unrepaired),
        "accepted_from_new_chunks": len(accepted_new),
        "incremental_accepted_samples": len(incremental_only),
        "total_accepted_samples": len(final_train_rows),
        "train_eval_overlap_count": overlap_count,
        "training_status": args.training_status,
        "new_candidates_scanned": len(new_candidates),
        "rejected_new_samples": len(rejected_new),
        "repair_candidates_new_samples": len(repair_candidates_new),
        "manual_review_new_samples": len(manual_review_new),
        "evidence_exact_match_rate": final_aggregate.get("evidence_exact_match_rate_mean", 0.0),
        "content_equals_evidence_rate": final_aggregate.get("content_equals_evidence_rate_mean", 0.0),
        "avg_nodes_per_sample": final_aggregate.get("avg_nodes_per_sample", 0.0),
        "avg_aspects_per_sample": final_aggregate.get("avg_aspects_per_sample", 0.0),
        "ready_for_training": minimum_gate.get("ready_for_training", False),
        "ready_for_training_recommended": recommended_gate.get("ready_for_training_recommended", False),
        "decision_gate_minimum": minimum_gate,
        "decision_gate_recommended": recommended_gate,
        "golden_eval_samples": len(base_eval_rows),
        "outputs": {},
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(args.output_dir / "manual_review_resolved.jsonl", manual_review_resolved)
    write_jsonl(args.output_dir / "unrepaired_triage.jsonl", unrepaired_triage)
    write_jsonl(args.output_dir / "new_candidates.jsonl", new_candidates)
    write_jsonl(args.output_dir / "accepted_new.jsonl", accepted_new)
    write_jsonl(args.output_dir / "rejected_new.jsonl", rejected_new)
    write_jsonl(args.output_dir / "repair_candidates_new.jsonl", repair_candidates_new)
    write_jsonl(args.output_dir / "manual_review_new.jsonl", manual_review_new)
    write_jsonl(args.output_dir / "train.jsonl", final_train_rows)
    write_jsonl(args.output_dir / "eval.jsonl", base_eval_rows)
    write_jsonl(args.output_dir / "expansion_diff.jsonl", expansion_diff)

    manifest["outputs"] = {
        "manual_review_resolved": str(args.output_dir / "manual_review_resolved.jsonl"),
        "unrepaired_triage": str(args.output_dir / "unrepaired_triage.jsonl"),
        "new_candidates": str(args.output_dir / "new_candidates.jsonl"),
        "accepted_new": str(args.output_dir / "accepted_new.jsonl"),
        "rejected_new": str(args.output_dir / "rejected_new.jsonl"),
        "repair_candidates_new": str(args.output_dir / "repair_candidates_new.jsonl"),
        "manual_review_new": str(args.output_dir / "manual_review_new.jsonl"),
        "train": str(args.output_dir / "train.jsonl"),
        "eval": str(args.output_dir / "eval.jsonl"),
        "expansion_diff": str(args.output_dir / "expansion_diff.jsonl"),
    }
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "VERSION").write_text(f"{dataset_version}\n", encoding="utf-8")
    if args.write_frozen or dataset_version.endswith("_120"):
        rollback_version = (
            "sft_v2_expanded" if previous_version == "sft_v2_expanded_104" else previous_version
        )
        frozen_md = build_frozen_markdown(
            manifest,
            version_name=dataset_version,
            rollback_version=rollback_version,
        )
        (args.output_dir / "FROZEN.md").write_text(frozen_md, encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()