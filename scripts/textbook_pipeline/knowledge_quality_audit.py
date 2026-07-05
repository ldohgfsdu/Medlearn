"""Baseline audit for golden-section knowledge extraction quality defects."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .paragraph_reconstruction import (
    can_stitch_artifacts,
    classify_expanded_content_risk,
    detect_heading_title_mismatch,
    detect_title_body_mismatch,
    find_abnormal_chinese_spaces,
    is_artifact_split_candidate,
    is_extractive_paraphrase,
    is_truncated_sentence,
    load_artifacts_from_evidence_payload,
    repair_truncated_fields,
)
from .evidence_artifact import EvidenceArtifact


@dataclass
class AuditFinding:
    category: str
    section_id: str
    node_id: str | None
    title: str | None
    detail: str
    artifact_id: str | None = None
    page: int | None = None
    source_order: int | None = None
    sample_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "section_id": self.section_id,
            "node_id": self.node_id,
            "title": self.title,
            "detail": self.detail,
            "artifact_id": self.artifact_id,
            "page": self.page,
            "source_order": self.source_order,
            "sample_text": self.sample_text,
        }


@dataclass
class SectionAuditReport:
    section_id: str
    findings: list[AuditFinding] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "section_id": self.section_id,
            "finding_count": len(self.findings),
            "stats": self.stats,
            "findings": [finding.to_dict() for finding in self.findings],
        }


HARDCODED_SECTION_PATCHES: list[dict[str, Any]] = [
    {
        "file": "scripts/textbook_pipeline/evidence_display_contract.py",
        "pattern": r"106\s*<=\s*page\s*<=\s*109",
        "detail": "肺结核 classification bucket uses fixed page range 106-109",
    },
    {
        "file": "scripts/textbook_pipeline/evidence_display_contract.py",
        "pattern": r"156\s*<=\s*order\s*<=\s*229",
        "detail": "肺结核 classification bucket uses fixed source_order range 156-229",
    },
    {
        "file": "scripts/textbook_pipeline/document_tree_builder.py",
        "pattern": r"第四章 支气管哮喘",
        "detail": "document tree golden scope profile references asthma chapter",
    },
    {
        "file": "scripts/textbook_pipeline/document_tree_builder.py",
        "pattern": r"第八章 肺结核",
        "detail": "document tree golden scope profile references tuberculosis chapter",
    },
]


def _walk_display_nodes(node: Any, acc: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if node.get("display") or node.get("evidence_items"):
            acc.append(node)
        for value in node.values():
            _walk_display_nodes(value, acc)
    elif isinstance(node, list):
        for item in node:
            _walk_display_nodes(item, acc)


def _candidate_items(candidate_payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not candidate_payload:
        return []
    items = candidate_payload.get("candidate_items") or []
    return [item for item in items if isinstance(item, dict)]


def _artifact_map(artifacts: list[EvidenceArtifact]) -> dict[str, EvidenceArtifact]:
    return {artifact.id: artifact for artifact in artifacts}


def audit_normalized_nodes(
    *,
    section_id: str,
    normalized_payload: dict[str, Any],
    artifacts: list[EvidenceArtifact],
    candidate_payload: dict[str, Any] | None = None,
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    artifact_by_id = _artifact_map(artifacts)

    for row in normalized_payload.get("nodes") or []:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        content = str(row.get("content") or "").strip()
        node_id = str(row.get("id") or "")
        source = row.get("source_span") or {}
        artifact_id = str(source.get("artifact_id") or "")
        evidence = str(source.get("evidence") or content)
        page = source.get("page_start")
        source_order = source.get("source_order")
        source_heading = str(source.get("source_heading") or "").strip()

        if not content:
            findings.append(
                AuditFinding(
                    category="empty_organized_node",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail="organized node has empty content",
                    artifact_id=artifact_id or None,
                    page=page if isinstance(page, int) else None,
                    source_order=source_order if isinstance(source_order, int) else None,
                )
            )
            continue

        if is_truncated_sentence(content):
            findings.append(
                AuditFinding(
                    category="truncated_sentence",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail="organized content ends mid-sentence",
                    artifact_id=artifact_id or None,
                    page=page if isinstance(page, int) else None,
                    source_order=source_order if isinstance(source_order, int) else None,
                    sample_text=content[:120],
                )
            )

        for position, space in find_abnormal_chinese_spaces(content):
            findings.append(
                AuditFinding(
                    category="abnormal_chinese_space",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail=f"abnormal CJK whitespace at position {position}",
                    artifact_id=artifact_id or None,
                    sample_text=space,
                )
            )

        mismatch = detect_title_body_mismatch(title, content)
        if mismatch:
            findings.append(
                AuditFinding(
                    category="title_body_mismatch",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail=mismatch,
                    artifact_id=artifact_id or None,
                    sample_text=content[:120],
                )
            )

        heading_mismatch = detect_heading_title_mismatch(source_heading, title, content)
        if heading_mismatch:
            findings.append(
                AuditFinding(
                    category="heading_title_mismatch",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail=heading_mismatch,
                    artifact_id=artifact_id or None,
                    sample_text=source_heading,
                )
            )

        if is_extractive_paraphrase(content, evidence):
            findings.append(
                AuditFinding(
                    category="extractive_paraphrase",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail="content drops leading evidence context",
                    artifact_id=artifact_id or None,
                    sample_text=content[:120],
                )
            )

        artifact = artifact_by_id.get(artifact_id)
        if artifact:
            next_order = artifact.source_order + 1
            next_artifact = next(
                (item for item in artifacts if item.source_order == next_order and item.page_start == artifact.page_start),
                None,
            )
            if next_artifact and is_artifact_split_candidate(artifact.raw_text):
                if can_stitch_artifacts(artifact, next_artifact):
                    findings.append(
                        AuditFinding(
                            category="stitchable_adjacent_artifact",
                            section_id=section_id,
                            node_id=node_id,
                            title=title,
                            detail="adjacent artifact can continue truncated content",
                            artifact_id=artifact_id,
                            page=artifact.page_start,
                            source_order=artifact.source_order,
                            sample_text=next_artifact.raw_text[:80],
                        )
                    )

    for item in _candidate_items(candidate_payload):
        if item.get("verification_state") != "pass":
            continue
        title = str(item.get("title") or "").strip()
        content = str(item.get("content") or "").strip()
        evidence = str(item.get("evidence") or "").strip()
        artifact_id = str(item.get("artifact_id") or "")
        artifact = artifact_by_id.get(artifact_id)
        if artifact and is_truncated_sentence(content):
            repair = repair_truncated_fields(
                content=content,
                evidence=evidence,
                artifact=artifact,
                all_artifacts=artifacts,
            )
            if repair:
                findings.append(
                    AuditFinding(
                        category="repairable_truncated_candidate",
                        section_id=section_id,
                        node_id=None,
                        title=title,
                        detail=(
                            "multi-artifact reconstruction possible; requires provenance review"
                            if repair.span.is_multi_artifact
                            else "single-chain reconstruction possible"
                        ),
                        artifact_id=artifact_id,
                        page=item.get("page_start") if isinstance(item.get("page_start"), int) else artifact.page_start,
                        source_order=artifact.source_order,
                        sample_text=repair.raw_text[:120],
                    )
                )

    return findings


def audit_display_contract(
    *,
    section_id: str,
    display_payload: dict[str, Any],
) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    nodes: list[dict[str, Any]] = []
    _walk_display_nodes(display_payload, nodes)

    for node in nodes:
        display = node.get("display") or {}
        title = str(display.get("title") or "").strip()
        body = str(display.get("body") or "").strip()
        publication_state = node.get("publication_state")
        node_id = str(node.get("id") or "")

        if publication_state == "organized" and not body:
            findings.append(
                AuditFinding(
                    category="empty_organized_node",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail="display organized node has empty body",
                )
            )

        if body and is_truncated_sentence(body):
            findings.append(
                AuditFinding(
                    category="truncated_sentence",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail="display body ends mid-sentence",
                    sample_text=body[:120],
                )
            )

        mismatch = detect_title_body_mismatch(title, body)
        if mismatch:
            findings.append(
                AuditFinding(
                    category="title_body_mismatch",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail=mismatch,
                    sample_text=body[:120],
                )
            )

        for position, space in find_abnormal_chinese_spaces(body):
            findings.append(
                AuditFinding(
                    category="abnormal_chinese_space",
                    section_id=section_id,
                    node_id=node_id,
                    title=title,
                    detail=f"abnormal CJK whitespace at position {position}",
                    sample_text=space,
                )
            )

    return findings


def summarize_findings(findings: list[AuditFinding]) -> dict[str, int]:
    stats: dict[str, int] = {}
    for finding in findings:
        stats[finding.category] = stats.get(finding.category, 0) + 1
    return stats


def audit_section_bundle(
    *,
    section_id: str,
    generated_root: Path,
    repo_root: Path | None = None,
) -> SectionAuditReport:
    knowledge_root = generated_root / "knowledge_nodes" / "internal-medicine-10"
    display_root = generated_root / "display_contracts" / "internal-medicine-10"
    candidate_root = generated_root / "evidence_candidates" / "internal-medicine-10"

    normalized_path = knowledge_root / f"{section_id}.normalized.json"
    evidence_path = knowledge_root / f"{section_id}.evidence.json"
    display_path = display_root / f"{section_id}.display_contract.json"
    candidate_path = candidate_root / f"{section_id}.candidate.json"

    normalized_payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    evidence_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    display_payload = json.loads(display_path.read_text(encoding="utf-8"))
    candidate_payload = (
        json.loads(candidate_path.read_text(encoding="utf-8")) if candidate_path.exists() else None
    )
    artifacts = load_artifacts_from_evidence_payload(evidence_payload)

    findings = [
        *audit_normalized_nodes(
            section_id=section_id,
            normalized_payload=normalized_payload,
            artifacts=artifacts,
            candidate_payload=candidate_payload,
        ),
        *audit_display_contract(section_id=section_id, display_payload=display_payload),
    ]

    if repo_root:
        for patch in HARDCODED_SECTION_PATCHES:
            file_path = repo_root / patch["file"]
            if not file_path.exists():
                continue
            text = file_path.read_text(encoding="utf-8")
            if re.search(patch["pattern"], text):
                findings.append(
                    AuditFinding(
                        category="hardcoded_section_patch",
                        section_id=section_id,
                        node_id=None,
                        title=None,
                        detail=f"{patch['file']}: {patch['detail']}",
                    )
                )

    return SectionAuditReport(
        section_id=section_id,
        findings=findings,
        stats=summarize_findings(findings),
    )


def dry_run_repair_candidate_items(
    candidate_payload: dict[str, Any],
    artifacts: list[EvidenceArtifact],
) -> tuple[dict[str, Any], dict[str, int]]:
    payload = json.loads(json.dumps(candidate_payload))
    stats = {
        "truncated_before": 0,
        "truncated_after": 0,
        "reconstructed_items": 0,
        "multi_artifact_reconstructions": 0,
        "downgraded_to_evidence_only": 0,
        "downgraded_paraphrase": 0,
        "downgraded_title_mismatch": 0,
    }
    artifact_by_id = _artifact_map(artifacts)

    for item in payload.get("candidate_items") or []:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "")
        evidence = str(item.get("evidence") or "")
        title = str(item.get("title") or "")
        artifact = artifact_by_id.get(str(item.get("artifact_id") or ""))

        if is_truncated_sentence(content):
            stats["truncated_before"] += 1

        if artifact:
            repair = repair_truncated_fields(
                content=content,
                evidence=evidence,
                artifact=artifact,
                all_artifacts=artifacts,
            )
            if repair:
                item["evidence"] = repair.raw_text
                item["content"] = repair.display_text
                item["source_artifact_ids"] = list(repair.span.artifact_ids)
                item["reconstructed_locators"] = [dict(locator) for locator in repair.span.locators]
                notes = list(item.get("verification_notes") or [])
                notes.extend(
                    [
                        repair.note,
                        "dry_run: reconstruction stored for review only; not publication-approved",
                    ]
                )
                item["verification_notes"] = list(dict.fromkeys(notes))
                item["verification_state"] = "needs_review"
                stats["reconstructed_items"] += 1
                if repair.span.is_multi_artifact:
                    stats["multi_artifact_reconstructions"] += 1
                expanded_risk = classify_expanded_content_risk(
                    str(item.get("content") or ""),
                    str(item.get("evidence") or ""),
                )
                if expanded_risk:
                    item["risk_class"] = "needs_review"
                    notes = list(item.get("verification_notes") or [])
                    notes.append(f"expanded_content_risk: {expanded_risk}")
                    item["verification_notes"] = list(dict.fromkeys(notes))

        if is_extractive_paraphrase(str(item.get("content") or ""), str(item.get("evidence") or "")):
            item["verification_state"] = "needs_review"
            notes = list(item.get("verification_notes") or [])
            notes.append("extractive_paraphrase: content drops leading evidence context")
            item["verification_notes"] = list(dict.fromkeys(notes))
            stats["downgraded_paraphrase"] += 1

        mismatch = detect_title_body_mismatch(title, str(item.get("content") or ""))
        if mismatch:
            item["verification_state"] = "needs_review"
            notes = list(item.get("verification_notes") or [])
            notes.append(f"title_body_mismatch: {mismatch}")
            item["verification_notes"] = list(dict.fromkeys(notes))
            stats["downgraded_title_mismatch"] += 1

        if is_truncated_sentence(str(item.get("content") or "")):
            stats["truncated_after"] += 1
            unresolved_risk = classify_expanded_content_risk(
                str(item.get("content") or ""),
                str(item.get("evidence") or ""),
            )
            if unresolved_risk:
                item["verification_state"] = "needs_review"
                item["risk_class"] = "needs_review"
                notes = list(item.get("verification_notes") or [])
                notes.append(f"expanded_content_risk: {unresolved_risk}")
                notes.append("truncated_sentence: unresolved with procedural risk; downgrade to needs_review")
                item["verification_notes"] = list(dict.fromkeys(notes))
            elif item.get("verification_state") == "pass":
                item["verification_state"] = "evidence_only"
                notes = list(item.get("verification_notes") or [])
                notes.append("truncated_sentence: unresolved; downgrade to evidence_only")
                item["verification_notes"] = list(dict.fromkeys(notes))
                stats["downgraded_to_evidence_only"] += 1

    return payload, stats