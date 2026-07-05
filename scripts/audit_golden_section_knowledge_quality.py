#!/usr/bin/env python3
"""Dry-run baseline and repair comparison for golden-section knowledge quality."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.knowledge_quality_audit import (  # noqa: E402
    audit_section_bundle,
    dry_run_repair_candidate_items,
    load_artifacts_from_evidence_payload,
)
from textbook_pipeline.paragraph_reconstruction import is_truncated_sentence  # noqa: E402


GOLDEN_SECTIONS = (
    "第二篇_呼吸系统疾病__第四章_支气管哮喘",
    "第二篇_呼吸系统疾病__第八章_肺结核",
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolve_candidate_path(generated_root: Path, section_id: str) -> Path:
    candidates = [
        generated_root / "pipeline_v3" / "evidence_candidates" / "internal-medicine-10" / f"{section_id}.candidate.json",
        generated_root / "evidence_candidates" / "internal-medicine-10" / f"{section_id}.candidate.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f"EV1 candidate cache not found for section: {section_id}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--generated-root",
        default=str(ROOT / "generated"),
        help="Generated artifacts root (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default=str(ROOT / "generated" / "golden_section_knowledge_quality_report.json"),
        help="Write JSON report to this path",
    )
    parser.add_argument(
        "--section-id",
        action="append",
        dest="section_ids",
        help="Limit to one or more section ids (default: asthma + tuberculosis)",
    )
    args = parser.parse_args(argv)

    generated_root = Path(args.generated_root)
    section_ids = tuple(args.section_ids or GOLDEN_SECTIONS)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sections": [],
        "summary": {},
    }

    aggregate_before: dict[str, int] = {}
    aggregate_after: dict[str, int] = {}

    for section_id in section_ids:
        baseline = audit_section_bundle(
            section_id=section_id,
            generated_root=generated_root,
            repo_root=ROOT,
        )
        candidate_path = _resolve_candidate_path(generated_root, section_id)
        evidence_path = (
            generated_root
            / "knowledge_nodes"
            / "internal-medicine-10"
            / f"{section_id}.evidence.json"
        )
        candidate_payload = _load_json(candidate_path)
        evidence_payload = _load_json(evidence_path)
        artifacts = load_artifacts_from_evidence_payload(evidence_payload)
        repaired_payload, repair_stats = dry_run_repair_candidate_items(
            candidate_payload,
            artifacts,
        )

        after_findings = []
        for item in repaired_payload.get("candidate_items") or []:
            content = str(item.get("content") or "")
            if item.get("verification_state") == "pass" and content.endswith("。"):
                continue
        after_stats = dict(repair_stats)
        after_stats["remaining_truncated_pass"] = sum(
            1
            for item in repaired_payload.get("candidate_items") or []
            if item.get("verification_state") == "pass"
            and is_truncated_sentence(str(item.get("content") or ""))
        )
        after_stats["needs_review_total"] = sum(
            1
            for item in repaired_payload.get("candidate_items") or []
            if item.get("verification_state") == "needs_review"
        )

        section_report = {
            "section_id": section_id,
            "baseline": baseline.to_dict(),
            "dry_run_repair": after_stats,
        }
        report["sections"].append(section_report)

        for key, value in baseline.stats.items():
            aggregate_before[key] = aggregate_before.get(key, 0) + value
        aggregate_after["reconstructed_items"] = aggregate_after.get(
            "reconstructed_items", 0
        ) + after_stats.get("reconstructed_items", 0)
        aggregate_after["multi_artifact_reconstructions"] = aggregate_after.get(
            "multi_artifact_reconstructions", 0
        ) + after_stats.get("multi_artifact_reconstructions", 0)
        aggregate_after["downgraded_to_evidence_only"] = aggregate_after.get(
            "downgraded_to_evidence_only", 0
        ) + after_stats.get("downgraded_to_evidence_only", 0)
        aggregate_after["downgraded_paraphrase"] = aggregate_after.get(
            "downgraded_paraphrase", 0
        ) + after_stats.get("downgraded_paraphrase", 0)
        aggregate_after["downgraded_title_mismatch"] = aggregate_after.get(
            "downgraded_title_mismatch", 0
        ) + after_stats.get("downgraded_title_mismatch", 0)
        aggregate_after["remaining_truncated_pass"] = aggregate_after.get(
            "remaining_truncated_pass", 0
        ) + after_stats.get("remaining_truncated_pass", 0)

    report["summary"] = {
        "baseline_stats": aggregate_before,
        "dry_run_repair_stats": aggregate_after,
    }

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[golden-section-quality] sections={len(section_ids)}")
    print(f"[golden-section-quality] baseline_stats={json.dumps(aggregate_before, ensure_ascii=False)}")
    print(f"[golden-section-quality] dry_run_repair_stats={json.dumps(aggregate_after, ensure_ascii=False)}")
    print(f"[golden-section-quality] report={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())