"""Metrics for Stage 1 evidence-copy curriculum evaluation."""
from __future__ import annotations

import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sft_eval_metrics import (  # noqa: E402
    EvalCaseInput,
    GeneratedCase,
    aspect_key,
    extract_prompt_and_expected,
    extract_source_text,
    infer_aspect_heuristic,
    parse_generated,
    utc_now_iso,
)
from textbook_pipeline.node_guardrails import (  # noqa: E402
    canonicalize_aspect_label,
    evidence_supported_by_source,
)

SINGLE_SUMMARY_MIN_EXPECTED = 3


@dataclass
class Stage1Gate:
    name: str
    actual: float | int | None
    threshold: float | int
    comparator: str
    passed: bool | None


def evaluate_stage1_case(case: GeneratedCase) -> dict[str, Any]:
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

    for index, node in enumerate(generated_nodes):
        if not isinstance(node, dict):
            add_failure("invalid_json", details={"reason": "node_not_object", "node_index": index})
            continue

        aspect = canonicalize_aspect_label(str(node.get("aspect") or "").strip())
        evidence = str(node.get("evidence") or "").strip()
        if not aspect:
            add_failure("missing_aspect", details={"node_index": index, "node": node})

        evidence_total += 1
        if not evidence:
            evidence_rewritten += 1
            add_failure(
                "evidence_not_in_source",
                details={"node_index": index, "failure_reason": "evidence_missing"},
            )
        elif evidence_supported_by_source(evidence, case.source_text):
            evidence_exact += 1
        else:
            evidence_rewritten += 1
            add_failure(
                "evidence_not_in_source",
                details={
                    "node_index": index,
                    "failure_reason": "evidence_rewritten",
                    "evidence_preview": evidence[:160],
                },
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

    expected_node_count = len(expected_nodes)
    actual_node_count = len(generated_nodes)

    return {
        "case_id": case.case_id,
        "suite": case.suite,
        "json_valid": json_valid,
        "has_nodes": has_nodes,
        "empty_nodes": empty_nodes,
        "expected_node_count": expected_node_count,
        "actual_node_count": actual_node_count,
        "evidence_exact_match_rate": round(evidence_exact / evidence_total, 4)
        if evidence_total
        else None,
        "evidence_rewritten_rate": round(evidence_rewritten / evidence_total, 4)
        if evidence_total
        else None,
        "aspect_coverage_rate": round(aspect_coverage_rate, 4)
        if aspect_coverage_rate is not None
        else None,
        "single_summary_node": len(expected_nodes) >= SINGLE_SUMMARY_MIN_EXPECTED
        and len(generated_nodes) == 1,
        "failure_taxonomy": dict(taxonomy_hits),
        "failures": failures,
        "generated_preview": case.raw_text[:500],
    }


def summarize_stage1_cases(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    if not case_results:
        return {}

    def mean_rate(key: str) -> float | None:
        values = [item[key] for item in case_results if item.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    json_valid_rate = round(
        sum(1 for item in case_results if item["json_valid"]) / len(case_results),
        4,
    )
    has_nodes_rate = round(
        sum(1 for item in case_results if item["has_nodes"]) / len(case_results),
        4,
    )
    empty_nodes_rate = round(
        sum(1 for item in case_results if item["empty_nodes"]) / len(case_results),
        4,
    )
    single_summary_node_rate = round(
        sum(1 for item in case_results if item["single_summary_node"]) / len(case_results),
        4,
    )
    avg_nodes = round(
        sum(item["actual_node_count"] for item in case_results) / len(case_results),
        4,
    )

    return {
        "case_count": len(case_results),
        "json_valid_rate": json_valid_rate,
        "has_nodes_rate": has_nodes_rate,
        "empty_nodes_rate": empty_nodes_rate,
        "evidence_exact_match_rate": mean_rate("evidence_exact_match_rate"),
        "evidence_rewritten_rate": mean_rate("evidence_rewritten_rate"),
        "avg_nodes_per_sample": avg_nodes,
        "aspect_coverage_rate": mean_rate("aspect_coverage_rate"),
        "single_summary_node_rate": single_summary_node_rate,
    }


def evaluate_stage1_gates(aggregate: dict[str, Any]) -> dict[str, Any]:
    gates = [
        Stage1Gate(
            "json_valid_rate",
            aggregate.get("json_valid_rate"),
            0.95,
            ">=",
            (aggregate.get("json_valid_rate") or 0) >= 0.95,
        ),
        Stage1Gate(
            "evidence_exact_match_rate",
            aggregate.get("evidence_exact_match_rate"),
            0.90,
            ">=",
            (aggregate.get("evidence_exact_match_rate") or 0) >= 0.90,
        ),
        Stage1Gate(
            "empty_nodes_rate",
            aggregate.get("empty_nodes_rate"),
            0,
            "==",
            aggregate.get("empty_nodes_rate") == 0,
        ),
        Stage1Gate(
            "avg_nodes_per_sample",
            aggregate.get("avg_nodes_per_sample"),
            3,
            ">=",
            (aggregate.get("avg_nodes_per_sample") or 0) >= 3,
        ),
    ]
    ideal_gates = [
        Stage1Gate(
            "json_valid_rate_ideal",
            aggregate.get("json_valid_rate"),
            0.98,
            ">=",
            (aggregate.get("json_valid_rate") or 0) >= 0.98,
        ),
        Stage1Gate(
            "evidence_exact_match_rate_ideal",
            aggregate.get("evidence_exact_match_rate"),
            0.95,
            ">=",
            (aggregate.get("evidence_exact_match_rate") or 0) >= 0.95,
        ),
        Stage1Gate(
            "evidence_rewritten_rate_ideal",
            aggregate.get("evidence_rewritten_rate"),
            0.05,
            "<=",
            (
                aggregate.get("evidence_rewritten_rate")
                if aggregate.get("evidence_rewritten_rate") is not None
                else 1.0
            )
            <= 0.05,
        ),
    ]
    minimum_passed = all(gate.passed for gate in gates)
    ideal_passed = all(gate.passed for gate in ideal_gates)
    return {
        "minimum_passed": minimum_passed,
        "ideal_passed": ideal_passed,
        "minimum_gates": [gate.__dict__ for gate in gates],
        "ideal_gates": [gate.__dict__ for gate in ideal_gates],
        "blockers": [
            f"{gate.name}={gate.actual} {gate.comparator} {gate.threshold}"
            for gate in gates
            if not gate.passed
        ],
    }


def row_to_stage1_case(row: dict[str, Any], suite: str) -> EvalCaseInput:
    prompt, expected = extract_prompt_and_expected(row)
    source_text = extract_source_text(row.get("text") or prompt)
    return EvalCaseInput(
        case_id=str(row.get("id") or suite),
        suite=suite,
        source_text=source_text,
        prompt=prompt,
        expected=expected,
        metadata={key: value for key, value in row.items() if key not in {"text", "expected"}},
    )


def build_stage1_markdown_report(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    gates = report["gates"]
    lines = [
        "# Stage 1 evidence-copy evaluation",
        "",
        f"- evaluated_at: {report['meta']['evaluated_at']}",
        f"- adapter: `{report['meta']['adapter']}`",
        f"- case_count: {aggregate.get('case_count', 0)}",
        "",
        "## Aggregate",
        "",
        f"- json_valid_rate: {aggregate.get('json_valid_rate')}",
        f"- has_nodes_rate: {aggregate.get('has_nodes_rate')}",
        f"- evidence_exact_match_rate: {aggregate.get('evidence_exact_match_rate')}",
        f"- evidence_rewritten_rate: {aggregate.get('evidence_rewritten_rate')}",
        f"- empty_nodes_rate: {aggregate.get('empty_nodes_rate')}",
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