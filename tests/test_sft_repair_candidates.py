"""Tests for SFT repair candidate logic."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from build_sft_dataset import compact_json, format_chat_text  # noqa: E402
from repair_sft_candidates import repair_one_row  # noqa: E402
from sft_dataset_audit_lib import audit_training_row, load_cleaning_rules  # noqa: E402
from sft_repair_lib import (  # noqa: E402
    build_best_node_for_aspect_bucket,
    classify_text_aspect,
    content_grounded_in_evidence,
    distill_content,
    normalize_node,
    repair_payload,
    r2_fix_content_equals_evidence,
    r3_split_by_source_segmentation,
)

RULES = load_cleaning_rules(PROJECT_ROOT / "training" / "data_cleaning_rules.yaml")


def make_row(source_text: str, nodes: list[dict], chapter_path: str = "测试 > 高血压") -> dict:
    user_prompt = f"""章节路径：{chapter_path}
教材原文：
{source_text}
/no_think"""
    payload = {"nodes": nodes, "edges": []}
    return {
        "id": "test-repair",
        "text": format_chat_text(user_prompt, compact_json(payload)),
    }


def test_distill_content_differs_from_evidence() -> None:
    evidence = "高血压的诊断包括诊室血压测量和动态血压监测。"
    content = distill_content("高血压", "诊断", evidence)
    assert content != evidence
    assert "高血压" in content
    assert "诊断" in content


def test_distill_content_long_evidence_stays_grounded() -> None:
    evidence = (
        "（2） 适用人群：未接受或接受短程治疗方案中的二线药物不超过1 个月，"
        "并且对氟喹诺酮类和二线注射剂敏感的利福平耐药病人，"
        "同时排除以下病人：①对短程方案中的任何药物不能耐受或存在药物毒性风险；"
    )
    content = distill_content("肺结核", "预防", evidence)
    assert content != evidence
    assert content_grounded_in_evidence(content, evidence, "肺结核", "预防")


def test_build_best_node_tries_later_sentences_in_bucket() -> None:
    sentences = [
        "（一） 手术治疗 是早期肺癌的最佳治疗方法，应当力争根治性切除。",
        "术后根据病人最终病理TNM 分期、切缘情况，选择辅助化疗或放疗。",
    ]
    node = build_best_node_for_aspect_bucket(
        "治疗",
        sentences,
        parent_entity="肺癌",
        source_text=" ".join(sentences),
    )
    assert node is not None
    assert node["aspect"] == "治疗"


def test_r2_preserves_evidence_when_in_source() -> None:
    evidence = "高血压的诊断包括诊室血压测量。"
    source = evidence + "治疗包括生活方式干预。"
    payload = {
        "nodes": [
            {
                "title": "高血压的诊断",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "诊断",
                "content": evidence,
                "evidence": evidence,
                "tags": [],
            }
        ],
        "edges": [],
    }
    repaired, actions = r2_fix_content_equals_evidence(
        payload,
        source_text=source,
        chapter_path="测试 > 高血压",
    )
    node = repaired["nodes"][0]
    assert node["evidence"] == evidence
    assert node["content"] != node["evidence"]
    assert "rewrite_content_not_evidence" in actions


def test_aspect_missing_filled_by_keywords() -> None:
    source = "肺结核的流行病学数据显示发病率持续下降。"
    node = normalize_node(
        {
            "title": "肺结核",
            "type": "disease",
            "parent_entity": "肺结核",
            "aspect": "",
            "content": "肺结核的流行病学数据显示发病率持续下降",
            "evidence": "肺结核的流行病学数据显示发病率持续下降。",
            "tags": [],
        },
        parent_entity="肺结核",
        source_text=source,
        chapter_path="呼吸系统 > 肺结核",
    )
    assert node is not None
    assert node["aspect"] == "流行病学"


def test_r3_splits_single_summary_into_multiple_nodes() -> None:
    source = (
        "【定义】高血压是以体循环动脉压升高为主要表现的临床综合征。"
        "【诊断】诊断依赖诊室血压测量。"
        "【治疗】治疗包括生活方式干预和降压药物。"
    )
    payload = {
        "nodes": [
            {
                "title": "高血压概述",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "概述",
                "content": source,
                "evidence": source,
                "tags": [],
            }
        ],
        "edges": [],
    }
    repaired, actions = r3_split_by_source_segmentation(
        payload,
        source_text=source,
        chapter_path="测试 > 高血压",
        min_nodes=3,
    )
    assert "r3" in actions[0]
    assert len(repaired["nodes"]) >= 3
    for node in repaired["nodes"]:
        assert node["aspect"]
        assert node["content"] != node["evidence"]


def test_evidence_not_in_source_not_faked() -> None:
    source = "高血压的诊断包括诊室血压测量。"
    payload = {
        "nodes": [
            {
                "title": "高血压的治疗",
                "type": "treatment",
                "parent_entity": "高血压",
                "aspect": "治疗",
                "content": "高血压的治疗包括手术治疗",
                "evidence": "高血压的治疗包括手术治疗",
                "tags": [],
            }
        ],
        "edges": [],
    }
    repaired, _ = repair_payload(
        payload,
        source_text=source,
        chapter_path="测试 > 高血压",
    )
    assert repaired["nodes"] == []


def test_repair_failure_goes_manual_review() -> None:
    row = make_row(
        "高血压的诊断包括诊室血压测量。",
        [
            {
                "title": "高血压的治疗",
                "type": "treatment",
                "parent_entity": "高血压",
                "aspect": "治疗",
                "content": "高血压的治疗包括手术治疗",
                "evidence": "高血压的治疗包括手术治疗",
                "tags": [],
            }
        ],
    )
    outcome = repair_one_row(row, rules=RULES, min_nodes=3)
    assert outcome["status"] in {"manual_review", "unrepaired"}
    assert outcome["diff"]["sample_id"] == "test-repair"


def test_repair_promotes_content_equals_sample() -> None:
    source = (
        "高血压是以体循环动脉压升高为主要表现的临床综合征。"
        "诊断依赖诊室血压测量。"
        "治疗包括生活方式干预和降压药物。"
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
                "content": "高血压是以体循环动脉压升高为主要表现的临床综合征。",
                "evidence": "高血压是以体循环动脉压升高为主要表现的临床综合征。",
                "tags": [],
            },
            {
                "title": "高血压的诊断",
                "type": "disease",
                "parent_entity": "高血压",
                "aspect": "诊断",
                "content": "诊断依赖诊室血压测量。",
                "evidence": "诊断依赖诊室血压测量。",
                "tags": [],
            },
            {
                "title": "高血压的治疗",
                "type": "treatment",
                "parent_entity": "高血压",
                "aspect": "治疗",
                "content": "治疗包括生活方式干预和降压药物。",
                "evidence": "治疗包括生活方式干预和降压药物。",
                "tags": [],
            },
        ],
    )
    before = audit_training_row(row, rules=RULES, source_file="test")
    assert "content_equals_evidence" in before["issues"]

    outcome = repair_one_row(row, rules=RULES, min_nodes=3)
    after = outcome["after_audit"]
    assert after["content_equals_evidence_rate"] == 0.0
    assert outcome["diff"]["tier_before"] == "B"
    assert outcome["after_audit"]["content_equals_evidence_rate"] == 0.0


def test_classify_text_aspect_for_diagnosis_marker() -> None:
    assert classify_text_aspect("【诊断】根据症状和体征可初步诊断") == "诊断"