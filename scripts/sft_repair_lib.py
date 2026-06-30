"""Deterministic and constrained repair logic for SFT v2 B-tier candidates."""
from __future__ import annotations

import copy
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
TRAINING_DIR = SCRIPTS_DIR.parent / "training"
for path in (SCRIPTS_DIR, TRAINING_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_sft_dataset import compact_json  # noqa: E402
from sft_eval_metrics import infer_aspect_heuristic  # noqa: E402
from sft_quality_gates import ALLOWED_NODE_TYPES, REQUIRED_NODE_FIELDS  # noqa: E402
from textbook_pipeline.node_guardrails import (  # noqa: E402
    STANDARD_ASPECT_RULES,
    canonicalize_aspect_label,
    evidence_supported_by_source,
    normalize_match_text,
)

SECTION_MARKER_RE = re.compile(r"【([^】]+)】")
CHAPTER_ENTITY_RE = re.compile(r"[>|]\s*([^>|]+?)\s*$")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。；！？])\s*")
MIN_EVIDENCE_LEN = 8
MIN_SEGMENT_LEN = 10
MAX_NODES = 12


def extract_parent_entity_from_chapter(chapter_path: str) -> str:
    path = (chapter_path or "").strip()
    if not path:
        return ""
    segments = [segment.strip() for segment in re.split(r"[>|]", path) if segment.strip()]
    if not segments:
        return ""
    entity = segments[-1]
    entity = re.sub(r"^第[一二三四五六七八九十百零\d]+节\s*", "", entity)
    entity = re.sub(r"^第[一二三四五六七八九十百零\d]+章\s*", "", entity)
    return entity.strip()


def classify_text_aspect(text: str, aspect_hint: str | None = None) -> str:
    marker = SECTION_MARKER_RE.search(text)
    if marker:
        aspect_hint = marker.group(1)
    if aspect_hint:
        hinted = canonicalize_aspect_label(aspect_hint)
        return hinted if hinted else aspect_hint
    for canonical, pattern in STANDARD_ASPECT_RULES:
        if pattern.search(text):
            return canonical
    return "unknown"


def infer_node_type(aspect: str) -> str:
    if aspect in {"治疗"}:
        return "treatment"
    if aspect in {"诊断", "鉴别诊断"}:
        return "exam"
    if aspect in {"临床表现"}:
        return "symptom"
    if aspect in {"发病机制", "病因"}:
        return "mechanism"
    return "disease"


def segment_source_text(source_text: str) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    current_hint: str | None = None
    parts = SECTION_MARKER_RE.split(source_text)
    for index, part in enumerate(parts):
        if index % 2 == 1:
            current_hint = part.strip()
            continue
        for sentence in SENTENCE_SPLIT_RE.split(part):
            sentence = re.sub(r"\s+", " ", sentence).strip()
            if len(sentence) < MIN_SEGMENT_LEN:
                continue
            aspect = classify_text_aspect(sentence, current_hint)
            segments.append(
                {
                    "text": sentence,
                    "aspect_hint": current_hint,
                    "aspect": aspect,
                }
            )
    return segments


def distill_content(parent_entity: str, aspect: str, evidence: str) -> str:
    cleaned = SECTION_MARKER_RE.sub("", evidence).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    clause = re.split(r"[。；]", cleaned)[0].strip() or cleaned
    if clause.startswith(parent_entity):
        clause = clause[len(parent_entity) :].lstrip("，,：:的 ")
    if len(clause) > 96:
        clause = clause[:96].rstrip("，,；; ")
    content = f"{parent_entity}的{aspect}：{clause}"
    if normalize_match_text(content) == normalize_match_text(evidence):
        snippet = clause[:48] if len(clause) > 48 else clause
        content = f"{parent_entity}在{aspect}方面的要点：{snippet}"
    return content.strip()


def content_grounded_in_evidence(
    content: str,
    evidence: str,
    parent_entity: str,
    aspect: str,
) -> bool:
    templates = (
        f"{parent_entity}的{aspect}：",
        f"{parent_entity}在{aspect}方面的要点：",
    )
    body = content
    for template in templates:
        body = body.replace(template, "")
    body_norm = normalize_match_text(body)
    evidence_norm = normalize_match_text(evidence)
    if not body_norm:
        return False
    return body_norm in evidence_norm


def snap_evidence_to_source(evidence: str, source_text: str) -> str | None:
    evidence = evidence.strip()
    if not evidence:
        return None
    if evidence_supported_by_source(evidence, source_text):
        return evidence
    normalized = normalize_match_text(evidence)
    source_norm = normalize_match_text(source_text)
    if normalized not in source_norm:
        return None
    start = source_norm.find(normalized)
    if start < 0:
        return None
    # Recover a source substring with flexible whitespace by regex search on tail.
    pattern = re.escape(evidence[: min(24, len(evidence))]).replace(r"\ ", r"\s*")
    match = re.search(pattern, source_text)
    if match:
        tail = source_text[match.start() :]
        collapsed = ""
        for char in tail:
            collapsed += char
            if normalize_match_text(collapsed) == normalized:
                return collapsed
    return evidence


def normalize_node(
    node: dict[str, Any],
    *,
    parent_entity: str,
    source_text: str,
    chapter_path: str,
) -> dict[str, Any] | None:
    node = copy.deepcopy(node)
    parent = str(node.get("parent_entity") or "").strip() or parent_entity
    if not parent:
        return None

    evidence = str(node.get("evidence") or "").strip()
    snapped = snap_evidence_to_source(evidence, source_text) if evidence else None
    if not snapped:
        return None
    evidence = snapped

    aspect = str(node.get("aspect") or "").strip()
    if not aspect or infer_aspect_heuristic(node) == "unknown":
        aspect = classify_text_aspect(evidence)
    aspect = canonicalize_aspect_label(aspect)
    if aspect == "unknown":
        return None

    node_type = str(node.get("type") or "").strip()
    if node_type not in ALLOWED_NODE_TYPES:
        node_type = infer_node_type(aspect)

    content = str(node.get("content") or "").strip()
    if not content or normalize_match_text(content) == normalize_match_text(evidence):
        content = distill_content(parent, aspect, evidence)
    if normalize_match_text(content) == normalize_match_text(evidence):
        return None
    if not content_grounded_in_evidence(content, evidence, parent, aspect):
        return None
    if parent not in content[: max(80, len(parent) + 20)]:
        content = f"{parent}的{aspect}：{content.split('：', 1)[-1]}"

    title = str(node.get("title") or "").strip() or f"{parent}的{aspect}"
    return {
        "title": title,
        "type": node_type,
        "parent_entity": parent,
        "aspect": aspect,
        "content": content,
        "evidence": evidence,
        "tags": list(node.get("tags") or []),
    }


def dedupe_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for node in nodes:
        key = (
            str(node.get("parent_entity") or "").strip(),
            canonicalize_aspect_label(str(node.get("aspect") or "").strip()),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(node)
    return deduped


def r1_deterministic_repair(
    payload: dict[str, Any],
    *,
    source_text: str,
    chapter_path: str,
) -> tuple[dict[str, Any], list[str]]:
    actions: list[str] = []
    parent_entity = extract_parent_entity_from_chapter(chapter_path)
    nodes = payload.get("nodes") or []
    optional_edges = list(payload.get("edges") or payload.get("optional_edges") or [])

    normalized_nodes: list[dict[str, Any]] = []
    for node in nodes:
        original_content = str(node.get("content") or "").strip()
        original_evidence = str(node.get("evidence") or "").strip()
        repaired = normalize_node(
            node,
            parent_entity=parent_entity,
            source_text=source_text,
            chapter_path=chapter_path,
        )
        if repaired:
            if (
                original_evidence
                and normalize_match_text(original_content)
                == normalize_match_text(original_evidence)
                and normalize_match_text(repaired["content"])
                != normalize_match_text(repaired["evidence"])
            ):
                actions.append("rewrite_content_not_evidence")
            normalized_nodes.append(repaired)
        else:
            actions.append("drop_invalid_node")

    before = len(normalized_nodes)
    normalized_nodes = dedupe_nodes(normalized_nodes)
    if len(normalized_nodes) < before:
        actions.append("dedupe_nodes")

    if optional_edges:
        actions.append("move_edges_to_optional")

    if actions:
        actions.insert(0, "r1_deterministic")

    return {
        "nodes": normalized_nodes[:MAX_NODES],
        "edges": [],
        "optional_edges": optional_edges,
    }, actions


def r2_fix_content_equals_evidence(
    payload: dict[str, Any],
    *,
    source_text: str,
    chapter_path: str,
) -> tuple[dict[str, Any], list[str]]:
    actions: list[str] = []
    parent_entity = extract_parent_entity_from_chapter(chapter_path)
    repaired_nodes: list[dict[str, Any]] = []

    for node in payload.get("nodes") or []:
        node = copy.deepcopy(node)
        evidence = str(node.get("evidence") or "").strip()
        content = str(node.get("content") or "").strip()
        parent = str(node.get("parent_entity") or "").strip() or parent_entity
        aspect = canonicalize_aspect_label(str(node.get("aspect") or "").strip())

        if not evidence_supported_by_source(evidence, source_text):
            repaired_nodes.append(node)
            continue

        if normalize_match_text(content) != normalize_match_text(evidence):
            repaired_nodes.append(node)
            continue

        new_content = distill_content(parent, aspect, evidence)
        if (
            normalize_match_text(new_content) != normalize_match_text(evidence)
            and content_grounded_in_evidence(new_content, evidence, parent, aspect)
            and parent in new_content[: max(80, len(parent) + 20)]
        ):
            node["content"] = new_content
            actions.append("rewrite_content_not_evidence")
        repaired_nodes.append(node)

    if actions:
        actions.insert(0, "r2_content_rewrite")
    payload = copy.deepcopy(payload)
    payload["nodes"] = repaired_nodes
    return payload, actions


def evidence_variants(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if len(candidate) < MIN_EVIDENCE_LEN or candidate in seen:
            return
        seen.add(candidate)
        variants.append(candidate)

    add(text)
    for part in re.split(r"[。；]", text):
        add(part)
    return variants


def build_best_node_for_aspect_bucket(
    aspect: str,
    sentences: list[str],
    *,
    parent_entity: str,
    source_text: str,
) -> dict[str, Any] | None:
    for sentence in sentences:
        for evidence in evidence_variants(sentence):
            node = build_node_from_segment(
                {"text": evidence, "aspect": aspect},
                parent_entity=parent_entity,
                source_text=source_text,
            )
            if node:
                return node
    return None


def build_node_from_segment(
    segment: dict[str, Any],
    *,
    parent_entity: str,
    source_text: str,
) -> dict[str, Any] | None:
    evidence = segment["text"].strip()
    if not evidence_supported_by_source(evidence, source_text):
        return None
    aspect = segment.get("aspect") or "unknown"
    if aspect == "unknown":
        return None
    content = distill_content(parent_entity, aspect, evidence)
    if normalize_match_text(content) == normalize_match_text(evidence):
        return None
    if not content_grounded_in_evidence(content, evidence, parent_entity, aspect):
        return None
    return {
        "title": f"{parent_entity}的{aspect}",
        "type": infer_node_type(aspect),
        "parent_entity": parent_entity,
        "aspect": aspect,
        "content": content,
        "evidence": evidence,
        "tags": [],
    }


def r3_split_by_source_segmentation(
    payload: dict[str, Any],
    *,
    source_text: str,
    chapter_path: str,
    min_nodes: int = 3,
) -> tuple[dict[str, Any], list[str]]:
    actions: list[str] = []
    parent_entity = extract_parent_entity_from_chapter(chapter_path)
    if not parent_entity:
        return payload, actions

    existing = payload.get("nodes") or []
    covered_aspects = {
        canonicalize_aspect_label(str(node.get("aspect") or "").strip())
        for node in existing
    }

    buckets: dict[str, list[str]] = defaultdict(list)
    for segment in segment_source_text(source_text):
        aspect = segment["aspect"]
        if aspect == "unknown":
            continue
        buckets[aspect].append(segment["text"])

    new_nodes = list(existing)
    for aspect, sentences in buckets.items():
        if aspect in covered_aspects:
            continue
        node = build_best_node_for_aspect_bucket(
            aspect,
            sentences,
            parent_entity=parent_entity,
            source_text=source_text,
        )
        if node:
            new_nodes.append(node)
            covered_aspects.add(aspect)
            actions.append(f"add_aspect_node:{aspect}")

    new_nodes = dedupe_nodes(new_nodes)
    new_nodes = [
        node
        for node in (
            normalize_node(
                item,
                parent_entity=parent_entity,
                source_text=source_text,
                chapter_path=chapter_path,
            )
            for item in new_nodes
        )
        if node
    ]

    if len(new_nodes) >= min_nodes and actions:
        actions.insert(0, "r3_source_segmentation")
        payload = copy.deepcopy(payload)
        payload["nodes"] = new_nodes[:MAX_NODES]
        return payload, actions

    if len(existing) < min_nodes:
        rebuilt: list[dict[str, Any]] = []
        for aspect, sentences in buckets.items():
            if not sentences:
                continue
            node = build_best_node_for_aspect_bucket(
                aspect,
                sentences,
                parent_entity=parent_entity,
                source_text=source_text,
            )
            if node:
                rebuilt.append(node)
        rebuilt = dedupe_nodes(rebuilt)
        if len(rebuilt) >= min_nodes:
            actions = ["r3_full_rebuild_from_source"] + [
                f"aspect:{node['aspect']}" for node in rebuilt
            ]
            payload = copy.deepcopy(payload)
            payload["nodes"] = rebuilt[:MAX_NODES]
            return payload, actions

    return payload, actions


def repair_payload(
    payload: dict[str, Any],
    *,
    source_text: str,
    chapter_path: str,
    min_nodes: int = 3,
) -> tuple[dict[str, Any], list[str]]:
    all_actions: list[str] = []
    current = {
        "nodes": list(payload.get("nodes") or []),
        "edges": [],
        "optional_edges": list(payload.get("optional_edges") or payload.get("edges") or []),
    }

    current, actions = r1_deterministic_repair(
        current,
        source_text=source_text,
        chapter_path=chapter_path,
    )
    all_actions.extend(actions)

    current, actions = r2_fix_content_equals_evidence(
        current,
        source_text=source_text,
        chapter_path=chapter_path,
    )
    all_actions.extend(actions)

    if len(current.get("nodes") or []) < min_nodes:
        current, actions = r3_split_by_source_segmentation(
            current,
            source_text=source_text,
            chapter_path=chapter_path,
            min_nodes=min_nodes,
        )
        all_actions.extend(actions)
    else:
        # Aspect imbalance: try adding missing aspect buckets.
        current, actions = r3_split_by_source_segmentation(
            current,
            source_text=source_text,
            chapter_path=chapter_path,
            min_nodes=min_nodes,
        )
        all_actions.extend(actions)

    return current, all_actions


def rebuild_row_text(row: dict[str, Any], payload: dict[str, Any]) -> str:
    full_text = str(row.get("text") or "")
    if "<|im_start|>assistant\n" not in full_text:
        return full_text
    prompt_part = full_text.split("<|im_start|>assistant\n", 1)[0] + "<|im_start|>assistant\n"
    nodes_only = {"nodes": payload.get("nodes") or [], "edges": []}
    return prompt_part + compact_json(nodes_only) + "<|im_end|>"


def build_repaired_row(
    row: dict[str, Any],
    payload: dict[str, Any],
    *,
    repair_actions: list[str],
    audit_after: dict[str, Any],
) -> dict[str, Any]:
    repaired = copy.deepcopy(row)
    repaired["text"] = rebuild_row_text(row, payload)
    repaired["node_count"] = len(payload.get("nodes") or [])
    repaired["edge_count"] = 0
    repaired["optional_edges"] = list(payload.get("optional_edges") or [])
    repaired["repair_actions"] = repair_actions
    repaired["tier"] = audit_after.get("tier")
    repaired["tier_label"] = audit_after.get("tier_label")
    repaired["audit_issues"] = audit_after.get("issues")
    repaired["evidence_exact_match_rate"] = audit_after.get("evidence_exact_match_rate")
    repaired["content_equals_evidence_rate"] = audit_after.get(
        "content_equals_evidence_rate"
    )
    repaired["repaired"] = True
    return repaired