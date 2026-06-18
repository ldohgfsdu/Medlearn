"""Convert EV1 evidence-first candidates into isolated knowledge-node rows.

EV1 candidates are review input. This module only converts deterministic
``pass`` candidates into V3-shaped cache rows for downstream contract testing;
it does not make publication or medical-review decisions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from textbook_identity import TextbookIdentity
from textbook_pipeline.ingestion_contract import ADAPTER_VERSION
from textbook_pipeline.knowledge_node_adapter import (
    attach_provenance,
    build_provenance,
    is_valid_node_row,
    production_node_id,
)

EV1_NORMALIZED_PIPELINE_VERSION = "ev1_candidate_to_knowledge_node"


class EvidenceCandidateConversionError(ValueError):
    """Raised when an EV1 candidate cache is not eligible for conversion."""


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _map_candidate_type(item: dict[str, Any]) -> str:
    text = "".join(
        [
            _clean_text(item.get("title")),
            _clean_text(item.get("source_heading")),
            _clean_text(item.get("aspect")),
            _clean_text(item.get("content")),
        ]
    )

    if any(token in text for token in ("治疗", "药", "抗菌", "用药", "手术", "处理")):
        return "treatment"
    if any(token in text for token in ("检查", "诊断", "影像", "实验室", "内镜")):
        return "exam"
    if any(token in text for token in ("病因", "机制", "发病")):
        return "mechanism"
    if any(token in text for token in ("症状", "体征", "表现", "发热", "疼痛")):
        return "symptom"
    return "concept"


def _conversion_summary(
    candidate_items: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    *,
    skipped_artifact_audit: int = 0,
) -> dict[str, int]:
    skipped_needs_review = sum(
        1 for item in candidate_items if item.get("verification_state") == "needs_review"
    )
    skipped_rejected = sum(
        1 for item in candidate_items if item.get("verification_state") == "rejected"
    )
    skipped_other = (
        len(candidate_items)
        - len(rows)
        - skipped_needs_review
        - skipped_rejected
        - skipped_artifact_audit
    )
    return {
        "candidate_items": len(candidate_items),
        "converted": len(rows),
        "skipped_needs_review": skipped_needs_review,
        "skipped_rejected": skipped_rejected,
        "skipped_artifact_audit": skipped_artifact_audit,
        "skipped_other": max(skipped_other, 0),
    }


def candidate_cache_to_knowledge_rows(
    candidate_payload: dict[str, Any],
    identity: TextbookIdentity,
    *,
    source_pdf: str,
    candidate_path: Path | str,
    blocked_artifact_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Convert a ready EV1 candidate cache into isolated knowledge-node rows.

    Only candidates with ``verification_state == "pass"`` are converted. Review
    and rejected candidates stay in the candidate artifact for editorial use.
    """
    candidate_status = _clean_text(candidate_payload.get("candidate_status"))
    if candidate_status != "ready_candidate":
        raise EvidenceCandidateConversionError(
            f"EV1 candidate_status must be ready_candidate, got {candidate_status!r}"
        )

    part_title = _clean_text(candidate_payload.get("part_title"))
    section_title = _clean_text(candidate_payload.get("section_title"))
    if not part_title or not section_title:
        raise EvidenceCandidateConversionError("EV1 candidate cache is missing part/section title")

    candidate_items = candidate_payload.get("candidate_items") or []
    if not isinstance(candidate_items, list):
        raise EvidenceCandidateConversionError("EV1 candidate_items must be a list")

    rows: list[dict[str, Any]] = []
    blocked_artifact_ids = blocked_artifact_ids or set()
    skipped_artifact_audit = 0
    for index, item in enumerate(candidate_items):
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"))
        content = _clean_text(item.get("content"))
        evidence = _clean_text(item.get("evidence"))
        artifact_id = _clean_text(item.get("artifact_id"))
        if artifact_id in blocked_artifact_ids:
            skipped_artifact_audit += 1
            continue
        if item.get("verification_state") != "pass":
            continue
        source_heading = _clean_text(item.get("source_heading")) or _clean_text(item.get("aspect")) or "原文片段"
        if not title or not content or not evidence or not artifact_id:
            continue

        page_start = item.get("page_start") or candidate_payload.get("page_start")
        page_end = item.get("page_end") or candidate_payload.get("page_end")
        row = {
            "id": production_node_id(
                identity.canonical_id,
                part_title,
                section_title,
                title,
                source_anchor=f"{artifact_id}:{item.get('item_index', index)}",
            ),
            "order_num": len(rows),
            "level": 3,
            "type": _map_candidate_type(item),
            "title": title,
            "subject": identity.subject_name,
            "chapter": part_title,
            "sub_chapter": section_title,
            "knowledge_path": [identity.subject_name, part_title, section_title, title],
            "content": content,
            "key_points": [],
            "structured_sections": [
                {
                    "title": source_heading,
                    "content": content,
                }
            ],
            "causal_links": [],
            "related_nodes": [],
            "tags": ["ev1_candidate", "evidence_first"],
            "source": "textbook_pipeline_ev1",
            "book_id": identity.canonical_id,
            "textbook": identity.canonical_id,
            "edition": identity.edition,
            "node_source": "ev1_candidate",
            "inferred": False,
            "standalone": True,
            "version": ADAPTER_VERSION,
            "source_span": {
                "artifact_id": artifact_id,
                "item_index": item.get("item_index", index),
                "source_heading": source_heading,
                "normalized_aspect": item.get("aspect"),
                "evidence": evidence,
                "page_start": page_start,
                "page_end": page_end,
                "verification_state": item.get("verification_state"),
                "verification_notes": item.get("verification_notes") or [],
                "risk_class": item.get("risk_class"),
                "candidate_only": True,
            },
        }
        provenance = build_provenance(
            identity=identity,
            part_title=part_title,
            section_title=section_title,
            source_pdf=source_pdf,
            pipeline_version=EV1_NORMALIZED_PIPELINE_VERSION,
            created_from=str(candidate_path),
            page_start=page_start if isinstance(page_start, int) else None,
            page_end=page_end if isinstance(page_end, int) else None,
            source_anchor=artifact_id,
            content=content,
        )
        attach_provenance(row, provenance)
        if is_valid_node_row(row):
            rows.append(row)

    return rows, _conversion_summary(
        candidate_items,
        rows,
        skipped_artifact_audit=skipped_artifact_audit,
    )
