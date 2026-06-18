"""Deterministic metrics for MedLearn SFT adapter evaluation (no model I/O)."""
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sft_quality_gates import (  # noqa: E402
    REQUIRED_NODE_FIELDS,
    validate_edges,
    validate_node_schema,
)
from textbook_pipeline.node_guardrails import (  # noqa: E402
    canonicalize_aspect_label,
    evidence_supported_by_source,
    normalize_match_text,
)

ASSISTANT_MARKER = "<|im_start|>assistant\n"
END_MARKER = "<|im_end|>"
SOURCE_MARKER = "教材原文："
FAILURE_TAXONOMY = (
    "invalid_json",
    "empty_nodes",
    "single_summary_node",
    "evidence_not_in_source",
    "content_equals_evidence",
    "missing_aspect",
    "wrong_parent_entity",
    "hallucinated_entity",
    "edge_missing",
    "edge_invalid_target",
)

LABEL_MATCH_THRESHOLD = 0.75
EVIDENCE_OVERLAP_THRESHOLD = 0.6
SINGLE_SUMMARY_MIN_EXPECTED = 3
ENGLISH_ASPECT_ALIASES = {
    "definition": "定义",
    "clinical_manifestations": "临床表现",
    "diagnostic_criteria": "诊断",
    "treatment_principles": "治疗",
    "indications": "治疗",
    "adverse_reactions": "预后",
    "clinical_significance": "临床表现",
    "normal_range": "诊断",
    "clinical_relevance": "临床表现",
    "etiology": "病因",
    "pathogenesis": "发病机制",
    "complication": "预后",
    "prevention": "预防",
}


@dataclass
class EvalCaseInput:
    case_id: str
    suite: str
    source_text: str
    prompt: str
    expected: dict[str, Any] | None
    golden_title: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GeneratedCase:
    case_id: str
    suite: str
    source_text: str
    expected: dict[str, Any] | None
    generated: dict[str, Any] | None
    raw_text: str
    json_valid: bool
    golden_title: str | None = None


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def extract_source_text(chat_or_prompt: str) -> str:
    text = chat_or_prompt
    if ASSISTANT_MARKER in text:
        text = text.split(ASSISTANT_MARKER, 1)[0]
    if "<|im_start|>user\n" in text:
        text = text.split("<|im_start|>user\n", 1)[1]
    if SOURCE_MARKER not in text:
        return ""
    body = text.split(SOURCE_MARKER, 1)[1]
    body = body.split("/no_think", 1)[0]
    body = body.split("<|im_end|>", 1)[0]
    return re.sub(r"\s+", " ", body).strip()


def extract_prompt_and_expected(row: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    if row.get("expected"):
        full_text = str(row["text"])
        prompt, _ = full_text.split(ASSISTANT_MARKER, 1)
        prompt += ASSISTANT_MARKER
        return prompt, row["expected"]

    full_text = str(row["text"])
    if ASSISTANT_MARKER not in full_text:
        return full_text, None
    prompt, expected_text = full_text.split(ASSISTANT_MARKER, 1)
    prompt += ASSISTANT_MARKER
    expected_text = expected_text.split(END_MARKER, 1)[0].strip()
    try:
        expected = json_loads(expected_text)
    except ValueError:
        expected = None
    return prompt, expected


def json_loads(text: str) -> dict[str, Any]:
    import json

    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError("expected object")
    return value


def parse_generated(text: str) -> tuple[dict[str, Any] | None, str]:
    import json

    candidate = text.split(END_MARKER, 1)[0].strip()
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start < 0 or end <= start:
        return None, candidate
    candidate = candidate[start : end + 1]
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None, candidate
    if not isinstance(payload, dict):
        return None, candidate
    return payload, candidate


def label_similarity(left: str, right: str) -> float:
    a = normalize_match_text(left)
    b = normalize_match_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def node_label(node: dict[str, Any]) -> str:
    title = str(node.get("title") or "").strip()
    if title:
        return title
    parent = str(node.get("parent_entity") or "").strip()
    aspect = str(node.get("aspect") or "").strip()
    return f"{parent}:{aspect}" if parent or aspect else ""


def evidence_overlap_score(left: str, right: str) -> float:
    a = normalize_match_text(left)
    b = normalize_match_text(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return 1.0
    best = 0.0
    shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
    for length in range(len(shorter), 11, -1):
        for index in range(len(shorter) - length + 1):
            fragment = shorter[index : index + length]
            if fragment in longer:
                return length / len(longer)
    overlap_chars = len(set(a) & set(b))
    return overlap_chars / max(len(set(a)), len(set(b)), 1)


def aspect_key(node: dict[str, Any]) -> tuple[str, str]:
    parent = str(node.get("parent_entity") or "").strip()
    aspect = infer_aspect_heuristic(node)
    return parent, aspect


def infer_aspect_heuristic(node: dict[str, Any]) -> str:
    declared = str(node.get("aspect") or "").strip()
    if declared:
        lowered = declared.lower()
        if lowered in ENGLISH_ASPECT_ALIASES:
            return ENGLISH_ASPECT_ALIASES[lowered]
        return canonicalize_aspect_label(declared)
    content = str(node.get("content") or "")
    title = str(node.get("title") or "")
    node_type = str(node.get("type") or "")
    for text in (declared, title, content, node_type):
        if text:
            canonical = canonicalize_aspect_label(text)
            if canonical != text or canonical in {
                "定义",
                "流行病学",
                "病因",
                "发病机制",
                "临床表现",
                "鉴别诊断",
                "诊断",
                "预防",
                "治疗",
                "预后",
            }:
                return canonical
    return declared or "unknown"


def parent_entity_category(
    parent_entity: str,
    source_text: str,
    content: str,
    *,
    for_expected: bool = False,
) -> str | None:
    parent = parent_entity.strip()
    if not parent:
        return "wrong_parent_entity"
    normalized_source = normalize_match_text(source_text)
    parent_in_source = normalize_match_text(parent) in normalized_source
    content_prefix = content[: max(80, len(parent) + 20)]
    parent_in_content = parent in content_prefix

    if not parent_in_source and not parent_in_content:
        return "hallucinated_entity" if not for_expected else "A_not_in_source"
    if parent_in_source and not parent_in_content:
        return "wrong_parent_entity" if not for_expected else "B_wrong_generated"
    if for_expected and parent_in_content and not parent_in_source:
        return "C_annotation_unreasonable"
    return None


def match_nodes(
    expected_nodes: list[dict[str, Any]],
    generated_nodes: list[dict[str, Any]],
) -> dict[str, Any]:
    matched_pairs: list[dict[str, Any]] = []
    used_generated: set[int] = set()

    for expected_index, expected_node in enumerate(expected_nodes):
        best_index = -1
        best_score = 0.0
        best_label_sim = 0.0
        best_evidence_overlap = 0.0
        for generated_index, generated_node in enumerate(generated_nodes):
            if generated_index in used_generated:
                continue
            label_sim = label_similarity(
                node_label(expected_node),
                node_label(generated_node),
            )
            evidence_overlap = evidence_overlap_score(
                str(expected_node.get("evidence") or ""),
                str(generated_node.get("evidence") or ""),
            )
            if label_sim >= LABEL_MATCH_THRESHOLD or evidence_overlap >= EVIDENCE_OVERLAP_THRESHOLD:
                score = max(label_sim, evidence_overlap)
                if score > best_score:
                    best_score = score
                    best_index = generated_index
                    best_label_sim = label_sim
                    best_evidence_overlap = evidence_overlap
        if best_index >= 0:
            used_generated.add(best_index)
            matched_pairs.append(
                {
                    "expected_index": expected_index,
                    "generated_index": best_index,
                    "label_similarity": round(best_label_sim, 4),
                    "evidence_overlap": round(best_evidence_overlap, 4),
                    "match_score": round(best_score, 4),
                }
            )

    true_positive = len(matched_pairs)
    generated_count = len(generated_nodes)
    expected_count = len(expected_nodes)
    precision = true_positive / generated_count if generated_count else 0.0
    recall = true_positive / expected_count if expected_count else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
    return {
        "node_precision": round(precision, 4),
        "node_recall": round(recall, 4),
        "node_f1": round(f1, 4),
        "matched_pairs": matched_pairs,
        "matching_mode": "heuristic",
        "matching_rule": (
            f"label_sim>={LABEL_MATCH_THRESHOLD} OR "
            f"evidence_overlap>={EVIDENCE_OVERLAP_THRESHOLD}"
        ),
    }


def aggregate_rates(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "mean": 0.0,
            "min": 0.0,
            "max": 0.0,
        }
    return {
        "mean": round(sum(values) / len(values), 4),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
    }


def evaluate_case(case: GeneratedCase) -> dict[str, Any]:
    expected_nodes = list((case.expected or {}).get("nodes") or [])
    expected_edges = list((case.expected or {}).get("edges") or [])
    generated = case.generated
    generated_nodes = list((generated or {}).get("nodes") or []) if generated else []
    generated_edges = list((generated or {}).get("edges") or []) if generated else []

    failures: list[dict[str, Any]] = []
    taxonomy_hits: Counter[str] = Counter()

    def add_failure(
        failure_type: str,
        *,
        node_index: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        taxonomy_hits[failure_type] += 1
        failures.append(
            {
                "case_id": case.case_id,
                "suite": case.suite,
                "golden_title": case.golden_title,
                "failure_type": failure_type,
                "node_index": node_index,
                **(details or {}),
            }
        )

    json_valid = case.json_valid
    has_nodes = isinstance(generated, dict) and isinstance(generated.get("nodes"), list)
    has_edges = isinstance(generated, dict) and isinstance(generated.get("edges"), list)

    if not json_valid:
        add_failure("invalid_json", details={"raw_preview": case.raw_text[:500]})
    if json_valid and has_nodes and not generated_nodes:
        add_failure("empty_nodes")
    if (
        len(expected_nodes) >= SINGLE_SUMMARY_MIN_EXPECTED
        and len(generated_nodes) == 1
    ):
        add_failure("single_summary_node")

    required_complete_nodes = 0
    evidence_total = 0
    evidence_exact = 0
    evidence_missing = 0
    evidence_rewritten = 0
    content_equals_evidence_nodes = 0

    for index, node in enumerate(generated_nodes):
        if not isinstance(node, dict):
            add_failure(
                "invalid_json",
                node_index=index,
                details={"reason": "node_not_object"},
            )
            continue

        if all(str(node.get(field) or "").strip() for field in REQUIRED_NODE_FIELDS):
            required_complete_nodes += 1
        else:
            add_failure(
                "missing_aspect",
                node_index=index,
                details={"reason": "required_fields_incomplete", "node": node},
            )

        content = str(node.get("content") or "").strip()
        evidence = str(node.get("evidence") or "").strip()
        parent_entity = str(node.get("parent_entity") or "").strip()
        aspect = str(node.get("aspect") or "").strip()

        if not aspect:
            add_failure(
                "missing_aspect",
                node_index=index,
                details={"node_id": node_label(node)},
            )

        evidence_total += 1
        if not evidence:
            evidence_missing += 1
            add_failure(
                "evidence_not_in_source",
                node_index=index,
                details={
                    "node_id": node_label(node),
                    "content": content,
                    "evidence": evidence,
                    "source_match": False,
                    "failure_reason": "evidence_missing",
                },
            )
        elif evidence_supported_by_source(evidence, case.source_text):
            evidence_exact += 1
        else:
            evidence_rewritten += 1
            add_failure(
                "evidence_not_in_source",
                node_index=index,
                details={
                    "node_id": node_label(node),
                    "content": content,
                    "evidence": evidence,
                    "source_match": False,
                    "failure_reason": "evidence_not_in_source",
                    "source_excerpt": case.source_text[:240],
                },
            )

        if content and evidence and normalize_match_text(content) == normalize_match_text(evidence):
            content_equals_evidence_nodes += 1
            add_failure(
                "content_equals_evidence",
                node_index=index,
                details={
                    "node_id": node_label(node),
                    "content": content,
                    "evidence": evidence,
                },
            )

        parent_issue = parent_entity_category(
            parent_entity,
            case.source_text,
            content,
            for_expected=False,
        )
        if parent_issue == "hallucinated_entity":
            add_failure(
                "hallucinated_entity",
                node_index=index,
                details={"parent_entity": parent_entity, "content": content},
            )
        elif parent_issue == "wrong_parent_entity":
            add_failure(
                "wrong_parent_entity",
                node_index=index,
                details={
                    "parent_entity": parent_entity,
                    "content": content,
                    "category": "B_model_wrong_parent",
                },
            )

        schema_ok, schema_reason = validate_node_schema(node)
        if not schema_ok:
            add_failure(
                "missing_aspect",
                node_index=index,
                details={"reason": schema_reason, "node": node},
            )

    if generated is not None and has_edges:
        edge_ok, edge_reason = validate_edges(generated_edges, generated_nodes)
        if not edge_ok:
            if edge_reason and edge_reason.startswith("edge_target_unresolved"):
                add_failure(
                    "edge_invalid_target",
                    details={"reason": edge_reason},
                )
            elif edge_reason and edge_reason.startswith("edge_source_unresolved"):
                add_failure(
                    "edge_invalid_target",
                    details={"reason": edge_reason},
                )
            else:
                add_failure(
                    "edge_invalid_target",
                    details={"reason": edge_reason},
                )

    if expected_edges and not generated_edges:
        add_failure("edge_missing", details={"expected_edge_count": len(expected_edges)})

    expected_aspect_keys = {
        aspect_key(node)
        for node in expected_nodes
        if infer_aspect_heuristic(node) != "unknown"
    }
    actual_aspect_keys = {
        aspect_key(node)
        for node in generated_nodes
        if infer_aspect_heuristic(node) != "unknown"
    }
    missing_aspect_keys = sorted(expected_aspect_keys - actual_aspect_keys)
    aspect_coverage_rate = (
        len(expected_aspect_keys & actual_aspect_keys) / len(expected_aspect_keys)
        if expected_aspect_keys
        else None
    )

    expected_node_count = len(expected_nodes)
    actual_node_count = len(generated_nodes)
    node_count_recall = (
        actual_node_count / expected_node_count if expected_node_count else None
    )

    node_match = (
        match_nodes(expected_nodes, generated_nodes)
        if expected_nodes
        else {
            "node_precision": None,
            "node_recall": None,
            "node_f1": None,
            "matched_pairs": [],
            "matching_mode": "heuristic",
            "matching_rule": (
                f"label_sim>={LABEL_MATCH_THRESHOLD} OR "
                f"evidence_overlap>={EVIDENCE_OVERLAP_THRESHOLD}"
            ),
        }
    )

    expected_parent_audit = []
    for index, node in enumerate(expected_nodes):
        category = parent_entity_category(
            str(node.get("parent_entity") or ""),
            case.source_text,
            str(node.get("content") or ""),
            for_expected=True,
        )
        if category:
            expected_parent_audit.append(
                {
                    "expected_index": index,
                    "parent_entity": node.get("parent_entity"),
                    "category": category,
                }
            )

    return {
        "case_id": case.case_id,
        "suite": case.suite,
        "golden_title": case.golden_title,
        "json_valid": json_valid,
        "has_nodes": has_nodes,
        "has_edges": has_edges,
        "expected_node_count": expected_node_count,
        "actual_node_count": actual_node_count,
        "node_count_recall": round(node_count_recall, 4) if node_count_recall is not None else None,
        "expected_edge_count": len(expected_edges),
        "actual_edge_count": len(generated_edges),
        "required_fields_complete_rate": round(
            required_complete_nodes / len(generated_nodes),
            4,
        )
        if generated_nodes
        else (1.0 if json_valid and not generated_nodes else 0.0),
        "evidence_exact_match_rate": round(evidence_exact / evidence_total, 4)
        if evidence_total
        else None,
        "evidence_missing_rate": round(evidence_missing / evidence_total, 4)
        if evidence_total
        else None,
        "evidence_rewritten_rate": round(evidence_rewritten / evidence_total, 4)
        if evidence_total
        else None,
        "content_equals_evidence_rate": round(
            content_equals_evidence_nodes / len(generated_nodes),
            4,
        )
        if generated_nodes
        else None,
        "aspect_coverage_mode": "heuristic",
        "expected_aspects": [list(key) for key in sorted(expected_aspect_keys)],
        "actual_aspects": [list(key) for key in sorted(actual_aspect_keys)],
        "missing_aspects": [list(key) for key in missing_aspect_keys],
        "aspect_coverage_rate": round(aspect_coverage_rate, 4)
        if aspect_coverage_rate is not None
        else None,
        "node_precision": node_match["node_precision"],
        "node_recall": node_match["node_recall"],
        "node_f1": node_match["node_f1"],
        "node_matching_mode": node_match["matching_mode"],
        "matched_pairs": node_match["matched_pairs"],
        "expected_parent_entity_audit": expected_parent_audit,
        "failure_taxonomy": dict(taxonomy_hits),
        "failures": failures,
        "generated_preview": case.raw_text[:500],
    }


def summarize_cases(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not case_results:
        return {}

    json_valid = [1.0 if item["json_valid"] else 0.0 for item in case_results]
    has_nodes = [1.0 if item["has_nodes"] else 0.0 for item in case_results]
    has_edges = [1.0 if item["has_edges"] else 0.0 for item in case_results]
    required_fields = [
        item["required_fields_complete_rate"]
        for item in case_results
        if item["required_fields_complete_rate"] is not None
    ]
    node_count_recalls = [
        item["node_count_recall"]
        for item in case_results
        if item["node_count_recall"] is not None
    ]
    aspect_coverage = [
        item["aspect_coverage_rate"]
        for item in case_results
        if item["aspect_coverage_rate"] is not None
    ]
    evidence_exact = [
        item["evidence_exact_match_rate"]
        for item in case_results
        if item["evidence_exact_match_rate"] is not None
    ]
    evidence_missing = [
        item["evidence_missing_rate"]
        for item in case_results
        if item["evidence_missing_rate"] is not None
    ]
    evidence_rewritten = [
        item["evidence_rewritten_rate"]
        for item in case_results
        if item["evidence_rewritten_rate"] is not None
    ]
    content_equals_evidence = [
        item["content_equals_evidence_rate"]
        for item in case_results
        if item["content_equals_evidence_rate"] is not None
    ]
    node_precision = [
        item["node_precision"] for item in case_results if item["node_precision"] is not None
    ]
    node_recall = [item["node_recall"] for item in case_results if item["node_recall"] is not None]
    node_f1 = [item["node_f1"] for item in case_results if item["node_f1"] is not None]

    taxonomy = Counter()
    for item in case_results:
        taxonomy.update(item.get("failure_taxonomy") or {})

    expected_nodes = [item["expected_node_count"] for item in case_results]
    actual_nodes = [item["actual_node_count"] for item in case_results]

    return {
        "case_count": len(case_results),
        "json_valid_rate": round(sum(json_valid) / len(json_valid), 4),
        "has_nodes_rate": round(sum(has_nodes) / len(has_nodes), 4),
        "has_edges_rate": round(sum(has_edges) / len(has_edges), 4),
        "required_fields_complete_rate": round(
            sum(required_fields) / len(required_fields),
            4,
        )
        if required_fields
        else None,
        "avg_expected_nodes": round(sum(expected_nodes) / len(expected_nodes), 4),
        "avg_actual_nodes": round(sum(actual_nodes) / len(actual_nodes), 4),
        "node_count_recall_mean": aggregate_rates(node_count_recalls)["mean"],
        "node_count_recall_min": aggregate_rates(node_count_recalls)["min"],
        "node_count_recall_max": aggregate_rates(node_count_recalls)["max"],
        "aspect_coverage_rate_mean": aggregate_rates(aspect_coverage)["mean"],
        "evidence_exact_match_rate_mean": aggregate_rates(evidence_exact)["mean"],
        "evidence_missing_rate_mean": aggregate_rates(evidence_missing)["mean"],
        "evidence_rewritten_rate_mean": aggregate_rates(evidence_rewritten)["mean"],
        "content_equals_evidence_rate_mean": aggregate_rates(content_equals_evidence)["mean"],
        "node_precision_mean": aggregate_rates(node_precision)["mean"],
        "node_recall_mean": aggregate_rates(node_recall)["mean"],
        "node_f1_mean": aggregate_rates(node_f1)["mean"],
        "failure_taxonomy": dict(sorted(taxonomy.items())),
    }


def build_markdown_report(report: dict[str, Any]) -> str:
    meta = report["meta"]
    aggregate = report["aggregate"]
    lines = [
        "# MedLearn SFT Eval Report",
        "",
        f"- Evaluated at: `{meta['evaluated_at']}`",
        f"- Base model: `{meta['base_model']}`",
        f"- Adapter: `{meta['adapter']}`",
        f"- Suites: {', '.join(meta['suites'])}",
        f"- Aspect coverage mode: `{meta['aspect_coverage_mode']}`",
        f"- Node matching mode: `{meta['node_matching_mode']}`",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]

    metric_rows = [
        ("Cases", aggregate.get("case_count")),
        ("JSON valid rate", aggregate.get("json_valid_rate")),
        ("Has nodes rate", aggregate.get("has_nodes_rate")),
        ("Has edges rate", aggregate.get("has_edges_rate")),
        ("Required fields complete rate", aggregate.get("required_fields_complete_rate")),
        ("Avg expected nodes", aggregate.get("avg_expected_nodes")),
        ("Avg actual nodes", aggregate.get("avg_actual_nodes")),
        ("Node count recall (mean)", aggregate.get("node_count_recall_mean")),
        ("Node count recall (min)", aggregate.get("node_count_recall_min")),
        ("Aspect coverage rate (mean)", aggregate.get("aspect_coverage_rate_mean")),
        ("Evidence exact match rate (mean)", aggregate.get("evidence_exact_match_rate_mean")),
        ("Evidence rewritten rate (mean)", aggregate.get("evidence_rewritten_rate_mean")),
        ("Content equals evidence rate (mean)", aggregate.get("content_equals_evidence_rate_mean")),
        ("Node precision (mean)", aggregate.get("node_precision_mean")),
        ("Node recall (mean)", aggregate.get("node_recall_mean")),
        ("Node F1 (mean)", aggregate.get("node_f1_mean")),
    ]
    for label, value in metric_rows:
        if value is None:
            continue
        lines.append(f"| {label} | {value} |")

    lines.extend(["", "## Failure Taxonomy", ""])
    taxonomy = aggregate.get("failure_taxonomy") or {}
    if taxonomy:
        lines.append("| Failure | Count |")
        lines.append("| --- | ---: |")
        for key, count in taxonomy.items():
            lines.append(f"| {key} | {count} |")
    else:
        lines.append("No failures recorded.")

    for suite_name, suite_report in report.get("suites", {}).items():
        lines.extend(["", f"## Suite: {suite_name}", ""])
        summary = suite_report.get("aggregate") or {}
        lines.append(
            f"Cases: {summary.get('case_count', 0)} | "
            f"node recall mean: {summary.get('node_count_recall_mean')} | "
            f"evidence exact mean: {summary.get('evidence_exact_match_rate_mean')}"
        )
        lines.append("")
        lines.append("| case_id | expected | actual | node_recall | evidence_exact | aspect_cov | node_f1 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for case in suite_report.get("cases") or []:
            lines.append(
                "| {case_id} | {expected} | {actual} | {recall} | {evidence} | {aspect} | {f1} |".format(
                    case_id=case["case_id"],
                    expected=case["expected_node_count"],
                    actual=case["actual_node_count"],
                    recall=case.get("node_count_recall"),
                    evidence=case.get("evidence_exact_match_rate"),
                    aspect=case.get("aspect_coverage_rate"),
                    f1=case.get("node_f1"),
                )
            )

    lines.extend(
        [
            "",
            "## Diagnosis",
            "",
            report.get("diagnosis", "No diagnosis generated."),
            "",
        ]
    )
    return "\n".join(lines)


def build_diagnosis(aggregate: dict[str, Any]) -> str:
    parts: list[str] = []
    json_rate = aggregate.get("json_valid_rate")
    if json_rate is not None:
        if json_rate >= 1.0:
            parts.append("JSON envelope is stable (100% valid).")
        else:
            parts.append(f"JSON envelope is unstable ({json_rate:.1%} valid).")

    recall_mean = aggregate.get("node_count_recall_mean")
    if recall_mean is not None:
        if recall_mean < 0.5:
            parts.append(
                f"Node recall is the primary bottleneck (mean recall {recall_mean:.1%})."
            )
        else:
            parts.append(f"Node recall is moderate (mean recall {recall_mean:.1%}).")

    evidence_mean = aggregate.get("evidence_exact_match_rate_mean")
    rewritten_mean = aggregate.get("evidence_rewritten_rate_mean")
    if evidence_mean is not None:
        if evidence_mean < 0.8:
            parts.append(
                f"Strict evidence grounding is weak (exact match {evidence_mean:.1%}"
                + (
                    f", rewritten {rewritten_mean:.1%})."
                    if rewritten_mean is not None
                    else ")."
                )
            )
        else:
            parts.append(f"Evidence grounding is acceptable (exact match {evidence_mean:.1%}).")

    content_eq = aggregate.get("content_equals_evidence_rate_mean")
    if content_eq is not None and content_eq >= 0.5:
        parts.append(
            f"Model often copies summary into evidence (content==evidence {content_eq:.1%})."
        )

    aspect_mean = aggregate.get("aspect_coverage_rate_mean")
    if aspect_mean is not None and aspect_mean < 0.6:
        parts.append(f"Aspect coverage is low (mean {aspect_mean:.1%}).")

    taxonomy = aggregate.get("failure_taxonomy") or {}
    if taxonomy.get("single_summary_node"):
        parts.append(
            f"Single-summary collapse observed in {taxonomy['single_summary_node']} cases."
        )

    return " ".join(parts) if parts else "Insufficient metrics to diagnose."