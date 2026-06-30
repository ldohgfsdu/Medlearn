"""Gates and comparison helpers for Stage 3 full nodes-only smoke evaluation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

OLD_ADAPTER_BASELINE = {
    "json_valid_rate": 0.952,
    "node_count_recall_mean": 0.348,
    "evidence_exact_match_rate_mean": 0.55,
    "content_equals_evidence_rate_mean": 0.80,
    "aspect_coverage_rate_mean": 0.23,
    "node_f1_mean": 0.30,
    "edge_missing": 11,
    "single_summary_node_rate": 13 / 21,
}


@dataclass
class Stage3Gate:
    name: str
    actual: float | int | None
    threshold: float | int
    comparator: str
    passed: bool | None


def enrich_stage3_aggregate(aggregate: dict[str, Any], case_results: list[dict[str, Any]]) -> dict[str, Any]:
    enriched = dict(aggregate)
    case_count = len(case_results) or 1
    single_summary = sum(
        1
        for item in case_results
        if (item.get("failure_taxonomy") or {}).get("single_summary_node")
    )
    edge_missing = sum(
        (item.get("failure_taxonomy") or {}).get("edge_missing", 0) for item in case_results
    )
    parent_failures = sum(
        (item.get("failure_taxonomy") or {}).get("wrong_parent_entity", 0)
        + (item.get("failure_taxonomy") or {}).get("hallucinated_entity", 0)
        for item in case_results
    )
    total_generated_nodes = sum(item.get("actual_node_count", 0) for item in case_results)
    enriched["single_summary_node_rate"] = round(single_summary / case_count, 4)
    enriched["edge_missing"] = edge_missing
    enriched["parent_entity_grounded_rate"] = round(
        1 - parent_failures / total_generated_nodes,
        4,
    ) if total_generated_nodes else None
    return enriched


def _gate_passed(actual: float | int | None, threshold: float | int, comparator: str) -> bool:
    if actual is None:
        return False
    if comparator == ">=":
        return actual >= threshold
    if comparator == "<=":
        return actual <= threshold
    if comparator == "<":
        return actual < threshold
    if comparator == "==":
        return actual == threshold
    return False


def evaluate_stage3_gates(aggregate: dict[str, Any], *, old_baseline: dict[str, Any]) -> dict[str, Any]:
    minimum = [
        Stage3Gate("json_valid_rate", aggregate.get("json_valid_rate"), 0.95, ">=", None),
        Stage3Gate("node_count_recall_mean", aggregate.get("node_count_recall_mean"), 0.50, ">=", None),
        Stage3Gate(
            "evidence_exact_match_rate_mean",
            aggregate.get("evidence_exact_match_rate_mean"),
            0.80,
            ">=",
            None,
        ),
        Stage3Gate(
            "content_equals_evidence_rate_mean",
            aggregate.get("content_equals_evidence_rate_mean"),
            0.20,
            "<=",
            None,
        ),
        Stage3Gate(
            "aspect_coverage_rate_mean",
            aggregate.get("aspect_coverage_rate_mean"),
            0.40,
            ">=",
            None,
        ),
        Stage3Gate("node_f1_mean", aggregate.get("node_f1_mean"), 0.35, ">=", None),
        Stage3Gate(
            "single_summary_node_rate_vs_old",
            aggregate.get("single_summary_node_rate"),
            old_baseline.get("single_summary_node_rate"),
            "<",
            None,
        ),
    ]
    ideal = [
        Stage3Gate("json_valid_rate_ideal", aggregate.get("json_valid_rate"), 0.98, ">=", None),
        Stage3Gate(
            "node_count_recall_mean_ideal",
            aggregate.get("node_count_recall_mean"),
            0.60,
            ">=",
            None,
        ),
        Stage3Gate(
            "evidence_exact_match_rate_ideal",
            aggregate.get("evidence_exact_match_rate_mean"),
            0.90,
            ">=",
            None,
        ),
        Stage3Gate(
            "content_equals_evidence_rate_ideal",
            aggregate.get("content_equals_evidence_rate_mean"),
            0.10,
            "<=",
            None,
        ),
        Stage3Gate(
            "aspect_coverage_rate_ideal",
            aggregate.get("aspect_coverage_rate_mean"),
            0.50,
            ">=",
            None,
        ),
        Stage3Gate("node_f1_mean_ideal", aggregate.get("node_f1_mean"), 0.45, ">=", None),
    ]
    for gate in minimum:
        gate.passed = _gate_passed(gate.actual, gate.threshold, gate.comparator)
    for gate in ideal:
        gate.passed = _gate_passed(gate.actual, gate.threshold, gate.comparator)

    minimum_passed = all(gate.passed for gate in minimum)
    ideal_passed = all(gate.passed for gate in ideal)
    return {
        "smoke_passed": minimum_passed,
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


def build_stage3_markdown_report(report: dict[str, Any]) -> str:
    aggregate = report["aggregate"]
    gates = report["gates"]
    lines = [
        "# Stage 3 full nodes-only evaluation",
        "",
        f"- evaluated_at: {report['meta']['evaluated_at']}",
        f"- adapter: `{report['meta']['adapter']}`",
        f"- base_adapter: `{report['meta'].get('base_adapter', '')}`",
        f"- case_count: {aggregate.get('case_count', 0)}",
        "",
        "## Aggregate",
        "",
        f"- json_valid_rate: {aggregate.get('json_valid_rate')}",
        f"- node_count_recall_mean: {aggregate.get('node_count_recall_mean')}",
        f"- evidence_exact_match_rate_mean: {aggregate.get('evidence_exact_match_rate_mean')}",
        f"- evidence_rewritten_rate_mean: {aggregate.get('evidence_rewritten_rate_mean')}",
        f"- content_equals_evidence_rate_mean: {aggregate.get('content_equals_evidence_rate_mean')}",
        f"- aspect_coverage_rate_mean: {aggregate.get('aspect_coverage_rate_mean')}",
        f"- node_f1_mean: {aggregate.get('node_f1_mean')}",
        f"- single_summary_node_rate: {aggregate.get('single_summary_node_rate')}",
        f"- edge_missing: {aggregate.get('edge_missing')}",
        f"- parent_entity_grounded_rate: {aggregate.get('parent_entity_grounded_rate')}",
        "",
        "## Gates",
        "",
        f"- smoke_passed: {gates.get('smoke_passed')}",
        f"- minimum_passed: {gates.get('minimum_passed')}",
        f"- ideal_passed: {gates.get('ideal_passed')}",
    ]
    if gates.get("blockers"):
        lines.append(f"- blockers: {', '.join(gates['blockers'])}")
    lines.append("")
    return "\n".join(lines)


def build_comparison_markdown(
    *,
    stage3_aggregate: dict[str, Any],
    old_aggregate: dict[str, Any],
    stage3_gates: dict[str, Any],
) -> str:
    metrics = [
        ("json_valid_rate", "json_valid_rate", ">="),
        ("node_count_recall_mean", "node_count_recall_mean", ">="),
        ("evidence_exact_match_rate", "evidence_exact_match_rate_mean", ">="),
        ("content_equals_evidence_rate", "content_equals_evidence_rate_mean", "<="),
        ("aspect_coverage_mean", "aspect_coverage_rate_mean", ">="),
        ("node_f1", "node_f1_mean", ">="),
        ("single_summary_node_rate", "single_summary_node_rate", "<="),
        ("edge_missing", "edge_missing", "<="),
        ("parent_entity_grounded_rate", "parent_entity_grounded_rate", ">="),
    ]
    lines = [
        "# Stage 3 vs old production adapter comparison",
        "",
        "| Metric | Old adapter | Stage 3 smoke | Delta | Better |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for label, key, direction in metrics:
        old_value = old_aggregate.get(key)
        new_value = stage3_aggregate.get(key)
        if old_value is None or new_value is None:
            continue
        delta = round(new_value - old_value, 4)
        if direction == ">=":
            better = "stage3" if new_value >= old_value else "old"
        elif direction == "<=":
            better = "stage3" if new_value <= old_value else "old"
        else:
            better = "-"
        lines.append(f"| {label} | {old_value} | {new_value} | {delta:+.4f} | {better} |")

    lines.extend(
        [
            "",
            "## Gate status",
            "",
            f"- smoke_passed: {stage3_gates.get('smoke_passed')}",
            f"- minimum_passed: {stage3_gates.get('minimum_passed')}",
            f"- ideal_passed: {stage3_gates.get('ideal_passed')}",
        ]
    )
    if stage3_gates.get("blockers"):
        lines.append(f"- blockers: {', '.join(stage3_gates['blockers'])}")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Old adapter baseline from `training/reports/sft_eval_report.json` unless re-evaluated live.",
            "- Stage 3 smoke must pass minimum gates before any production consideration.",
            "- Passing smoke does not authorize production adapter replacement.",
            "",
        ]
    )
    return "\n".join(lines)