"""Shared audit and classification logic for SFT dataset quality hardening."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TRAINING_DIR = PROJECT_ROOT / "training"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
for path in (SCRIPTS_DIR, TRAINING_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from sft_eval_metrics import (  # noqa: E402
    aspect_key,
    extract_prompt_and_expected,
    extract_source_text,
    infer_aspect_heuristic,
    parent_entity_category,
)
from sft_quality_gates import (  # noqa: E402
    REQUIRED_NODE_FIELDS,
    validate_edges,
    validate_node_schema,
)
from textbook_pipeline.node_guardrails import (  # noqa: E402
    evidence_supported_by_source,
    normalize_match_text,
)

CHAPTER_PATH_RE = re.compile(r"章节路径：(.+?)\n教材原文：", re.DOTALL)
DEFAULT_RULES_PATH = TRAINING_DIR / "data_cleaning_rules.yaml"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_cleaning_rules(path: Path | None = None) -> dict[str, Any]:
    rules_path = path or DEFAULT_RULES_PATH
    return yaml.safe_load(rules_path.read_text(encoding="utf-8"))


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def extract_chapter_path(chat_or_prompt: str) -> str:
    match = CHAPTER_PATH_RE.search(chat_or_prompt)
    return match.group(1).strip() if match else ""


def source_context(source_text: str, chapter_path: str) -> str:
    parts = [part.strip() for part in (chapter_path, source_text) if part.strip()]
    return "\n".join(parts)


def parse_row_payload(row: dict[str, Any]) -> tuple[str, str, dict[str, Any] | None, str]:
    text = str(row.get("text") or "")
    source_text = extract_source_text(text)
    chapter_path = extract_chapter_path(text)
    _, expected = extract_prompt_and_expected(row)
    return source_text, chapter_path, expected, text


def collect_sample_issues(
    *,
    source_text: str,
    chapter_path: str,
    payload: dict[str, Any] | None,
    rules: dict[str, Any],
    focus_nodes_only: bool = False,
) -> tuple[set[str], list[dict[str, Any]], dict[str, Any]]:
    issues: set[str] = set()
    failures: list[dict[str, Any]] = []
    context = source_context(source_text, chapter_path)

    if not source_text.strip():
        issues.add("source_text_missing")

    if payload is None:
        issues.add("invalid_json")
        return issues, failures, _empty_metrics()

    nodes = payload.get("nodes")
    edges = payload.get("edges") or []

    if not isinstance(nodes, list):
        issues.add("invalid_json")
        return issues, failures, _empty_metrics()

    if not nodes:
        issues.add("empty_nodes")
        return issues, failures, _empty_metrics()

    accept_cfg = rules.get("accept") or {}
    min_nodes = int(accept_cfg.get("min_nodes_per_sample", 3))
    if len(nodes) < min_nodes:
        issues.add("single_summary_node")
    elif len(nodes) == 1:
        issues.add("single_summary_node")

    evidence_total = 0
    evidence_exact = 0
    content_equals_evidence_nodes = 0
    missing_aspect_nodes = 0
    parent_entity_missing = 0
    hallucinated_entities = 0

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            issues.add("nodes_missing_required_fields")
            failures.append(
                {
                    "node_index": index,
                    "failure_type": "nodes_missing_required_fields",
                    "reason": "node_not_object",
                }
            )
            continue

        schema_ok, schema_reason = validate_node_schema(node)
        if not schema_ok:
            if schema_reason == "empty_field:aspect":
                issues.add("missing_aspect")
                missing_aspect_nodes += 1
                failures.append(
                    {
                        "node_index": index,
                        "failure_type": "missing_aspect",
                        "reason": schema_reason,
                        "node": node,
                    }
                )
            else:
                issues.add("nodes_missing_required_fields")
                failures.append(
                    {
                        "node_index": index,
                        "failure_type": "nodes_missing_required_fields",
                        "reason": schema_reason,
                        "node": node,
                    }
                )
            continue

        content = str(node.get("content") or "").strip()
        evidence = str(node.get("evidence") or "").strip()
        parent_entity = str(node.get("parent_entity") or "").strip()
        aspect = str(node.get("aspect") or "").strip()

        if not aspect or infer_aspect_heuristic(node) == "unknown":
            issues.add("missing_aspect")
            missing_aspect_nodes += 1
            failures.append(
                {
                    "node_index": index,
                    "failure_type": "missing_aspect",
                    "node_id": node.get("title"),
                }
            )

        evidence_total += 1
        if not evidence or not evidence_supported_by_source(evidence, context):
            issues.add("evidence_not_in_source")
            failures.append(
                {
                    "node_index": index,
                    "failure_type": "evidence_not_in_source",
                    "content": content,
                    "evidence": evidence,
                    "source_match": False,
                }
            )
        else:
            evidence_exact += 1

        if content and evidence and normalize_match_text(content) == normalize_match_text(evidence):
            issues.add("content_equals_evidence")
            content_equals_evidence_nodes += 1
            failures.append(
                {
                    "node_index": index,
                    "failure_type": "content_equals_evidence",
                    "content": content,
                    "evidence": evidence,
                }
            )

        parent_issue = parent_entity_category(
            parent_entity,
            context,
            content,
            for_expected=True,
        )
        if parent_issue == "A_not_in_source" or parent_issue == "hallucinated_entity":
            if accept_cfg.get("require_parent_entity_in_source", True):
                issues.add("hallucinated_entity")
                hallucinated_entities += 1
                failures.append(
                    {
                        "node_index": index,
                        "failure_type": "hallucinated_entity",
                        "parent_entity": parent_entity,
                        "category": "A_not_in_source",
                    }
                )
        elif parent_issue in {"B_wrong_generated", "wrong_parent_entity"}:
            issues.add("parent_entity_missing_in_content")
            parent_entity_missing += 1
            failures.append(
                {
                    "node_index": index,
                    "failure_type": "parent_entity_missing_in_content",
                    "parent_entity": parent_entity,
                    "category": "B_model_or_label",
                }
            )
        elif parent_issue == "C_annotation_unreasonable":
            failures.append(
                {
                    "node_index": index,
                    "failure_type": "parent_entity_missing_in_content",
                    "parent_entity": parent_entity,
                    "category": "C_annotation_unreasonable",
                }
            )

    if not focus_nodes_only:
        edge_ok, edge_reason = validate_edges(edges, nodes)
        if edges and not edge_ok:
            if edge_reason and (
                edge_reason.startswith("edge_target_unresolved")
                or edge_reason.startswith("edge_source_unresolved")
            ):
                issues.add("edge_invalid_target")
                failures.append(
                    {
                        "failure_type": "edge_invalid_target",
                        "reason": edge_reason,
                    }
                )
            else:
                issues.add("edge_missing")
                failures.append(
                    {
                        "failure_type": "edge_missing",
                        "reason": edge_reason,
                    }
                )

    aspect_keys = {aspect_key(node) for node in nodes if isinstance(node, dict)}
    aspects_by_parent: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        if not isinstance(node, dict):
            continue
        parent = str(node.get("parent_entity") or "").strip()
        aspects_by_parent[parent].add(infer_aspect_heuristic(node))

    aspect_balance = rules.get("aspect_balance") or {}
    min_unique = int(aspect_balance.get("min_unique_aspects_per_parent_entity", 3))
    for parent, aspects in aspects_by_parent.items():
        cleaned = {aspect for aspect in aspects if aspect and aspect != "unknown"}
        if parent and len(cleaned) < min_unique:
            issues.add("aspect_imbalance")
            failures.append(
                {
                    "failure_type": "aspect_imbalance",
                    "parent_entity": parent,
                    "unique_aspects": sorted(cleaned),
                    "required_min": min_unique,
                }
            )

    metrics = {
        "node_count": len(nodes),
        "edge_count": len(edges) if isinstance(edges, list) else 0,
        "unique_aspect_count": len(aspect_keys),
        "avg_aspects_per_parent_entity": round(
            sum(len(values) for values in aspects_by_parent.values())
            / max(len(aspects_by_parent), 1),
            4,
        ),
        "evidence_exact_match_rate": round(evidence_exact / evidence_total, 4)
        if evidence_total
        else 0.0,
        "content_equals_evidence_rate": round(
            content_equals_evidence_nodes / len(nodes),
            4,
        ),
        "missing_aspect_nodes": missing_aspect_nodes,
        "parent_entity_missing_in_content_nodes": parent_entity_missing,
        "hallucinated_entity_nodes": hallucinated_entities,
        "aspects_by_parent": {
            parent: sorted(values) for parent, values in aspects_by_parent.items()
        },
    }
    return issues, failures, metrics


def _empty_metrics() -> dict[str, Any]:
    return {
        "node_count": 0,
        "edge_count": 0,
        "unique_aspect_count": 0,
        "avg_aspects_per_parent_entity": 0.0,
        "evidence_exact_match_rate": 0.0,
        "content_equals_evidence_rate": 0.0,
        "missing_aspect_nodes": 0,
        "parent_entity_missing_in_content_nodes": 0,
        "hallucinated_entity_nodes": 0,
        "aspects_by_parent": {},
    }


def check_accept_criteria(metrics: dict[str, Any], issues: set[str], rules: dict[str, Any]) -> list[str]:
    accept_cfg = rules.get("accept") or {}
    failures: list[str] = []

    min_nodes = int(accept_cfg.get("min_nodes_per_sample", 3))
    if metrics.get("node_count", 0) < min_nodes:
        failures.append(f"min_nodes_per_sample:{metrics.get('node_count', 0)}<{min_nodes}")

    if accept_cfg.get("evidence_must_be_exact_substring", True):
        if metrics.get("evidence_exact_match_rate", 0.0) < 1.0:
            failures.append("evidence_must_be_exact_substring")

    if not accept_cfg.get("allow_content_equals_evidence", False):
        if metrics.get("content_equals_evidence_rate", 0.0) > 0.0:
            failures.append("allow_content_equals_evidence")

    if accept_cfg.get("require_aspect", True) and metrics.get("missing_aspect_nodes", 0) > 0:
        failures.append("require_aspect")

    if accept_cfg.get("require_parent_entity_in_source", True) and metrics.get(
        "hallucinated_entity_nodes", 0
    ) > 0:
        failures.append("require_parent_entity_in_source")

    aspect_balance = rules.get("aspect_balance") or {}
    min_unique = int(aspect_balance.get("min_unique_aspects_per_parent_entity", 3))
    for parent, aspects in (metrics.get("aspects_by_parent") or {}).items():
        cleaned = [aspect for aspect in aspects if aspect and aspect != "unknown"]
        if parent and len(cleaned) < min_unique:
            failures.append(f"aspect_balance:{parent}<{min_unique}")

    return failures


def classify_tier(issues: set[str], metrics: dict[str, Any], rules: dict[str, Any]) -> str:
    hard = set(rules.get("hard_reject") or [])
    soft = set(rules.get("soft_repair") or [])

    if issues & hard:
        return "C"

    accept_failures = check_accept_criteria(metrics, issues, rules)
    soft_hits = issues & soft

    if not soft_hits and not accept_failures:
        return "A"
    if soft_hits or accept_failures:
        return "B"
    return "C"


def audit_metadata_only_row(
    row: dict[str, Any],
    *,
    source_file: str,
) -> dict[str, Any]:
    reasons = [str(reason) for reason in (row.get("reasons") or [])]
    issues: set[str] = set()
    for reason in reasons:
        if "evidence_not_in_source" in reason:
            issues.add("evidence_not_in_source")
        elif "parent_entity_missing_in_content" in reason:
            issues.add("parent_entity_missing_in_content")
        elif "empty_nodes" in reason:
            issues.add("empty_nodes")
        elif "edge_target_unresolved" in reason or "edge_source_unresolved" in reason:
            issues.add("edge_invalid_target")
        elif reason.startswith("missing_field") or "missing_field" in reason:
            issues.add("nodes_missing_required_fields")

    metrics = row.get("metrics") or {}
    node_count = int(row.get("node_count") or metrics.get("node_count") or 0)
    evidence_matched = int(metrics.get("evidence_matched") or 0)
    evidence_rate = round(evidence_matched / node_count, 4) if node_count else 0.0

    return {
        "sample_id": str(row.get("id") or "unknown"),
        "source_file": source_file,
        "tier": "C",
        "tier_label": "rejected",
        "node_count": node_count,
        "edge_count": int(metrics.get("edge_count") or 0),
        "unique_aspect_count": 0,
        "avg_aspects_per_parent_entity": 0.0,
        "evidence_exact_match_rate": evidence_rate,
        "content_equals_evidence_rate": 0.0,
        "issues": sorted(issues) or ["metadata_only_rejected"],
        "hard_reject_reasons": sorted(issues),
        "soft_repair_reasons": [],
        "accept_failures": ["metadata_only_no_text_field"],
        "metrics": metrics,
        "failures": [{"failure_type": reason} for reason in reasons],
        "chapter_path": "",
        "source_text_length": 0,
        "metadata_only": True,
    }


def audit_training_row(
    row: dict[str, Any],
    *,
    rules: dict[str, Any],
    source_file: str,
    focus_nodes_only: bool | None = None,
) -> dict[str, Any]:
    if focus_nodes_only is None:
        focus_nodes_only = bool((rules.get("training_focus") or {}).get("include_edges_in_loss") is False)

    source_text, chapter_path, payload, _ = parse_row_payload(row)
    issues, failures, metrics = collect_sample_issues(
        source_text=source_text,
        chapter_path=chapter_path,
        payload=payload,
        rules=rules,
        focus_nodes_only=focus_nodes_only,
    )
    tier = classify_tier(issues, metrics, rules)
    hard = set(rules.get("hard_reject") or [])
    soft = set(rules.get("soft_repair") or [])

    return {
        "sample_id": str(row.get("id") or "unknown"),
        "source_file": source_file,
        "tier": tier,
        "tier_label": {"A": "accepted", "B": "repair_candidate", "C": "rejected"}[tier],
        "node_count": metrics.get("node_count", 0),
        "edge_count": metrics.get("edge_count", 0),
        "unique_aspect_count": metrics.get("unique_aspect_count", 0),
        "avg_aspects_per_parent_entity": metrics.get("avg_aspects_per_parent_entity", 0.0),
        "evidence_exact_match_rate": metrics.get("evidence_exact_match_rate", 0.0),
        "content_equals_evidence_rate": metrics.get("content_equals_evidence_rate", 0.0),
        "issues": sorted(issues),
        "hard_reject_reasons": sorted(issues & hard),
        "soft_repair_reasons": sorted(issues & soft),
        "accept_failures": check_accept_criteria(metrics, issues, rules),
        "metrics": metrics,
        "failures": failures,
        "chapter_path": chapter_path,
        "source_text_length": len(source_text),
        "salvaged_from_partial_chunk": bool(row.get("salvaged_from_partial_chunk")),
    }


def summarize_audit_results(results: list[dict[str, Any]]) -> dict[str, Any]:
    if not results:
        return {"sample_count": 0}

    tier_counts = Counter(item["tier"] for item in results)
    issue_counts = Counter(
        issue for item in results for issue in item.get("issues") or []
    )
    node_counts = [item.get("node_count", 0) for item in results]
    evidence_rates = [item.get("evidence_exact_match_rate", 0.0) for item in results]
    content_eq_rates = [item.get("content_equals_evidence_rate", 0.0) for item in results]
    aspect_counts = [item.get("unique_aspect_count", 0) for item in results]
    single_node_samples = sum(1 for count in node_counts if count == 1)

    return {
        "sample_count": len(results),
        "tier_a_accepted": tier_counts.get("A", 0),
        "tier_b_repair": tier_counts.get("B", 0),
        "tier_c_rejected": tier_counts.get("C", 0),
        "acceptance_rate": round(tier_counts.get("A", 0) / len(results), 4),
        "repair_candidate_rate": round(tier_counts.get("B", 0) / len(results), 4),
        "rejection_rate": round(tier_counts.get("C", 0) / len(results), 4),
        "evidence_exact_match_rate_mean": round(sum(evidence_rates) / len(evidence_rates), 4),
        "content_equals_evidence_rate_mean": round(sum(content_eq_rates) / len(content_eq_rates), 4),
        "avg_nodes_per_sample": round(sum(node_counts) / len(node_counts), 4),
        "avg_aspects_per_sample": round(sum(aspect_counts) / len(aspect_counts), 4),
        "single_node_sample_count": single_node_samples,
        "single_node_sample_rate": round(single_node_samples / len(results), 4),
        "issue_taxonomy": dict(sorted(issue_counts.items())),
    }


def build_audit_markdown(report: dict[str, Any]) -> str:
    meta = report.get("meta") or {}
    aggregate = report.get("aggregate") or {}
    lines = [
        "# SFT Dataset Audit Report",
        "",
        f"- Generated at: `{meta.get('generated_at')}`",
        f"- Rules version: `{meta.get('rules_version')}`",
        f"- Sources: {', '.join(meta.get('sources') or [])}",
        "",
        "## Aggregate",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    rows = [
        ("Samples audited", aggregate.get("sample_count")),
        ("Tier A (accepted)", aggregate.get("tier_a_accepted")),
        ("Tier B (repair)", aggregate.get("tier_b_repair")),
        ("Tier C (rejected)", aggregate.get("tier_c_rejected")),
        ("Acceptance rate", aggregate.get("acceptance_rate")),
        ("Evidence exact match (mean)", aggregate.get("evidence_exact_match_rate_mean")),
        ("Content==evidence (mean)", aggregate.get("content_equals_evidence_rate_mean")),
        ("Avg nodes / sample", aggregate.get("avg_nodes_per_sample")),
        ("Avg aspects / sample", aggregate.get("avg_aspects_per_sample")),
        ("Single-node samples", aggregate.get("single_node_sample_count")),
    ]
    for label, value in rows:
        if value is None:
            continue
        lines.append(f"| {label} | {value} |")

    eval_bridge = report.get("eval_failure_bridge") or {}
    if eval_bridge:
        lines.extend(
            [
                "",
                "## Eval Failure Bridge",
                "",
                f"Top adapter eval failures mapped to dataset issues: "
                f"`{eval_bridge.get('top_eval_failure_types')}`",
            ]
        )

    decision = report.get("decision_gate") or {}
    lines.extend(
        [
            "",
            "## Decision Gate",
            "",
            f"- Ready for LoRA v2: **{decision.get('ready_for_training', False)}**",
            f"- Blockers: {', '.join(decision.get('blockers') or []) or 'none'}",
            "",
            report.get("recommendation", ""),
        ]
    )
    return "\n".join(lines)


def evaluate_decision_gate(
    aggregate: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    gate = rules.get("decision_gate") or {}
    blockers: list[str] = []

    accepted = aggregate.get("tier_a_accepted", 0)
    if accepted < int(gate.get("min_accepted_samples_to_train", 100)):
        blockers.append(f"accepted_samples={accepted}<{gate.get('min_accepted_samples_to_train', 100)}")

    evidence_mean = aggregate.get("evidence_exact_match_rate_mean", 0.0)
    if evidence_mean < float(gate.get("min_evidence_exact_match_rate", 0.9)):
        blockers.append(
            f"evidence_exact_match_rate={evidence_mean}<{gate.get('min_evidence_exact_match_rate', 0.9)}"
        )

    content_eq = aggregate.get("content_equals_evidence_rate_mean", 0.0)
    if content_eq > float(gate.get("max_content_equals_evidence_rate", 0.1)):
        blockers.append(
            f"content_equals_evidence_rate={content_eq}>{gate.get('max_content_equals_evidence_rate', 0.1)}"
        )

    avg_nodes = aggregate.get("avg_nodes_per_sample", 0.0)
    if avg_nodes < float(gate.get("min_avg_nodes_per_sample", 3)):
        blockers.append(
            f"avg_nodes_per_sample={avg_nodes}<{gate.get('min_avg_nodes_per_sample', 3)}"
        )

    return {
        "ready_for_training": not blockers,
        "blockers": blockers,
        "accepted_samples": accepted,
        "target_accepted_samples": gate.get("target_accepted_samples", 300),
    }


def bridge_eval_failures(
    eval_report_path: Path,
    failure_jsonl_path: Path,
) -> dict[str, Any]:
    eval_report = {}
    if eval_report_path.exists():
        eval_report = json.loads(eval_report_path.read_text(encoding="utf-8"))

    failure_types = Counter()
    if failure_jsonl_path.exists():
        for line in failure_jsonl_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            failure_types[record.get("failure_type") or "unknown"] += 1

    aggregate_taxonomy = (
        (eval_report.get("aggregate") or {}).get("failure_taxonomy") or {}
    )
    return {
        "adapter_eval_case_count": (eval_report.get("meta") or {}).get("case_count"),
        "adapter_failure_taxonomy": aggregate_taxonomy,
        "top_eval_failure_types": [
            key
            for key, _ in sorted(
                failure_types.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:5]
        ],
        "eval_failure_counts": dict(failure_types),
    }


def discover_dataset_files(data_glob_dir: Path) -> list[Path]:
    files: list[Path] = []
    if data_glob_dir.exists():
        files.extend(sorted(data_glob_dir.glob("*.jsonl")))
    return files


def recommendation_text(decision: dict[str, Any], aggregate: dict[str, Any]) -> str:
    accepted = aggregate.get("tier_a_accepted", 0)
    if decision.get("ready_for_training"):
        return (
            f"Tier A has {accepted} samples and passes decision gate thresholds. "
            "Proceed to SFT v2 curriculum rebuild, then consider 0.6B smoke retrain."
        )
    if accepted >= 100:
        return (
            f"Tier A has {accepted} samples but decision gate blockers remain. "
            "Prioritize repair_candidates before any retrain."
        )
    return (
        f"Tier A has only {accepted} samples. Do not retrain yet; expand or repair data first."
    )