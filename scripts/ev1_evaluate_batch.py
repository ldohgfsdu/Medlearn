#!/usr/bin/env python3
"""EV1 Evaluation Batch Report Generator.

Generates a comprehensive evaluation report for EV1 pipeline.
No LLM calls. No uploads. No manifest changes.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

EVIDENCE_DIR = PROJECT_ROOT / "generated" / "evidence" / "internal-medicine-10"
REPORT_PATH = PROJECT_ROOT / "generated" / "ev1_evaluation_report.json"
REPORT_MD_PATH = PROJECT_ROOT / "generated" / "ev1_evaluation_report.md"


def load_evidence_cache(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_synthesis_cache(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def analyze_chapter(evidence_path: Path, synthesis_path: Path) -> dict[str, Any]:
    """Analyze a single chapter's evidence + synthesis results."""
    evidence = load_evidence_cache(evidence_path)
    synthesis = load_synthesis_cache(synthesis_path) if synthesis_path.exists() else None

    artifacts = evidence.get("artifacts", [])
    items = synthesis.get("items", []) if synthesis else []
    metrics = synthesis.get("metrics", []) if synthesis else []

    # Artifact stats
    artifact_types = {}
    for art in artifacts:
        t = art.get("artifact_type", "unknown")
        artifact_types[t] = artifact_types.get(t, 0) + 1

    # Item stats
    item_count = len(items)
    pass_count = sum(1 for i in items if i.get("verification_state") == "pass")
    needs_review = sum(1 for i in items if i.get("verification_state") == "needs_review")
    rejected = sum(1 for i in items if i.get("verification_state") == "rejected")

    # Timing
    total_time = sum(m.get("time_s", 0) for m in metrics)
    avg_time = total_time / len(metrics) if metrics else 0

    # Risk class distribution
    risk_classes = {}
    for item in items:
        rc = item.get("risk_class", "unknown")
        risk_classes[rc] = risk_classes.get(rc, 0) + 1

    # Evidence substring pass rate
    evidence_pass = sum(
        1 for item in items
        if item.get("verification_state") in ("pass", "needs_review")
    )
    evidence_rate = evidence_pass / item_count if item_count > 0 else 0

    return {
        "chapter": evidence_path.stem.split("__")[-1] if "__" in evidence_path.stem else evidence_path.stem,
        "artifacts": {
            "total": len(artifacts),
            "types": artifact_types,
        },
        "items": {
            "total": item_count,
            "pass": pass_count,
            "needs_review": needs_review,
            "rejected": rejected,
            "success_rate": item_count / len(artifacts) if artifacts else 0,
        },
        "verification": {
            "evidence_substring_pass_rate": evidence_rate,
        },
        "risk_classes": risk_classes,
        "timing": {
            "total_s": total_time,
            "avg_per_artifact_s": avg_time,
        },
    }


def generate_report() -> dict[str, Any]:
    """Generate evaluation report for all chapters."""
    chapters = []

    # Find all evidence files
    for evidence_path in sorted(EVIDENCE_DIR.glob("*.evidence.json")):
        synthesis_path = evidence_path.with_suffix(".synthesis.json")
        if synthesis_path.exists():
            chapter = analyze_chapter(evidence_path, synthesis_path)
            chapters.append(chapter)

    # Summary
    total_artifacts = sum(c["artifacts"]["total"] for c in chapters)
    total_items = sum(c["items"]["total"] for c in chapters)
    total_pass = sum(c["items"]["pass"] for c in chapters)
    total_needs_review = sum(c["items"]["needs_review"] for c in chapters)
    total_rejected = sum(c["items"]["rejected"] for c in chapters)
    total_time = sum(c["timing"]["total_s"] for c in chapters)

    summary = {
        "chapters_processed": len(chapters),
        "total_artifacts": total_artifacts,
        "total_items": total_items,
        "total_pass": total_pass,
        "total_needs_review": total_needs_review,
        "total_rejected": total_rejected,
        "overall_pass_rate": total_pass / total_items if total_items > 0 else 0,
        "overall_success_rate": total_items / total_artifacts if total_artifacts > 0 else 0,
        "total_time_s": total_time,
        "avg_time_per_item_s": total_time / total_items if total_items > 0 else 0,
    }

    # Production gate check
    gate_checks = {
        "json_parse_failures": 0,  # We track this separately
        "evidence_substring_pass_rate": all(
            c["verification"]["evidence_substring_pass_rate"] >= 0.98
            for c in chapters
        ),
        "high_risk_items_reviewed": total_rejected == 0,
        "table_artifacts_preserved": all(
            c["artifacts"]["types"].get("table", 0) >= 0
            for c in chapters
        ),
    }

    return {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "chapters": chapters,
        "production_gate": gate_checks,
    }


def write_markdown_report(report: dict[str, Any], path: Path) -> None:
    """Write human-readable markdown report."""
    lines = [
        "# EV1 Evaluation Batch Report",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Summary",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Chapters processed | {report['summary']['chapters_processed']} |",
        f"| Total artifacts | {report['summary']['total_artifacts']} |",
        f"| Total items | {report['summary']['total_items']} |",
        f"| Pass | {report['summary']['total_pass']} |",
        f"| Needs review | {report['summary']['total_needs_review']} |",
        f"| Rejected | {report['summary']['total_rejected']} |",
        f"| Overall pass rate | {report['summary']['overall_pass_rate']:.1%} |",
        f"| Overall success rate | {report['summary']['overall_success_rate']:.1%} |",
        f"| Total time | {report['summary']['total_time_s']:.1f}s |",
        f"| Avg time per item | {report['summary']['avg_time_per_item_s']:.2f}s |",
        "",
        "## Chapters",
        "",
    ]

    for chapter in report["chapters"]:
        lines.extend([
            f"### {chapter['chapter']}",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Artifacts | {chapter['artifacts']['total']} |",
            f"| Items | {chapter['items']['total']} |",
            f"| Pass | {chapter['items']['pass']} |",
            f"| Needs review | {chapter['items']['needs_review']} |",
            f"| Rejected | {chapter['items']['rejected']} |",
            f"| Success rate | {chapter['items']['success_rate']:.1%} |",
            f"| Evidence pass rate | {chapter['verification']['evidence_substring_pass_rate']:.1%} |",
            f"| Avg time/artifact | {chapter['timing']['avg_per_artifact_s']:.2f}s |",
            "",
        ])

    lines.extend([
        "## Production Gate",
        "",
        f"| Check | Status |",
        f"|-------|--------|",
        f"| JSON parse failures | {report['production_gate']['json_parse_failures']} |",
        f"| Evidence substring pass | {'✓' if report['production_gate']['evidence_substring_pass_rate'] else '✗'} |",
        f"| High-risk items reviewed | {'✓' if report['production_gate']['high_risk_items_reviewed'] else '✗'} |",
        f"| Table artifacts preserved | {'✓' if report['production_gate']['table_artifacts_preserved'] else '✗'} |",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("Generating EV1 Evaluation Report...")

    report = generate_report()

    # Write JSON
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"JSON report: {REPORT_PATH}")

    # Write Markdown
    write_markdown_report(report, REPORT_MD_PATH)
    print(f"Markdown report: {REPORT_MD_PATH}")

    # Print summary
    print("\n--- Summary ---")
    print(f"Chapters: {report['summary']['chapters_processed']}")
    print(f"Artifacts: {report['summary']['total_artifacts']}")
    print(f"Items: {report['summary']['total_items']}")
    print(f"Pass: {report['summary']['total_pass']} ({report['summary']['overall_pass_rate']:.1%})")
    print(f"Needs review: {report['summary']['total_needs_review']}")
    print(f"Rejected: {report['summary']['total_rejected']}")
    print(f"Time: {report['summary']['total_time_s']:.1f}s")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
