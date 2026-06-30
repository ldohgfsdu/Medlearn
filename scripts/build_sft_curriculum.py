#!/usr/bin/env python
"""Build three-stage evidence-copy curriculum from frozen Tier A dataset."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

from audit_sft_dataset_distribution import audit_distribution  # noqa: E402
from build_sft_dataset import write_jsonl  # noqa: E402
from sft_curriculum_lib import (  # noqa: E402
    build_curriculum_row,
    build_sampling_policy,
    parse_train_sample,
)
from sft_dataset_audit_lib import load_jsonl, utc_now_iso  # noqa: E402

DEFAULT_TRAIN = TRAINING_DIR / "data" / "sft_v2_expanded_182" / "train.jsonl"
DEFAULT_EVAL = TRAINING_DIR / "data" / "sft_v2_expanded_182" / "eval.jsonl"
DEFAULT_OUTPUT = TRAINING_DIR / "curriculum" / "sft_v2_nodes_curriculum"
DEFAULT_DISTRIBUTION = TRAINING_DIR / "reports" / "sft_v2_expanded_182_distribution.json"

STAGES = (
    ("stage1_evidence_copy", 1),
    ("stage2_evidence_content_distill", 2),
    ("stage3_full_nodes_only", 3),
)


def build_stage_rows(train_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    stage_rows: dict[str, list[dict[str, Any]]] = {stage: [] for stage, _ in STAGES}
    skipped: list[dict[str, Any]] = []

    for row in train_rows:
        parsed = parse_train_sample(row)
        built_any = False
        for stage_name, stage_index in STAGES:
            curriculum_row = build_curriculum_row(parsed, stage=stage_name, stage_index=stage_index)
            if curriculum_row:
                stage_rows[stage_name].append(curriculum_row)
                built_any = True
        if not built_any:
            skipped.append({"id": parsed["id"], "reason": "curriculum_build_failed"})

    return stage_rows


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Build evidence-copy curriculum stages")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--distribution-report", type=Path, default=DEFAULT_DISTRIBUTION)
    args = parser.parse_args()

    train_rows = load_jsonl(args.train)
    eval_rows = load_jsonl(args.eval)
    stage_rows = build_stage_rows(train_rows)

    distribution_report: dict[str, Any]
    if args.distribution_report.exists():
        distribution_report = json.loads(args.distribution_report.read_text(encoding="utf-8"))
    else:
        distribution_report = audit_distribution(train_rows)

    sampling_policy = build_sampling_policy(distribution_report)
    manifest = {
        "curriculum_version": "sft_v2_nodes_curriculum_v1",
        "dataset_version": "sft_v2_expanded_182",
        "generated_at": utc_now_iso(),
        "source_train_samples": len(train_rows),
        "golden_eval_samples": len(eval_rows),
        "golden_in_curriculum_train": False,
        "stages": {
            stage: {
                "rows": len(stage_rows[stage]),
                "directory": str(args.output_dir / stage),
            }
            for stage, _ in STAGES
        },
        "smoke_checkpoint_target": "training/checkpoints/qwen3-0.6b-medlearn-lora-nodes-v2-smoke/",
        "production_checkpoint_protected": "training/checkpoints/qwen3-0.6b-medlearn-lora/final",
        "training_status": "curriculum_ready_not_trained",
        "sampling_policy": sampling_policy,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for stage_name, _ in STAGES:
        stage_dir = args.output_dir / stage_name
        stage_dir.mkdir(parents=True, exist_ok=True)
        write_jsonl(stage_dir / "train.jsonl", stage_rows[stage_name])

    write_jsonl(args.output_dir / "eval.jsonl", eval_rows)
    (args.output_dir / "sampling_policy.json").write_text(
        json.dumps(sampling_policy, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()