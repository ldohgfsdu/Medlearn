#!/usr/bin/env python
"""Audit Tier A dataset distribution without deleting samples."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
TRAINING_DIR = Path(__file__).resolve().parents[1] / "training"
sys.path.insert(0, str(TRAINING_DIR))

from sft_dataset_audit_lib import load_jsonl, utc_now_iso  # noqa: E402
from sft_eval_metrics import extract_prompt_and_expected, extract_source_text  # noqa: E402
from textbook_pipeline.node_guardrails import canonicalize_aspect_label  # noqa: E402

DEFAULT_TRAIN = TRAINING_DIR / "data" / "sft_v2_expanded_182" / "train.jsonl"
DEFAULT_JSON_OUT = TRAINING_DIR / "reports" / "sft_v2_expanded_182_distribution.json"
DEFAULT_MD_OUT = TRAINING_DIR / "reports" / "sft_v2_expanded_182_distribution.md"

HYDRATED_METHOD_MARKERS = (
    "source_segmentation_hydrated",
    "node_repair_hydrated_source",
    "node_repair_hydrated",
)


def is_hydrated(method: str) -> bool:
    normalized = (method or "").strip().lower()
    return any(marker in normalized for marker in HYDRATED_METHOD_MARKERS)


def bucket_nodes(count: int) -> str:
    if count <= 3:
        return "3"
    if count == 4:
        return "4"
    if count == 5:
        return "5"
    if count == 6:
        return "6"
    return "7+"


def bucket_source_length(length: int) -> str:
    if length < 200:
        return "0-199"
    if length < 500:
        return "200-499"
    if length < 1000:
        return "500-999"
    if length < 2000:
        return "1000-1999"
    return "2000+"


def top_share(counter: Counter[str], total: int) -> tuple[str, float]:
    if not counter or total <= 0:
        return "", 0.0
    label, count = counter.most_common(1)[0]
    return label, round(count / total, 4)


def build_skew_flags(report: dict[str, Any]) -> list[dict[str, Any]]:
    total = report["total_samples"]
    flags: list[dict[str, Any]] = []

    hydrated_pct = report["hydrated_vs_non_hydrated"]["hydrated_pct"]
    if hydrated_pct > 0.6:
        flags.append(
            {
                "flag": "hydrated_over_60pct",
                "value": hydrated_pct,
                "sampler_action": "cap_hydrated_per_batch_or_balance_with_non_hydrated",
            }
        )

    chapter_top, chapter_share = top_share(
        Counter(report["by_chapter_path"]),
        total,
    )
    if chapter_share > 0.3:
        flags.append(
            {
                "flag": "single_chapter_over_30pct",
                "chapter_path": chapter_top,
                "value": chapter_share,
                "sampler_action": "chapter_balanced_batch_sampler",
            }
        )

    parent_top, parent_share = top_share(
        Counter(report["by_parent_entity"]),
        total,
    )
    if parent_share > 0.1:
        flags.append(
            {
                "flag": "single_parent_entity_over_10pct",
                "parent_entity": parent_top,
                "value": parent_share,
                "sampler_action": "max_per_parent_entity_cap",
            }
        )

    aspect_top, aspect_share = top_share(Counter(report["by_aspect"]), report["aspect_observations"])
    if aspect_share > 0.2:
        flags.append(
            {
                "flag": "single_aspect_over_20pct",
                "aspect": aspect_top,
                "value": aspect_share,
                "sampler_action": "aspect_balanced_sampling",
            }
        )

    return flags


def audit_distribution(train_rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_generation_method: Counter[str] = Counter()
    by_chapter: Counter[str] = Counter()
    by_parent: Counter[str] = Counter()
    by_aspect: Counter[str] = Counter()
    nodes_hist: Counter[str] = Counter()
    source_len_hist: Counter[str] = Counter()
    hydrated = 0
    non_hydrated = 0

    for row in train_rows:
        method = str(row.get("generation_method") or "unknown")
        by_generation_method[method] += 1
        if is_hydrated(method):
            hydrated += 1
        else:
            non_hydrated += 1

        chapter = str(row.get("chapter_path") or "").strip()
        if not chapter:
            chapter = "unknown"
        by_chapter[chapter] += 1

        _, expected = extract_prompt_and_expected(row)
        nodes = list((expected or {}).get("nodes") or [])
        nodes_hist[bucket_nodes(len(nodes))] += 1

        source_text = extract_source_text(str(row.get("text") or ""))
        source_len_hist[bucket_source_length(len(source_text))] += 1

        for node in nodes:
            parent = str(node.get("parent_entity") or "").strip() or "unknown"
            by_parent[parent] += 1
            aspect = canonicalize_aspect_label(str(node.get("aspect") or "").strip()) or "unknown"
            by_aspect[aspect] += 1

    total = len(train_rows)
    aspect_observations = sum(by_aspect.values())
    report = {
        "dataset_version": "sft_v2_expanded_182",
        "generated_at": utc_now_iso(),
        "total_samples": total,
        "by_generation_method": dict(by_generation_method),
        "hydrated_vs_non_hydrated": {
            "hydrated": hydrated,
            "non_hydrated": non_hydrated,
            "hydrated_pct": round(hydrated / max(total, 1), 4),
            "non_hydrated_pct": round(non_hydrated / max(total, 1), 4),
        },
        "by_chapter_path": dict(by_chapter),
        "by_parent_entity": dict(by_parent),
        "by_aspect": dict(by_aspect),
        "aspect_observations": aspect_observations,
        "nodes_per_sample_histogram": dict(nodes_hist),
        "source_text_length_histogram": dict(source_len_hist),
    }
    report["skew_flags"] = build_skew_flags(report)
    report["sampler_recommendations"] = [
        flag["sampler_action"] for flag in report["skew_flags"]
    ] or ["uniform_shuffle_ok"]
    return report


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SFT v2 expanded 182 distribution audit",
        "",
        f"- dataset_version: `{report['dataset_version']}`",
        f"- generated_at: {report['generated_at']}",
        f"- total_samples: {report['total_samples']}",
        "",
        "## Hydrated vs non-hydrated",
        "",
        f"- hydrated: {report['hydrated_vs_non_hydrated']['hydrated']} "
        f"({report['hydrated_vs_non_hydrated']['hydrated_pct'] * 100:.1f}%)",
        f"- non_hydrated: {report['hydrated_vs_non_hydrated']['non_hydrated']} "
        f"({report['hydrated_vs_non_hydrated']['non_hydrated_pct'] * 100:.1f}%)",
        "",
        "## Generation method",
        "",
    ]
    for method, count in sorted(
        report["by_generation_method"].items(),
        key=lambda item: (-item[1], item[0]),
    ):
        lines.append(f"- {method}: {count}")

    lines.extend(["", "## Nodes per sample", ""])
    for bucket, count in sorted(report["nodes_per_sample_histogram"].items()):
        lines.append(f"- {bucket}: {count}")

    lines.extend(["", "## Source text length", ""])
    for bucket, count in sorted(report["source_text_length_histogram"].items()):
        lines.append(f"- {bucket}: {count}")

    lines.extend(["", "## Skew flags", ""])
    if report["skew_flags"]:
        for flag in report["skew_flags"]:
            lines.append(f"- `{flag['flag']}` → {flag['sampler_action']}")
    else:
        lines.append("- none")

    lines.extend(["", "## Top chapters", ""])
    for chapter, count in Counter(report["by_chapter_path"]).most_common(10):
        lines.append(f"- {chapter}: {count}")

    lines.extend(["", "## Top parent entities", ""])
    for parent, count in Counter(report["by_parent_entity"]).most_common(10):
        lines.append(f"- {parent}: {count}")

    lines.extend(["", "## Top aspects", ""])
    for aspect, count in Counter(report["by_aspect"]).most_common(12):
        lines.append(f"- {aspect}: {count}")

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="Audit SFT dataset distribution")
    parser.add_argument("--train", type=Path, default=DEFAULT_TRAIN)
    parser.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    parser.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT)
    args = parser.parse_args()

    train_rows = load_jsonl(args.train)
    report = audit_distribution(train_rows)
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    args.md_out.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\nWrote {args.json_out}")
    print(f"Wrote {args.md_out}")


if __name__ == "__main__":
    main()