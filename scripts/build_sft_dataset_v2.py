#!/usr/bin/env python
"""Build versioned SFT v2 candidate dataset from cleaning rules."""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from build_sft_dataset import (  # noqa: E402
    build_user_prompt,
    clean_source_text,
    compact_json,
    format_chat_text,
    iter_pipeline_chunks,
    write_jsonl,
)
from sft_dataset_audit_lib import (  # noqa: E402
    audit_training_row,
    extract_prompt_and_expected,
    load_cleaning_rules,
    load_jsonl,
    summarize_audit_results,
    utc_now_iso,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
DEFAULT_OUTPUT = TRAINING_DIR / "data" / "sft_v2"
DEFAULT_TRAIN_V1 = TRAINING_DIR / "sft_train.jsonl"
DEFAULT_GOLDEN_EVAL = TRAINING_DIR / "sft_smoke_eval.jsonl"


def build_v2_row(
    row: dict[str, Any],
    *,
    audited: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    _, payload = extract_prompt_and_expected(row)
    payload = payload or {"nodes": [], "edges": []}
    optional_edges = list(payload.get("edges") or [])
    nodes_only = {"nodes": list(payload.get("nodes") or []), "edges": []}

    full_text = str(row.get("text") or "")
    if "<|im_start|>assistant\n" in full_text:
        prompt_part = full_text.split("<|im_start|>assistant\n", 1)[0] + "<|im_start|>assistant\n"
        text = prompt_part + compact_json(nodes_only) + "<|im_end|>"
    else:
        text = full_text

    training_focus = rules.get("training_focus") or {}
    record = {
        "id": row.get("id"),
        "source_file": row.get("source_file"),
        "chunk_id": row.get("chunk_id"),
        "task": "pipeline_v3_extract_v2_nodes",
        "text": text,
        "node_count": len(nodes_only["nodes"]),
        "edge_count": 0,
        "optional_edges": optional_edges,
        "tier": audited.get("tier"),
        "tier_label": audited.get("tier_label"),
        "audit_issues": audited.get("issues"),
        "evidence_exact_match_rate": audited.get("evidence_exact_match_rate"),
        "content_equals_evidence_rate": audited.get("content_equals_evidence_rate"),
        "training_focus": training_focus.get("primary_target", "nodes"),
    }
    if row.get("salvaged_from_partial_chunk"):
        record["salvaged_from_partial_chunk"] = True
    return record


def pipeline_sample_to_row(sample: dict[str, Any]) -> dict[str, Any]:
    source_text = clean_source_text(sample["content"])
    payload = {"nodes": sample["nodes"], "edges": sample["edges"]}
    user_prompt = build_user_prompt(sample["headings"], source_text)
    return {
        "id": f"{sample['source_file']}::{sample['chunk_id']}",
        "source_file": sample["source_file"],
        "chunk_id": sample["chunk_id"],
        "task": "pipeline_v3_extract",
        "text": format_chat_text(user_prompt, compact_json(payload)),
    }


def build_v2_eval_rows(golden_path: Path, *, rules: dict[str, Any]) -> list[dict[str, Any]]:
    eval_rows: list[dict[str, Any]] = []
    for row in load_jsonl(golden_path):
        try:
            source_name = str(golden_path.relative_to(PROJECT_ROOT))
        except ValueError:
            source_name = str(golden_path)
        audited = audit_training_row(row, rules=rules, source_file=source_name)
        v2_row = build_v2_row(row, audited=audited, rules=rules)
        v2_row["task"] = "pipeline_v3_extract_v2_eval"
        v2_row["golden_title"] = row.get("golden_title")
        v2_row["expected"] = row.get("expected")
        eval_rows.append(v2_row)
    return eval_rows


def build_dataset_v2(
    *,
    train_v1_path: Path,
    golden_eval_path: Path,
    pipeline_dir: Path,
    output_dir: Path,
    rules_path: Path,
    include_pipeline: bool,
    eval_holdout_rate: float,
    seed: int,
) -> dict[str, Any]:
    rules = load_cleaning_rules(rules_path)
    rows_to_audit: list[tuple[dict[str, Any], dict[str, Any]]] = []

    for row in load_jsonl(train_v1_path):
        try:
            source_name = str(train_v1_path.relative_to(PROJECT_ROOT))
        except ValueError:
            source_name = str(train_v1_path)
        audited = audit_training_row(row, rules=rules, source_file=source_name)
        rows_to_audit.append((row, audited))

    if include_pipeline and pipeline_dir.exists():
        seen_ids = {str(row.get("id")) for row, _ in rows_to_audit}
        for sample in iter_pipeline_chunks(pipeline_dir):
            sample_id = f"{sample['source_file']}::{sample['chunk_id']}"
            if sample_id in seen_ids:
                continue
            row = pipeline_sample_to_row(sample)
            audited = audit_training_row(
                row,
                rules=rules,
                source_file="generated/pipeline_v3",
            )
            rows_to_audit.append((row, audited))

    accepted: list[dict[str, Any]] = []
    repair_candidates: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for row, audited in rows_to_audit:
        v2_row = build_v2_row(row, audited=audited, rules=rules)
        tier = audited.get("tier")
        if tier == "A":
            accepted.append(v2_row)
        elif tier == "B":
            repair_candidates.append(v2_row)
        else:
            rejected.append(v2_row)

    rng = random.Random(seed)
    rng.shuffle(accepted)
    holdout_size = max(1, round(len(accepted) * eval_holdout_rate)) if accepted else 0
    internal_eval = accepted[:holdout_size]
    train_rows = accepted[holdout_size:]

    eval_rows = build_v2_eval_rows(golden_eval_path, rules=rules)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "train.jsonl", train_rows)
    write_jsonl(output_dir / "eval.jsonl", eval_rows)
    write_jsonl(output_dir / "rejected.jsonl", rejected)
    write_jsonl(output_dir / "repair_candidates.jsonl", repair_candidates)

    all_accepted_metrics = summarize_audit_results(
        [
            {
                "tier": "A",
                "node_count": row.get("node_count", 0),
                "unique_aspect_count": row.get("node_count", 0),
                "evidence_exact_match_rate": row.get("evidence_exact_match_rate", 0.0),
                "content_equals_evidence_rate": row.get("content_equals_evidence_rate", 0.0),
            }
            for row in accepted
        ]
    )
    total_samples = len(rows_to_audit)
    manifest = {
        "version": "sft_v2",
        "source_version": "sft_v1",
        "generated_at": utc_now_iso(),
        "rules_version": rules.get("version"),
        "total_samples": total_samples,
        "accepted_samples": len(accepted),
        "train_samples": len(train_rows),
        "internal_eval_samples": len(internal_eval),
        "golden_eval_samples": len(eval_rows),
        "repair_candidates": len(repair_candidates),
        "rejected_samples": len(rejected),
        "acceptance_rate": round(len(accepted) / total_samples, 4) if total_samples else 0.0,
        "evidence_exact_match_rate": all_accepted_metrics.get(
            "evidence_exact_match_rate_mean",
            0.0,
        ),
        "content_equals_evidence_rate": all_accepted_metrics.get(
            "content_equals_evidence_rate_mean",
            0.0,
        ),
        "avg_nodes_per_sample": all_accepted_metrics.get("avg_nodes_per_sample", 0.0),
        "avg_aspects_per_sample": all_accepted_metrics.get("avg_aspects_per_sample", 0.0),
        "training_focus": rules.get("training_focus"),
        "outputs": {
            "train": str(output_dir / "train.jsonl"),
            "eval": str(output_dir / "eval.jsonl"),
            "rejected": str(output_dir / "rejected.jsonl"),
            "repair_candidates": str(output_dir / "repair_candidates.jsonl"),
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build SFT v2 candidate dataset")
    parser.add_argument("--train-v1", type=Path, default=DEFAULT_TRAIN_V1)
    parser.add_argument("--golden-eval", type=Path, default=DEFAULT_GOLDEN_EVAL)
    parser.add_argument(
        "--pipeline-dir",
        type=Path,
        default=PROJECT_ROOT / "generated" / "pipeline_v3",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--rules",
        type=Path,
        default=TRAINING_DIR / "data_cleaning_rules.yaml",
    )
    parser.add_argument("--include-pipeline", action="store_true")
    parser.add_argument("--eval-holdout-rate", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    manifest = build_dataset_v2(
        train_v1_path=args.train_v1,
        golden_eval_path=args.golden_eval,
        pipeline_dir=args.pipeline_dir,
        output_dir=args.output_dir,
        rules_path=args.rules,
        include_pipeline=args.include_pipeline,
        eval_holdout_rate=args.eval_holdout_rate,
        seed=args.seed,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()