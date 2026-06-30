"""Tests for Stage 1 evidence-copy evaluation metrics."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from sft_eval_metrics import GeneratedCase  # noqa: E402
from stage1_eval_metrics import (  # noqa: E402
    evaluate_stage1_case,
    evaluate_stage1_gates,
    summarize_stage1_cases,
)


def test_stage1_case_counts_exact_evidence() -> None:
    case = GeneratedCase(
        case_id="t1",
        suite="test",
        source_text="【治疗】治疗包括生活方式干预和降压药物治疗。",
        expected={
            "nodes": [
                {"aspect": "治疗", "evidence": "治疗包括生活方式干预和降压药物治疗。"},
            ]
        },
        generated={
            "nodes": [
                {"aspect": "治疗", "evidence": "治疗包括生活方式干预和降压药物治疗。"},
            ],
            "edges": [],
        },
        raw_text="",
        json_valid=True,
    )
    result = evaluate_stage1_case(case)
    assert result["json_valid"] is True
    assert result["evidence_exact_match_rate"] == 1.0
    assert result["empty_nodes"] is False


def test_stage1_gates_minimum_pass() -> None:
    aggregate = {
        "json_valid_rate": 0.96,
        "evidence_exact_match_rate": 0.92,
        "empty_nodes_rate": 0.0,
        "avg_nodes_per_sample": 3.5,
        "evidence_rewritten_rate": 0.08,
    }
    gates = evaluate_stage1_gates(aggregate)
    assert gates["minimum_passed"] is True


def test_summarize_stage1_cases() -> None:
    rows = [
        {
            "json_valid": True,
            "has_nodes": True,
            "empty_nodes": False,
            "actual_node_count": 4,
            "evidence_exact_match_rate": 1.0,
            "evidence_rewritten_rate": 0.0,
            "aspect_coverage_rate": 0.8,
            "single_summary_node": False,
        },
        {
            "json_valid": True,
            "has_nodes": True,
            "empty_nodes": False,
            "actual_node_count": 3,
            "evidence_exact_match_rate": 0.5,
            "evidence_rewritten_rate": 0.5,
            "aspect_coverage_rate": 0.6,
            "single_summary_node": False,
        },
    ]
    summary = summarize_stage1_cases(rows)
    assert summary["case_count"] == 2
    assert summary["json_valid_rate"] == 1.0
    assert summary["evidence_exact_match_rate"] == 0.75