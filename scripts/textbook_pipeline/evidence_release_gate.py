"""Release-gate checks for EV1 normalized caches."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from textbook_identity import TextbookIdentity
from textbook_pipeline.evidence_to_knowledge import EV1_NORMALIZED_PIPELINE_VERSION
from textbook_pipeline.knowledge_node_adapter import production_node_id


@dataclass
class Ev1GateResult:
    path: str
    section: str
    node_count: int = 0
    passed: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "section": self.section,
            "node_count": self.node_count,
            "passed": self.passed,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def validate_ev1_normalized_payload(
    payload: dict[str, Any],
    *,
    path: Path,
    identity: TextbookIdentity,
    blocked_artifact_ids: set[str] | None = None,
) -> Ev1GateResult:
    part_title = str(payload.get("part_title") or "").strip()
    section_title = str(payload.get("section_title") or "").strip()
    result = Ev1GateResult(
        path=str(path),
        section=f"{part_title}/{section_title}",
    )

    nodes = payload.get("nodes") or []
    if not isinstance(nodes, list):
        result.errors.append("nodes must be a list")
        nodes = []
    result.node_count = len(nodes)

    if payload.get("pipeline_version") != EV1_NORMALIZED_PIPELINE_VERSION:
        result.errors.append("pipeline_version is not ev1_candidate_to_knowledge_node")
    if payload.get("node_count") != len(nodes):
        result.errors.append("node_count does not match nodes length")
    if payload.get("textbook_id") != identity.canonical_id:
        result.errors.append("textbook_id mismatch")
    if not part_title or not section_title:
        result.errors.append("missing part_title or section_title")
    if not nodes:
        result.errors.append("zero nodes")

    seen_ids: set[str] = set()
    blocked_artifact_ids = blocked_artifact_ids or set()
    for index, row in enumerate(nodes):
        if not isinstance(row, dict):
            result.errors.append(f"node[{index}] is not an object")
            continue
        row_id = str(row.get("id") or "")
        title = str(row.get("title") or "").strip()
        source_span = row.get("source_span") or {}
        if row_id in seen_ids:
            result.errors.append(f"duplicate id: {row_id}")
        seen_ids.add(row_id)
        if not row_id.startswith("kn-"):
            result.errors.append(f"node[{index}] id is not production-shaped")
        artifact_id = str(source_span.get("artifact_id") or "").strip()
        if artifact_id in blocked_artifact_ids:
            result.errors.append(
                f"node[{index}] artifact is blocked by EV1 artifact audit"
            )
        item_index = source_span.get("item_index", index)
        expected_id = production_node_id(
            identity.canonical_id,
            part_title,
            section_title,
            title,
            source_anchor=f"{artifact_id}:{item_index}",
        )
        if title and artifact_id and row_id != expected_id:
            result.errors.append(f"node[{index}] id is not stable for artifact anchor")
        if row.get("node_source") != "ev1_candidate":
            result.errors.append(f"node[{index}] node_source is not ev1_candidate")
        if row.get("source") != "textbook_pipeline_ev1":
            result.errors.append(f"node[{index}] source is not textbook_pipeline_ev1")
        if source_span.get("candidate_only") is not True:
            result.errors.append(f"node[{index}] candidate_only must be true")
        if source_span.get("verification_state") != "pass":
            result.errors.append(f"node[{index}] verification_state is not pass")
        if not str(source_span.get("evidence") or "").strip():
            result.errors.append(f"node[{index}] missing evidence")
        if not str(source_span.get("source_heading") or "").strip():
            result.errors.append(f"node[{index}] missing source_heading")
        if not isinstance(source_span.get("page_start"), int):
            result.errors.append(f"node[{index}] page_start is not int")
        if not isinstance(source_span.get("page_end"), int):
            result.errors.append(f"node[{index}] page_end is not int")
        provenance = source_span.get("provenance") or {}
        if provenance.get("textbook_id") != identity.canonical_id:
            result.errors.append(f"node[{index}] provenance textbook_id mismatch")
        if provenance.get("source_anchor") != artifact_id:
            result.errors.append(f"node[{index}] provenance source_anchor mismatch")
        sections = row.get("structured_sections") or []
        if not sections:
            result.errors.append(f"node[{index}] missing structured_sections")
        elif sections[0].get("title") != source_span.get("source_heading"):
            result.errors.append(f"node[{index}] structured section does not preserve source_heading")

    summary = payload.get("conversion_summary") or {}
    if summary:
        converted = summary.get("converted")
        if converted != len(nodes):
            result.errors.append("conversion_summary.converted does not match nodes length")
        if int(summary.get("skipped_needs_review") or 0) > 0:
            result.warnings.append(
                "needs_review organized conclusions were skipped; original source evidence can be displayed evidence-only after source QA"
            )
        if int(summary.get("skipped_rejected") or 0) > 0:
            result.warnings.append("rejected candidates were skipped")

    result.passed = not result.errors
    return result


def summarize_gate_results(results: list[Ev1GateResult]) -> dict[str, Any]:
    total_nodes = sum(result.node_count for result in results)
    failed = [result for result in results if not result.passed]
    return {
        "sections": len(results),
        "passed_sections": len(results) - len(failed),
        "failed_sections": len(failed),
        "total_nodes": total_nodes,
        "passed": len(failed) == 0 and bool(results),
    }
