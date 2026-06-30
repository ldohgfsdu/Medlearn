"""Quality gates for pipeline_v3_extract SFT samples.

Reuses Medlearn guardrails where possible. Samples must pass all gates
before entering sft_train.jsonl.
"""
from __future__ import annotations

import re
from typing import Any

from textbook_pipeline.node_guardrails import (
    MAX_NODES_PER_CHUNK,
    evidence_supported_by_source,
    normalize_match_text,
)

ALLOWED_NODE_TYPES = frozenset(
    {"concept", "mechanism", "disease", "symptom", "treatment", "exam"}
)
ALLOWED_EDGE_RELATIONS = frozenset(
    {
        "causes",
        "characteristic_of",
        "treated_by",
        "complication_of",
        "associated_with",
    }
)
REQUIRED_NODE_FIELDS = ("title", "type", "parent_entity", "aspect", "content", "evidence")
SELF_REF_CONTENT_RE = re.compile(r"^(该病|本病|其|上述|前者|后者|这种情况)")
CONTENT_EVIDENCE_RATIO_MAX = 2.8


def _node_identifiers(nodes: list[dict[str, Any]]) -> set[str]:
    ids: set[str] = set()
    for node in nodes:
        title = str(node.get("title") or "").strip()
        parent = str(node.get("parent_entity") or "").strip()
        if title:
            ids.add(normalize_match_text(title))
        if parent:
            ids.add(normalize_match_text(parent))
    return ids


def validate_node_schema(node: Any) -> tuple[bool, str | None]:
    if not isinstance(node, dict):
        return False, "node_not_object"

    for field in REQUIRED_NODE_FIELDS:
        if field not in node:
            return False, f"missing_field:{field}"
        if not str(node.get(field) or "").strip():
            return False, f"empty_field:{field}"

    node_type = str(node["type"]).strip()
    if node_type not in ALLOWED_NODE_TYPES:
        return False, f"invalid_type:{node_type}"

    if not isinstance(node.get("tags", []), list):
        return False, "invalid_tags"

    return True, None


def validate_node_grounding(
    node: dict[str, Any],
    source_text: str,
) -> tuple[bool, str | None]:
    content = str(node.get("content") or "").strip()
    evidence = str(node.get("evidence") or "").strip()
    parent_entity = str(node.get("parent_entity") or "").strip()

    if len(content) < 15:
        return False, "content_too_short"

    if parent_entity and parent_entity not in content[: max(80, len(parent_entity) + 20)]:
        return False, "parent_entity_missing_in_content"

    if SELF_REF_CONTENT_RE.match(content):
        return False, "self_referential_content"

    if not evidence_supported_by_source(evidence, source_text):
        return False, "evidence_not_in_source"

    evidence_len = len(normalize_match_text(evidence))
    content_len = len(normalize_match_text(content))
    if evidence_len > 0 and content_len > evidence_len * CONTENT_EVIDENCE_RATIO_MAX + 48:
        return False, "content_exceeds_evidence"

    return True, None


def validate_edges(
    edges: list[Any],
    nodes: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    if not isinstance(edges, list):
        return False, "edges_not_list"

    identifiers = _node_identifiers(nodes)
    if not identifiers and edges:
        return False, "edges_without_nodes"

    for edge in edges:
        if not isinstance(edge, dict):
            return False, "edge_not_object"

        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        relation = str(edge.get("relation") or "").strip()

        if not source or not target or not relation:
            return False, "edge_missing_fields"

        if relation not in ALLOWED_EDGE_RELATIONS:
            return False, f"invalid_relation:{relation}"

        source_key = normalize_match_text(source)
        target_key = normalize_match_text(target)
        if source_key not in identifiers and not any(
            source_key in ident or ident in source_key for ident in identifiers
        ):
            return False, f"edge_source_unresolved:{source}"

        if target_key not in identifiers and not any(
            target_key in ident or ident in target_key for ident in identifiers
        ):
            return False, f"edge_target_unresolved:{target}"

    return True, None


def count_duplicate_parent_aspects(nodes: list[dict[str, Any]]) -> int:
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for node in nodes:
        key = (
            str(node.get("parent_entity") or "").strip(),
            str(node.get("aspect") or "").strip(),
        )
        if not key[0] or not key[1]:
            continue
        if key in seen:
            duplicates += 1
        seen.add(key)
    return duplicates


def validate_extraction_payload(
    payload: Any,
    source_text: str,
    *,
    allow_empty: bool = False,
) -> tuple[bool, list[str], dict[str, Any]]:
    """Validate one assistant JSON payload against source_text."""
    reasons: list[str] = []
    metrics: dict[str, Any] = {
        "node_count": 0,
        "edge_count": 0,
        "schema_valid": False,
        "evidence_matched": 0,
        "edge_resolved": True,
    }

    if not isinstance(payload, dict):
        return False, ["payload_not_object"], metrics

    nodes = payload.get("nodes")
    edges = payload.get("edges")

    if not isinstance(nodes, list):
        return False, ["nodes_not_list"], metrics

    if edges is None:
        edges = []
    if not isinstance(edges, list):
        return False, ["edges_not_list"], metrics

    metrics["node_count"] = len(nodes)
    metrics["edge_count"] = len(edges)
    metrics["schema_valid"] = True

    if not nodes:
        if allow_empty:
            return True, [], metrics
        return False, ["empty_nodes"], metrics

    if len(nodes) > MAX_NODES_PER_CHUNK:
        reasons.append(f"too_many_nodes:{len(nodes)}")

    dup_aspects = count_duplicate_parent_aspects(nodes)
    if dup_aspects:
        reasons.append(f"duplicate_parent_aspect:{dup_aspects}")

    for index, node in enumerate(nodes):
        ok, reason = validate_node_schema(node)
        if not ok:
            reasons.append(f"node_{index}:{reason}")
            continue

        ok, reason = validate_node_grounding(node, source_text)
        if not ok:
            reasons.append(f"node_{index}:{reason}")
        else:
            metrics["evidence_matched"] += 1

    ok, reason = validate_edges(edges, nodes)
    if not ok:
        reasons.append(reason or "edge_invalid")
        metrics["edge_resolved"] = False

    if metrics["evidence_matched"] < len(nodes):
        pass  # reasons already capture per-node failures

    accepted = not reasons and metrics["evidence_matched"] == len(nodes)
    return accepted, reasons, metrics