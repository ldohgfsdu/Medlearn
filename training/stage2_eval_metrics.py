"""Metrics for Stage 2 evidence + content distill curriculum evaluation."""
from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sft_eval_metrics import (  # noqa: E402
    GeneratedCase,
    aspect_key,
    infer_aspect_heuristic,
)
from textbook_pipeline.node_guardrails import (  # noqa: E402
    canonicalize_aspect_label,
    evidence_supported_by_source,
    normalize_match_text,
)

SINGLE_SUMMARY_MIN_EXPECTED = 3


@dataclass
class Stage2Gate:
    name: str
    actual: float | int | None
    threshold: float | int
    comparator: str
    passed: bool | None


def content_body(content: str) -> str:
    text = content.strip()
    if "：" in text:
        return text.split("：", 1)[-1].strip()
    if ":" in text:
        return text.split(":", 1)[-1].strip()
    return text


def content_grounded_in_evidence(content: str, evidence: str, source_text: str) -> bool:
    body = content_body(content)
    body_norm = normalize_match_text(body)
    if not body_norm:
        return False
    evidence_norm = normalize_match_text(evidence)
    source_norm = normalize_match_text(source_text)
    if body_norm in evidence_norm:
        return True
    if body_norm in source_norm:
        return True
    # Allow condensed distill when main clause still appears in evidence.
    clause = re.split(r"[。；]", body)[0].strip()
    clause_norm = normalize_match_text(clause)
    return bool(clause_norm) and clause_norm in evidence_norm


def evaluate_stage2_case(case: GeneratedCase) -> dict[str, Any]:
    expected = case.expected or {}
    expected_nodes = list(expected.get("nodes") or [])
    generated = case.generated or {}
    generated_nodes = list((generated or {}).get("nodes") or []) if case.generated else []

    failures: list[dict[str, Any]] = []
    taxonomy_hits: Counter[str] = Counter()

    def add_failure(failure_type: str, *, details: dict[str, Any] | None = None) -> None:
        taxonomy_hits[failure_type] += 1
        failures.append(
            {
                "case_id": case.case_id,
                "suite": case.suite,
                "failure_type": failure_type,
                **(details or {}),
            }
        )

    json_valid = case.json_valid
    has_nodes = isinstance(generated, dict) and isinstance(generated.get("nodes"), list)
    empty_nodes = json_valid and has_nodes and not generated_nodes

    if not json_valid:
        add_failure("invalid_json", details={"raw_preview": case.raw_text[:500]})
    if empty_nodes:
        add_failure("empty_nodes")
    if (
        len(expected_nodes) >= SINGLE_SUMMARY_MIN_EXPECTED
        and len(generated_nodes) == 1
    ):
        add_failure("single_summary_node")

    evidence_total = 0
    evidence_exact = 0
    evidence_rewritten = 0
    content_total = 0
    content_missing = 0
    content_equals_evidence = 0
    content_grounded = 0

    for index, node in enumerate(generated_nodes):
        if not isinstance(node, dict):
            add_failure("invalid_json", details={"reason": "node_not_object", "node_index": index})
            continue

        aspect = canonicalize_aspect_label(str(node.get("aspect") or "").strip())
        evidence = str(node.get("evidence") or "").strip()
        content = str(node.get("content") or "").strip()

        if not aspect:
            add_failure("missing_aspect", details={"node_index": index})

        evidence_total += 1
        if not evidence:
            evidence_rewritten += 1
            add_failure("evidence_not_in_source", details={"node_index": index, "failure_reason": "evidence_missing"})
        elif evidence_supported_by_source(evidence, case.source_text):
            evidence_exact += 1
        else:
            evidence_rewritten += 1
            add_failure(
                "evidence_not_in_source",
                details={"node_index": index, "failure_reason": "evidence_rewritten"},
            )

        content_total += 1
        if not content:
            content_missing += 1
            add_failure("content_missing", details={"node_index": index})
            continue

        if evidence and normalize_match_text(content) == normalize_match_text(evidence):
            content_equals_evidence += 1
            add_failure("content_equals_evidence", details={"node_index": index})

        if content_grounded_in_evidence(content, evidence, case.source_text):
            content_grounded += 1
        else:
            add_failure(
                "content_not_grounded",
                details={"node_index": index, "content_preview": content[:120]},
            )

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
    aspect_coverage_rate = (
        len(expected_aspect_keys & actual_aspect_keys) / len(expected_aspect_keys)
        if expected_aspect_keys
        else None
    )

    return {
        "case_id": case.case_id,
        "suite": case.suite,
        "json_valid": json_valid,
        "has_nodes": has_nodes,
        "empty_nodes": empty_nodes,
        "expected_node_count": len(expected_nodes),
        "actual_node_count": len(generated_nodes),
        "evidence_exact_match_rate": round(evidence_exact / evidence_total, 4) if evidence_total else None,
        "evidence_rewritten_rate": round(evidence_rewritten / evidence_total, 4) if evidence_total else None,
        "content_equals_evidence_rate": round(content_equals_evidence / content_total, 4)
        if content_total
        else None,
        "content_missing_rate": round(content_missing / content_total, 4) if content_total else None,
        "content_grounded_in_evidence_rate": round(content_grounded / content_total, 4)
        if content_total
        else None,
        "aspect_coverage_rate": round(aspect_coverage_rate, 4) if aspect_coverage_rate is not None else None,
        "single_summary_node": len(expected_nodes) >= SINGLE_SUMMARY_MIN_EXPECTED
        and len(generated_nodes) == 1,
        "failure_taxonomy": dict(taxonomy_hits),
        "failures": failures,
        "generated_preview": case.raw_text[:500],
    }


def summarize_stage2_cases(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not case_results:
        return {}

    def mean_rate(key: str) -> float | None:
        values = [item[key] for item in case_results if item.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    return {
        "case_count": len(case_results),
        "json_valid_rate": round(sum(1 for item in case_results if item["json_valid"]) / len(case_results), 4),
        "has_nodes_rate": round(sum(1 for item in case_results if item["has_nodes"]) / len(case_results), 4),
        "empty_nodes_rate": round(sum(1 for item in case_results if item["empty_nodes"]) / len(case_results), 4),
        "evidence_exact_match_rate": mean_rate("evidence_exact_match_rate"),
        "evidence_rewritten_rate": mean_rate("evidence_rewritten_rate"),
        "content_equals_evidence_rate": mean_rate("content_equals_evidence_rate"),
        "content_missing_rate": mean_rate("content_missing_rate"),
        "content_grounded_in_evidence_rate": mean_rate("content_grounded_in_evidence_rate"),
        "avg_nodes_per_sample": round(
            sum(item["actual_node_count"] for item in case_results) / len(case_results),
            4,
        ),
        "aspect_coverage_rate": mean_rate("aspect_coverage_rate"),
        "single_summary_node_rate": round(
            sum(1 for item in case_results if item["single_summary_node"]) / len(case_results),
            4,
        ),
    }


def _gate_passed(actual: float | int | None, threshold: float | int, comparator: str) -> bool:
    if actual is None:
        return False
    if comparator == ">=":
        return actual >= threshold
    if comparator == "<=":
        return actual <= threshold
    if comparator == "==":
        return actual == threshold
    return False


def evaluate_stage2_gates(aggregate: dict[str, Any]) -> dict[str, Any]:
    minimum = [
        Stage2Gate("json_valid_rate", aggregate.get("json_valid_rate"), 0.95, ">=", None),
        Stage2Gate("evidence_exact_match_rate", aggregate.get("evidence_exact_match_rate"), 0.90, ">=", None),
        Stage2Gate("content_equals_evidence_rate", aggregate.get("content_equals_evidence_rate"), 0.10, "<=", None),
        Stage2Gate("content_missing_rate", aggregate.get("content_missing_rate"), 0.10, "<=", None),
        Stage2Gate("avg_nodes_per_sample", aggregate.get("avg_nodes_per_sample"), 3, ">=", None),
    ]
    ideal = [
        Stage2Gate("json_valid_rate_ideal", aggregate.get("json_valid_rate"), 0.98, ">=", None),
        Stage2Gate("evidence_exact_match_rate_ideal", aggregate.get("evidence_exact_match_rate"), 0.95, ">=", None),
        Stage2Gate("content_equals_evidence_rate_ideal", aggregate.get("content_equals_evidence_rate"), 0.05, "<=", None),
        Stage2Gate(
            "content_grounded_in_evidence_rate_ideal",
            aggregate.get("content_grounded_in_evidence_rate"),
            0.90,
            ">=",
            None,
        ),
        Stage2Gate("avg_nodes_per_sample_ideal", aggregate.get("avg_nodes_per_sample"), 3.5, ">=", None),
    ]
    for gate in minimum:
        gate.passed = _gate_passed(gate.actual, gate.threshold, gate.comparator)
    for gate in ideal:
        gate.passed = _gate_passed(gate.actual, gate.threshold, gate.comparator)

    minimum_passed = all(gate.passed for gate in minimum)
    ideal_passed = all(gate.passed for gate in ideal)
    return {
        "minimum_passed": minimum_passed,
        "ideal_passed": ideal_passed,
        "minimum_gates": [gate.__dict__ for gate in minimum],
        "ideal_gates": [gate.__dict__ for gate in ideal],
        "blockers": [
            f"{gate.name}={gate.actual} {gate.comparator} {gate.threshold}"
            for gate in minimum
            if not gate.passed
        ],
    }


def build_stage2_markdown_report(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    gates = report["gates"]
    lines = [
        "# Stage 2 evidence + content distill evaluation",
        "",
        f"- evaluated_at: {report['meta']['evaluated_at']}",
        f"- adapter: `{report['meta']['adapter']}`",
        f"- base_adapter: `{report['meta'].get('base_adapter', '')}`",
        f"- case_count: {aggregate.get('case_count', 0)}",
        "",
        "## Aggregate",
        "",
        f"- json_valid_rate: {aggregate.get('json_valid_rate')}",
        f"- evidence_exact_match_rate: {aggregate.get('evidence_exact_match_rate')}",
        f"- evidence_rewritten_rate: {aggregate.get('evidence_rewritten_rate')}",
        f"- content_equals_evidence_rate: {aggregate.get('content_equals_evidence_rate')}",
        f"- content_missing_rate: {aggregate.get('content_missing_rate')}",
        f"- content_grounded_in_evidence_rate: {aggregate.get('content_grounded_in_evidence_rate')}",
        f"- avg_nodes_per_sample: {aggregate.get('avg_nodes_per_sample')}",
        f"- aspect_coverage_rate: {aggregate.get('aspect_coverage_rate')}",
        f"- single_summary_node_rate: {aggregate.get('single_summary_node_rate')}",
        "",
        "## Gates",
        "",
        f"- minimum_passed: {gates['minimum_passed']}",
        f"- ideal_passed: {gates['ideal_passed']}",
    ]
    if gates["blockers"]:
        lines.append(f"- blockers: {', '.join(gates['blockers'])}")
    lines.append("")
    return "\n".join(lines)