#!/usr/bin/env python
"""Copy and freeze an SFT dataset directory under a canonical version name."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from expand_sft_candidates_from_chunks import build_frozen_markdown, train_eval_overlap_count  # noqa: E402
from sft_dataset_audit_lib import load_jsonl, utc_now_iso  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
DEFAULT_SOURCE = TRAINING_DIR / "data" / "sft_v2_expanded_120"
DEFAULT_TARGET = TRAINING_DIR / "data" / "sft_v2_expanded_182"

COPY_FILES = (
    "train.jsonl",
    "eval.jsonl",
    "expansion_diff.jsonl",
)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Freeze SFT dataset under a versioned directory")
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--target-dir", type=Path, default=DEFAULT_TARGET)
    parser.add_argument("--version-name", type=str, default="sft_v2_expanded_182")
    parser.add_argument("--previous-version", type=str, default="sft_v2_expanded_104")
    parser.add_argument("--rollback-version", type=str, default="sft_v2_expanded")
    args = parser.parse_args()

    args.target_dir.mkdir(parents=True, exist_ok=True)
    for filename in COPY_FILES:
        source = args.source_dir / filename
        if source.exists():
            shutil.copy2(source, args.target_dir / filename)

    train_rows = load_jsonl(args.target_dir / "train.jsonl")
    eval_rows = load_jsonl(args.target_dir / "eval.jsonl")
    source_manifest: dict[str, Any] = {}
    source_manifest_path = args.source_dir / "manifest.json"
    if source_manifest_path.exists():
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))

    manifest = {
        **source_manifest,
        "version": args.version_name,
        "previous_version": args.previous_version,
        "frozen": True,
        "frozen_at": utc_now_iso(),
        "total_accepted_samples": len(train_rows),
        "golden_eval_samples": len(eval_rows),
        "train_eval_overlap_count": train_eval_overlap_count(train_rows, eval_rows),
        "training_status": "not_started",
        "outputs": {
            "train": str(args.target_dir / "train.jsonl"),
            "eval": str(args.target_dir / "eval.jsonl"),
            "expansion_diff": str(args.target_dir / "expansion_diff.jsonl"),
        },
    }
    (args.target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (args.target_dir / "VERSION").write_text(f"{args.version_name}\n", encoding="utf-8")
    frozen_md = build_frozen_markdown(
        manifest,
        version_name=args.version_name,
        rollback_version=args.rollback_version,
    )
    (args.target_dir / "FROZEN.md").write_text(frozen_md, encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.target_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()