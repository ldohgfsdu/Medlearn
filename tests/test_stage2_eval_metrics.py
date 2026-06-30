"""Tests for Stage 2 evidence + content evaluation metrics."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from sft_eval_metrics import GeneratedCase  # noqa: E402
from stage2_eval_metrics import (  # noqa: E402
    content_grounded_in_evidence,
    evaluate_stage2_case,
    evaluate_stage2_gates,
)


def test_stage2_case_passes_with_distinct_content() -> None:
    source = "【治疗】治疗包括生活方式干预和降压药物治疗。"
    case = GeneratedCase(
        case_id="t2",
        suite="test",
        source_text=source,
        expected={
            "nodes": [
                {
                    "aspect": "治疗",
                    "evidence": "治疗包括生活方式干预和降压药物治疗。",
                    "content": "高血压的治疗：治疗包括生活方式干预和降压药物治疗",
                }
            ]
        },
        generated={
            "nodes": [
                {
                    "aspect": "治疗",
                    "evidence": "治疗包括生活方式干预和降压药物治疗。",
                    "content": "高血压的治疗：治疗包括生活方式干预",
                }
            ],
            "edges": [],
        },
        raw_text="",
        json_valid=True,
    )
    result = evaluate_stage2_case(case)
    assert result["evidence_exact_match_rate"] == 1.0
    assert result["content_equals_evidence_rate"] == 0.0
    assert result["content_missing_rate"] == 0.0


def test_content_grounded_detects_body_in_evidence() -> None:
    evidence = "治疗包括生活方式干预和降压药物治疗。"
    content = "高血压的治疗：治疗包括生活方式干预"
    assert content_grounded_in_evidence(content, evidence, evidence) is True


def test_stage2_minimum_gates() -> None:
    aggregate = {
        "json_valid_rate": 0.96,
        "evidence_exact_match_rate": 0.92,
        "content_equals_evidence_rate": 0.05,
        "content_missing_rate": 0.02,
        "avg_nodes_per_sample": 3.6,
        "content_grounded_in_evidence_rate": 0.88,
    }
    gates = evaluate_stage2_gates(aggregate)
    assert gates["minimum_passed"] is True