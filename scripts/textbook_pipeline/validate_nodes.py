"""
Validation of nodes + segments against catalog.
Outputs: validation-report.md + validation-report.json
"""
from __future__ import annotations
import json
from pathlib import Path
from textbook_pipeline.atomic_io import atomic_write_json, atomic_write_text

# ── Rules ───────────────────────────────────────────────────────────────

def validate(catalog: dict, segments: list[dict], nodes_payload: dict, max_nodes_per_seg: int = 50) -> dict:
    nodes = nodes_payload.get("nodes", [])
    weak_defs = nodes_payload.get("weakDefinitionCandidates", [])

    errors: list[dict] = []
    warnings: list[dict] = []
    seg_stats: list[dict] = []

    # 1. Catalog missing items
    expected_titles = set()
    for ch in catalog.get("chapters", []):
        for sec in ch.get("sections", []):
            expected_titles.add(sec["title"])

    found_titles = {s["sectionTitle"] for s in segments if s["found"]}
    for title in expected_titles - found_titles:
        errors.append({
            "rule": "catalog-missing",
            "severity": "error",
            "message": f"Catalog item not found in TOC: {title}",
        })

    # 2. Per-segment checks
    node_by_seg: dict[str, list] = {}
    for n in nodes:
        seg_id = n.get("sourceSpan", {}).get("segmentId", "")
        node_by_seg.setdefault(seg_id, []).append(n)

    for seg in segments:
        seg_id = seg["segmentId"]
        seg_nodes = node_by_seg.get(seg_id, [])
        seg_warnings = []

        if not seg["found"]:
            seg_warnings.append("segment not found in TOC")

        if seg["confidence"] < 0.8 and seg["found"]:
            seg_warnings.append(f"low confidence: {seg['confidence']}")

        # Empty segment detection: found in TOC but no text content
        if seg["found"] and not seg.get("text"):
            seg_warnings.append("empty segment (matched in TOC but no text extracted)")

        if len(seg_nodes) > max_nodes_per_seg:
            errors.append({
                "rule": "node-count-exceeded",
                "severity": "error",
                "message": f"Segment '{seg_id}' has {len(seg_nodes)} nodes (max {max_nodes_per_seg})",
            })

        seg_stats.append({
            "segmentId": seg_id,
            "sectionTitle": seg["sectionTitle"],
            "found": seg["found"],
            "confidence": seg["confidence"],
            "pageStart": seg.get("pageStart"),
            "pageEnd": seg.get("pageEnd"),
            "nodeCount": len(seg_nodes),
            "warnings": seg_warnings,
        })

    # 3. Duplicate titles within same segment
    title_counts: dict[str, int] = {}
    for n in nodes:
        key = f"{n.get('chapter', '')}::{n['title']}"
        title_counts[key] = title_counts.get(key, 0) + 1
    for key, count in title_counts.items():
        if count > 3:
            warnings.append({
                "rule": "duplicate-title-high",
                "severity": "warning",
                "message": f"Title '{key}' appears {count} times across segments",
            })

    # 4. Weak definitions
    for wd in weak_defs:
        warnings.append({
            "rule": "weak-definition",
            "severity": "warning",
            "message": f"Weak definition candidate in {wd['segmentId']}: {wd['definition'][:60]}...",
        })

    # 5. Summary
    summary = {
        "totalNodes": len(nodes),
        "totalSegments": len(segments),
        "foundSegments": sum(1 for s in segments if s["found"]),
        "missingSegments": sum(1 for s in segments if not s["found"]),
        "errors": len(errors),
        "warnings": len(warnings),
        "weakDefinitions": len(weak_defs),
    }

    return {
        "summary": summary,
        "segments": seg_stats,
        "errors": errors,
        "warnings": warnings,
        "weakDefinitionCandidates": weak_defs,
    }


def render_markdown(report: dict) -> str:
    lines = ["# Validation Report\n"]
    s = report["summary"]
    lines.append(f"**Nodes:** {s['totalNodes']}  **Segments:** {s['foundSegments']}/{s['totalSegments']} found\n")
    lines.append(f"**Errors:** {s['errors']}  **Warnings:** {s['warnings']}  **Weak defs:** {s['weakDefinitions']}\n")

    if report["errors"]:
        lines.append("\n## Errors\n")
        for e in report["errors"]:
            lines.append(f"- [{e['rule']}] {e['message']}")
    if report["warnings"]:
        lines.append("\n## Warnings\n")
        for w in report["warnings"]:
            lines.append(f"- [{w['rule']}] {w['message']}")

    lines.append("\n## Segment Stats\n")
    lines.append("| Section | Found | Conf | Nodes | Warnings |")
    lines.append("|---------|-------|------|-------|----------|")
    for seg in report["segments"]:
        warn_str = "; ".join(seg["warnings"]) or "-"
        lines.append(f"| {seg['sectionTitle'][:30]} | {'✓' if seg['found'] else '✗'} | {seg['confidence']:.1f} | {seg['nodeCount']} | {warn_str} |")

    return "\n".join(lines)


def run_validate(catalog_path: str, segments_path: str, nodes_path: str, out_dir: str) -> dict:
    try:
        catalog = json.loads(Path(catalog_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid catalog JSON: {catalog_path}: {e}") from e

    try:
        segments = [json.loads(l) for l in Path(segments_path).read_text(encoding="utf-8").splitlines() if l.strip()]
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid segments JSONL: {segments_path}: {e}") from e

    try:
        nodes_payload = json.loads(Path(nodes_path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid nodes JSON: {nodes_path}: {e}") from e

    report = validate(catalog, segments, nodes_payload)

    atomic_write_json(Path(out_dir) / "validation-report.json", report)
    atomic_write_text(Path(out_dir) / "validation-report.md", render_markdown(report))
    return report
