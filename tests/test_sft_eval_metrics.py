"""Unit tests for deterministic SFT evaluation metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from sft_eval_metrics import (  # noqa: E402
    GeneratedCase,
    aspect_key,
    build_diagnosis,
    evaluate_case,
    evidence_overlap_score,
    extract_source_text,
    label_similarity,
    match_nodes,
    parse_generated,
    summarize_cases,
)


def test_extract_source_text_from_prompt() -> None:
    prompt = (
        "<|im_start|>user\n章节路径：测试\n教材原文：\n"
        "社区获得性肺炎是医院外获得的肺炎感染。\n/no_think<|im_end|>\n"
    )
    assert extract_source_text(prompt) == "社区获得性肺炎是医院外获得的肺炎感染。"


def test_parse_generated_json() -> None:
    payload, raw = parse_generated('{"nodes":[{"title":"A"}],"edges":[]}')
    assert payload is not None
    assert payload["nodes"][0]["title"] == "A"
    assert raw.startswith("{")


def test_label_similarity_and_evidence_overlap() -> None:
    assert label_similarity("高血压的治疗", "高血压的治疗") == 1.0
    assert evidence_overlap_score("药物治疗", "高血压的治疗包括药物治疗和生活方式干预") == 1.0


def test_match_nodes_heuristic() -> None:
    expected = [
        {
            "title": "高血压的治疗",
            "parent_entity": "高血压",
            "aspect": "治疗",
            "evidence": "降压治疗包括生活方式干预和药物治疗",
        }
    ]
    generated = [
        {
            "title": "高血压的治疗",
            "parent_entity": "高血压",
            "aspect": "治疗",
            "evidence": "降压治疗包括生活方式干预和药物治疗",
        }
    ]
    result = match_nodes(expected, generated)
    assert result["node_f1"] == 1.0
    assert len(result["matched_pairs"]) == 1


def test_evaluate_case_flags_evidence_and_single_node_collapse() -> None:
    case = GeneratedCase(
        case_id="case-1",
        suite="holdout_3",
        source_text="非小细胞肺癌（NSCLC）是肺癌中最常见的类型，约占肺癌总发病率的85%。",
        expected={
            "nodes": [
                {"title": "定义", "parent_entity": "非小细胞肺癌", "aspect": "定义"},
                {"title": "流行病学", "parent_entity": "非小细胞肺癌", "aspect": "流行病学"},
                {"title": "治疗", "parent_entity": "非小细胞肺癌", "aspect": "治疗"},
            ],
            "edges": [],
        },
        generated={
            "nodes": [
                {
                    "title": "非小细胞肺癌的定义",
                    "type": "disease",
                    "parent_entity": "非小细胞肺癌",
                    "aspect": "定义",
                    "content": "非小细胞肺癌是最常见肺癌类型",
                    "evidence": "非小细胞肺癌是最常见肺癌类型",
                    "tags": [],
                }
            ],
            "edges": [],
        },
        raw_text="{}",
        json_valid=True,
    )
    result = evaluate_case(case)
    assert result["node_count_recall"] == pytest.approx(1 / 3, rel=1e-3)
    assert result["failure_taxonomy"]["single_summary_node"] == 1
    assert result["failure_taxonomy"]["content_equals_evidence"] == 1
    assert result["failure_taxonomy"]["evidence_not_in_source"] == 1


def test_summarize_cases_and_diagnosis() -> None:
    cases = [
        {
            "json_valid": True,
            "has_nodes": True,
            "has_edges": True,
            "required_fields_complete_rate": 1.0,
            "expected_node_count": 4,
            "actual_node_count": 1,
            "node_count_recall": 0.25,
            "aspect_coverage_rate": 0.25,
            "evidence_exact_match_rate": 0.0,
            "evidence_missing_rate": 0.0,
            "evidence_rewritten_rate": 1.0,
            "content_equals_evidence_rate": 1.0,
            "node_precision": 0.25,
            "node_recall": 0.25,
            "node_f1": 0.25,
            "failure_taxonomy": {
                "single_summary_node": 1,
                "evidence_not_in_source": 1,
                "content_equals_evidence": 1,
            },
        }
    ]
    aggregate = summarize_cases(cases)
    assert aggregate["json_valid_rate"] == 1.0
    assert aggregate["node_count_recall_mean"] == 0.25
    diagnosis = build_diagnosis(aggregate)
    assert "JSON envelope is stable" in diagnosis
    assert "Node recall is the primary bottleneck" in diagnosis


def test_aspect_key_maps_english_golden_aspects() -> None:
    assert aspect_key({"parent_entity": "社区获得性肺炎", "aspect": "definition"}) == (
        "社区获得性肺炎",
        "定义",
    )
    assert aspect_key({"parent_entity": "社区获得性肺炎", "aspect": "诊断"}) == (
        "社区获得性肺炎",
        "诊断",
    )


def test_golden_rows_have_parseable_expected() -> None:
    golden_path = PROJECT_ROOT / "training" / "sft_smoke_eval.jsonl"
    rows = [
        json.loads(line)
        for line in golden_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 8
    for row in rows:
        assert row.get("expected")
        assert extract_source_text(row["text"])