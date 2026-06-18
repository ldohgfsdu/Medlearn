"""Tests for SFT dataset audit and classification."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from build_sft_dataset import compact_json, format_chat_text  # noqa: E402
from sft_dataset_audit_lib import (  # noqa: E402
    audit_training_row,
    classify_tier,
    collect_sample_issues,
    load_cleaning_rules,
    summarize_audit_results,
)

RULES = load_cleaning_rules(PROJECT_ROOT / "training" / "data_cleaning_rules.yaml")


def make_row(source_text: str, nodes: list[dict], edges: list | None = None) -> dict:
    user_prompt = f"""章节路径：测试 > 高血压
教材原文：
{source_text}
/no_think"""
    payload = {"nodes": nodes, "edges": edges or []}
    return {
        "id": "test-sample",
        "text": format_chat_text(user_prompt, compact_json(payload)),
    }


def test_hard_reject_evidence_not_in_source() -> None:
    row = make_row(
        "高血压的诊断包括诊室血压测量。",
        [
            {
                "title": "高血压的诊断",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "诊断",
                "content": "高血压的诊断依赖诊室血压测量",
                "evidence": "这是原文中没有的概括句",
                "tags": [],
            }
        ],
    )
    result = audit_training_row(row, rules=RULES, source_file="test.jsonl")
    assert result["tier"] == "C"
    assert "evidence_not_in_source" in result["hard_reject_reasons"]


def test_soft_repair_content_equals_evidence() -> None:
    source = (
        "高血压的诊断包括诊室血压测量。"
        "高血压的治疗包括生活方式干预和药物治疗。"
        "高血压需要长期随访管理。"
    )
    row = make_row(
        source,
        [
            {
                "title": "高血压的诊断",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "诊断",
                "content": "高血压的诊断包括诊室血压测量。",
                "evidence": "高血压的诊断包括诊室血压测量。",
                "tags": [],
            },
            {
                "title": "高血压的治疗",
                "type": "treatment",
                "parent_entity": "高血压",
                "aspect": "治疗",
                "content": "高血压的治疗包括生活方式干预和药物治疗",
                "evidence": "高血压的治疗包括生活方式干预和药物治疗",
                "tags": [],
            },
            {
                "title": "高血压的预后",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "预后",
                "content": "高血压需要长期随访管理",
                "evidence": "高血压需要长期随访管理",
                "tags": [],
            },
        ],
    )
    result = audit_training_row(row, rules=RULES, source_file="test.jsonl")
    assert result["tier"] == "B"
    assert "content_equals_evidence" in result["soft_repair_reasons"]


def test_soft_repair_single_summary_node() -> None:
    row = make_row(
        "2型糖尿病是胰岛素抵抗伴胰岛素分泌不足。",
        [
            {
                "title": "2型糖尿病的定义",
                "type": "disease",
                "parent_entity": "2型糖尿病",
                "aspect": "定义",
                "content": "2型糖尿病的定义是胰岛素抵抗伴胰岛素分泌不足",
                "evidence": "2型糖尿病是胰岛素抵抗伴胰岛素分泌不足。",
                "tags": [],
            }
        ],
    )
    result = audit_training_row(row, rules=RULES, source_file="test.jsonl")
    assert result["tier"] == "B"
    assert "single_summary_node" in result["soft_repair_reasons"]


def test_accepted_sample_tier_a() -> None:
    source = (
        "高血压是以体循环动脉压升高为主要表现的临床综合征。"
        "诊断依赖诊室血压测量。治疗包括生活方式干预和降压药物治疗。"
        "长期管理可降低心脑血管并发症风险。"
    )
    row = make_row(
        source,
        [
            {
                "title": "高血压的定义",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "定义",
                "content": "高血压是以体循环动脉压升高为主要表现的临床综合征",
                "evidence": "高血压是以体循环动脉压升高为主要表现的临床综合征。",
                "tags": [],
            },
            {
                "title": "高血压的诊断",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "诊断",
                "content": "高血压的诊断依赖诊室血压测量",
                "evidence": "诊断依赖诊室血压测量。",
                "tags": [],
            },
            {
                "title": "高血压的治疗",
                "type": "treatment",
                "parent_entity": "高血压",
                "aspect": "治疗",
                "content": "高血压的治疗包括生活方式干预和降压药物治疗",
                "evidence": "治疗包括生活方式干预和降压药物治疗。",
                "tags": [],
            },
        ],
    )
    result = audit_training_row(row, rules=RULES, source_file="test.jsonl")
    assert result["tier"] == "A"
    assert result["evidence_exact_match_rate"] == 1.0
    assert result["content_equals_evidence_rate"] == 0.0


def test_missing_aspect_is_soft_repair() -> None:
    issues, _, _ = collect_sample_issues(
        source_text="高血压需要长期随访。",
        chapter_path="测试 > 高血压",
        payload={
            "nodes": [
                {
                    "title": "高血压随访",
                    "type": "disease",
                    "parent_entity": "高血压",
                    "aspect": "",
                    "content": "高血压需要长期随访管理",
                    "evidence": "高血压需要长期随访。",
                    "tags": [],
                }
            ]
            * 3,
            "edges": [],
        },
        rules=RULES,
    )
    assert "missing_aspect" in issues
    assert classify_tier(issues, {"node_count": 3}, RULES) == "B"


def test_summarize_audit_results() -> None:
    summary = summarize_audit_results(
        [
            {"tier": "A", "node_count": 4, "issues": [], "evidence_exact_match_rate": 1.0,
             "content_equals_evidence_rate": 0.0, "unique_aspect_count": 4},
            {"tier": "B", "node_count": 1, "issues": ["single_summary_node"],
             "evidence_exact_match_rate": 1.0, "content_equals_evidence_rate": 1.0,
             "unique_aspect_count": 1},
            {"tier": "C", "node_count": 2, "issues": ["evidence_not_in_source"],
             "evidence_exact_match_rate": 0.5, "content_equals_evidence_rate": 0.0,
             "unique_aspect_count": 2},
        ]
    )
    assert summary["tier_a_accepted"] == 1
    assert summary["tier_b_repair"] == 1
    assert summary["tier_c_rejected"] == 1
    assert summary["acceptance_rate"] == pytest.approx(1 / 3, rel=1e-3)


def test_rules_file_exists() -> None:
    rules_path = PROJECT_ROOT / "training" / "data_cleaning_rules.yaml"
    rules = load_cleaning_rules(rules_path)
    assert rules["version"] == "sft_data_cleaning_v2"
    assert "evidence_not_in_source" in rules["hard_reject"]
    assert "content_equals_evidence" in rules["soft_repair"]