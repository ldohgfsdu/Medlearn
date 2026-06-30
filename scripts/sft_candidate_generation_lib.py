"""Generate SFT candidate rows from pipeline chunks with existing quality gates."""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
TRAINING_DIR = SCRIPTS_DIR.parent / "training"
for path in (SCRIPTS_DIR, TRAINING_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_sft_dataset import (  # noqa: E402
    build_user_prompt,
    clean_source_text,
    compact_json,
    format_chat_text,
)
from sft_eval_metrics import extract_source_text  # noqa: E402
from sft_repair_lib import (  # noqa: E402
    dedupe_nodes,
    extract_parent_entity_from_chapter,
    repair_payload,
    r3_split_by_source_segmentation,
    segment_source_text,
)
from textbook_pipeline.node_guardrails import canonicalize_aspect_label  # noqa: E402

MIN_SOURCE_CHARS = 80
MIN_SEGMENT_COUNT = 3
MIN_UNIQUE_ASPECTS = 3
TABLE_DENSITY_MAX = 0.18


def build_chapter_path(headings: list[str]) -> str:
    return " > ".join(part.strip() for part in headings if str(part).strip()) or "未识别"


def make_sample_id(source_file: str, chunk_id: str) -> str:
    return f"{source_file.replace('/', chr(92))}::{chunk_id}"


def table_density(source_text: str) -> float:
    text = source_text.strip()
    if not text:
        return 0.0
    return text.count("|") / max(len(text), 1)


def count_segment_aspects(source_text: str) -> dict[str, Any]:
    aspects: set[str] = set()
    segments = segment_source_text(source_text)
    for segment in segments:
        aspect = segment.get("aspect")
        if aspect and aspect != "unknown":
            aspects.add(canonicalize_aspect_label(aspect))
    return {
        "segment_count": len(segments),
        "unique_aspects": sorted(aspects),
        "unique_aspect_count": len(aspects),
    }


def source_suitability(source_text: str) -> dict[str, Any]:
    stats = count_segment_aspects(source_text)
    density = table_density(source_text)
    has_enough_segments = stats["segment_count"] >= MIN_SEGMENT_COUNT
    has_enough_aspects = stats["unique_aspect_count"] >= MIN_UNIQUE_ASPECTS
    source_long_enough = len(source_text) >= MIN_SOURCE_CHARS or (
        has_enough_segments and has_enough_aspects
    )
    return {
        **stats,
        "source_length": len(source_text),
        "table_density": round(density, 4),
        "has_enough_segments": has_enough_segments,
        "has_enough_aspects": has_enough_aspects,
        "source_long_enough": source_long_enough,
        "table_heavy": density > TABLE_DENSITY_MAX,
    }


def hydrate_chunk_source_text(sample: dict[str, Any]) -> tuple[str, str | None]:
    source_text = clean_source_text(str(sample.get("content") or ""))
    if source_text:
        return source_text, None

    evidences: list[str] = []
    seen: set[str] = set()
    for node in sample.get("nodes") or []:
        evidence = str(node.get("evidence") or "").strip()
        if not evidence or evidence in seen:
            continue
        seen.add(evidence)
        evidences.append(evidence)
    if not evidences:
        return "", None
    return "\n".join(evidences), "node_evidence_hydration"


def generate_candidate_payload(
    sample: dict[str, Any],
    *,
    min_nodes: int = MIN_UNIQUE_ASPECTS,
    allow_source_hydration: bool = True,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    source_text, hydration_method = (
        hydrate_chunk_source_text(sample)
        if allow_source_hydration
        else (clean_source_text(str(sample.get("content") or "")), None)
    )
    chapter_path = build_chapter_path(list(sample.get("headings") or []))
    suitability = source_suitability(source_text)
    meta = {
        "chapter_path": chapter_path,
        "parent_entity": extract_parent_entity_from_chapter(chapter_path),
        "suitability": suitability,
        "source_recovery_method": hydration_method,
    }

    if not suitability["source_long_enough"]:
        meta["reject_reason"] = "source_too_short"
        return None, meta
    if suitability["table_heavy"] and not suitability["has_enough_aspects"]:
        meta["reject_reason"] = "table_heavy_low_aspect_signal"
        return None, meta
    if not suitability["has_enough_aspects"]:
        meta["reject_reason"] = "insufficient_aspect_signal"
        return None, meta

    payload, actions = r3_split_by_source_segmentation(
        {"nodes": [], "edges": [], "optional_edges": list(sample.get("edges") or [])},
        source_text=source_text,
        chapter_path=chapter_path,
        min_nodes=min_nodes,
    )
    nodes = dedupe_nodes(payload.get("nodes") or [])
    payload["nodes"] = nodes
    payload["edges"] = []
    meta["generation_actions"] = actions

    aspect_keys = {
        canonicalize_aspect_label(str(node.get("aspect") or "").strip()) for node in nodes
    }
    aspect_keys.discard("unknown")
    if len(nodes) < min_nodes or len(aspect_keys) < MIN_UNIQUE_ASPECTS:
        if hydration_method and sample.get("nodes"):
            repaired, repair_actions = repair_payload(
                {
                    "nodes": list(sample.get("nodes") or []),
                    "edges": list(sample.get("edges") or []),
                    "optional_edges": [],
                },
                source_text=source_text,
                chapter_path=chapter_path,
                min_nodes=min_nodes,
            )
            repaired_nodes = dedupe_nodes(repaired.get("nodes") or [])
            repaired_aspects = {
                canonicalize_aspect_label(str(node.get("aspect") or "").strip())
                for node in repaired_nodes
            }
            repaired_aspects.discard("unknown")
            if len(repaired_nodes) >= min_nodes and len(repaired_aspects) >= MIN_UNIQUE_ASPECTS:
                repaired["nodes"] = repaired_nodes
                repaired["edges"] = []
                meta["generation_actions"] = ["node_repair_hydrated_source", *repair_actions]
                meta["generation_method"] = "node_repair_hydrated_source"
                repaired["generation_method"] = meta["generation_method"]
                return repaired, meta
        meta["reject_reason"] = "generated_nodes_below_threshold"
        return None, meta

    if hydration_method:
        meta["generation_method"] = "source_segmentation_hydrated"
        payload["generation_method"] = meta["generation_method"]
    return payload, meta


def chunk_sample_to_row(
    sample: dict[str, Any],
    payload: dict[str, Any],
    *,
    task: str = "pipeline_v3_extract_v2_nodes_generated",
) -> dict[str, Any]:
    source_text, _ = hydrate_chunk_source_text(sample)
    if not source_text:
        source_text = clean_source_text(str(sample.get("content") or ""))
    chapter_path = build_chapter_path(list(sample.get("headings") or []))
    user_prompt = build_user_prompt(list(sample.get("headings") or []), source_text)
    return {
        "id": make_sample_id(str(sample["source_file"]), str(sample["chunk_id"])),
        "source_file": sample["source_file"],
        "chunk_id": sample["chunk_id"],
        "task": task,
        "text": format_chat_text(user_prompt, compact_json({"nodes": payload["nodes"], "edges": []})),
        "node_count": len(payload.get("nodes") or []),
        "edge_count": 0,
        "optional_edges": list(payload.get("optional_edges") or sample.get("edges") or []),
        "generation_method": payload.get("generation_method") or "source_segmentation",
        "chapter_path": chapter_path,
    }


def load_chunk_index(pipeline_dir: Path) -> dict[str, dict[str, Any]]:
    from build_sft_dataset import iter_pipeline_chunks

    index: dict[str, dict[str, Any]] = {}
    for sample in iter_pipeline_chunks(pipeline_dir):
        index[make_sample_id(sample["source_file"], sample["chunk_id"])] = sample
    return index


def embedded_source_length(row: dict[str, Any]) -> int:
    return len(extract_source_text(str(row.get("text") or "")))


def audit_manual_review_row(
    row: dict[str, Any],
    chunk_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sample_id = str(row.get("id") or "")
    chunk = chunk_index.get(sample_id)
    embedded_len = embedded_source_length(row)
    raw_len = len(clean_source_text(str((chunk or {}).get("content") or ""))) if chunk else 0
    recoverable_truncation = bool(chunk and raw_len > embedded_len + 40)
    issues = list(row.get("audit_issues") or [])
    hard_evidence_miss = "evidence_not_in_source" in issues
    empty_nodes = "empty_nodes" in issues or int(row.get("node_count") or 0) == 0

    if recoverable_truncation and empty_nodes:
        disposition = "rescuable_truncation"
    elif recoverable_truncation and not hard_evidence_miss:
        disposition = "rescuable_truncation"
    elif hard_evidence_miss and not recoverable_truncation:
        disposition = "reject_hard_evidence_miss"
    elif empty_nodes and not recoverable_truncation:
        disposition = "reject_empty_without_recovery"
    else:
        disposition = "reject_other"

    return {
        "sample_id": sample_id,
        "disposition": disposition,
        "embedded_source_length": embedded_len,
        "raw_chunk_length": raw_len,
        "recoverable_truncation": recoverable_truncation,
        "audit_issues": issues,
        "manual_review_reason": row.get("manual_review_reason"),
    }


def triage_unrepaired_row(
    row: dict[str, Any],
    chunk_index: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    sample_id = str(row.get("id") or "")
    chunk = chunk_index.get(sample_id)
    source_text = clean_source_text(str((chunk or {}).get("content") or extract_source_text(str(row.get("text") or ""))))
    suitability = source_suitability(source_text)
    issues = set(row.get("audit_issues") or [])

    if suitability["table_heavy"] and not suitability["has_enough_aspects"]:
        bucket = "B3_discard"
        reason = "table_heavy_low_aspect_signal"
    elif not suitability["source_long_enough"] or not suitability["has_enough_aspects"]:
        bucket = "B3_discard"
        reason = "source_information_poor"
    elif issues <= {"content_equals_evidence", "missing_aspect", "parent_entity_missing_in_content"}:
        bucket = "B1_deterministic_repair"
        reason = "soft_issue_only"
    elif suitability["has_enough_segments"] and suitability["has_enough_aspects"]:
        bucket = "B2_reextract_from_chunk"
        reason = "chunk_has_aspect_signal"
    else:
        bucket = "B3_discard"
        reason = "low_structure_signal"

    return {
        "sample_id": sample_id,
        "triage_bucket": bucket,
        "triage_reason": reason,
        "audit_issues": sorted(issues),
        "suitability": suitability,
        "node_count": row.get("node_count"),
    }