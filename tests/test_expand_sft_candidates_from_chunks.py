"""Tests for SFT dataset expansion from pipeline chunks."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from build_sft_dataset import build_user_prompt, clean_source_text, compact_json, format_chat_text  # noqa: E402
from sft_candidate_generation_lib import (  # noqa: E402
    audit_manual_review_row,
    generate_candidate_payload,
    hydrate_chunk_source_text,
    source_suitability,
    triage_unrepaired_row,
)
from sft_dataset_audit_lib import audit_training_row, load_cleaning_rules  # noqa: E402

RULES = load_cleaning_rules(PROJECT_ROOT / "training" / "data_cleaning_rules.yaml")


def test_generate_candidate_from_rich_source() -> None:
    source = (
        "【定义】高血压是以体循环动脉压升高为主要表现的临床综合征。"
        "【诊断】诊断依赖诊室血压测量和动态血压监测。"
        "【治疗】治疗包括生活方式干预和降压药物治疗。"
        "【预后】长期管理可降低心脑血管并发症风险。"
    )
    sample = {
        "source_file": "generated/pipeline_v3/test.extraction.json",
        "chunk_id": "1",
        "headings": ["第二篇 循环系统疾病", "高血压"],
        "content": source,
        "nodes": [],
        "edges": [],
    }
    payload, meta = generate_candidate_payload(sample, min_nodes=3)
    assert payload is not None
    assert len(payload["nodes"]) >= 3
    assert meta["suitability"]["unique_aspect_count"] >= 3


def test_table_heavy_source_rejected() -> None:
    source = "|A|B|" * 40 + "\n|---|---|\n" + "|1|2|\n" * 20
    suitability = source_suitability(source)
    assert suitability["table_heavy"] is True
    payload, meta = generate_candidate_payload(
        {
            "source_file": "t.extraction.json",
            "chunk_id": "1",
            "headings": ["测试"],
            "content": source,
            "nodes": [],
            "edges": [],
        }
    )
    assert payload is None
    assert meta["reject_reason"] == "table_heavy_low_aspect_signal"


def test_manual_review_truncation_audit() -> None:
    full_source = "【定义】肺结核是严重危害人类健康的传染病。" * 3 + "【治疗】治疗以抗结核药物为主。"
    short_source = "【定义】肺结核是严重危害人类健康的传染病。"
    user_prompt = build_user_prompt(["呼吸系统", "肺结核"], short_source)
    row = {
        "id": "generated\\pipeline_v3\\test.extraction.json::8",
        "text": format_chat_text(user_prompt, compact_json({"nodes": [], "edges": []})),
        "audit_issues": ["empty_nodes"],
        "node_count": 0,
    }
    chunk_index = {
        "generated\\pipeline_v3\\test.extraction.json::8": {
            "source_file": "generated\\pipeline_v3\\test.extraction.json",
            "chunk_id": "8",
            "headings": ["呼吸系统", "肺结核"],
            "content": full_source,
            "nodes": [],
            "edges": [],
        }
    }
    audit = audit_manual_review_row(row, chunk_index)
    assert audit["recoverable_truncation"] is True
    assert audit["disposition"] == "rescuable_truncation"


def test_unrepaired_triage_buckets() -> None:
    rich_source = (
        "【定义】细菌性肺炎是由细菌感染引起的肺部炎症。"
        "【诊断】诊断结合症状、体征和影像学检查。"
        "【治疗】治疗以经验性抗生素为主。"
        "【预后】并发症包括脓胸和呼吸衰竭。"
    )
    chunk_index = {
        "sample-1": {
            "source_file": "t.extraction.json",
            "chunk_id": "1",
            "headings": ["呼吸系统", "细菌性肺炎"],
            "content": rich_source,
            "nodes": [],
            "edges": [],
        }
    }
    row = {
        "id": "sample-1",
        "audit_issues": ["content_equals_evidence", "aspect_imbalance"],
        "node_count": 2,
        "text": "placeholder",
    }
    triage = triage_unrepaired_row(row, chunk_index)
    assert triage["triage_bucket"] in {"B1_deterministic_repair", "B2_reextract_from_chunk"}

    poor_row = {
        "id": "sample-2",
        "audit_issues": ["single_summary_node"],
        "node_count": 1,
        "text": format_chat_text(
            build_user_prompt(["测试"], "只有一句话。"),
            compact_json({"nodes": [], "edges": []}),
        ),
    }
    poor_triage = triage_unrepaired_row(poor_row, {})
    assert poor_triage["triage_bucket"] == "B3_discard"


def test_hydrate_empty_content_from_node_evidence() -> None:
    sample = {
        "content": "",
        "nodes": [
            {
                "parent_entity": "高血压",
                "aspect": "定义",
                "content": "高血压是以体循环动脉压升高为主要表现的临床综合征。",
                "evidence": "【定义】高血压是以体循环动脉压升高为主要表现的临床综合征。",
            },
            {
                "parent_entity": "高血压",
                "aspect": "诊断",
                "content": "诊断依赖诊室血压测量。",
                "evidence": "【诊断】诊断依赖诊室血压测量和动态血压监测。",
            },
            {
                "parent_entity": "高血压",
                "aspect": "治疗",
                "content": "治疗包括生活方式干预。",
                "evidence": "【治疗】治疗包括生活方式干预和降压药物治疗。",
            },
        ],
        "edges": [],
    }
    source_text, method = hydrate_chunk_source_text(sample)
    assert method == "node_evidence_hydration"
    assert "【定义】" in source_text
    assert "【治疗】" in source_text


def test_generated_row_passes_tier_a_audit() -> None:
    source = (
        "【定义】2型糖尿病是胰岛素抵抗伴胰岛素分泌不足。"
        "【临床表现】临床表现为多饮、多尿、多食、体重下降。"
        "【诊断】诊断标准为空腹血糖≥7.0mmol/L或餐后2h血糖≥11.1mmol/L。"
        "【治疗】治疗包括生活方式干预、口服降糖药、胰岛素。"
    )
    sample = {
        "source_file": "generated/pipeline_v3/dm.extraction.json",
        "chunk_id": "1",
        "headings": ["内分泌", "2型糖尿病"],
        "content": source,
        "nodes": [],
        "edges": [],
    }
    from sft_candidate_generation_lib import chunk_sample_to_row

    payload, _ = generate_candidate_payload(sample, min_nodes=3)
    assert payload is not None
    row = chunk_sample_to_row(sample, payload)
    audit = audit_training_row(row, rules=RULES, source_file="test")
    assert audit["tier"] == "A"
    assert audit["evidence_exact_match_rate"] == 1.0
    assert audit["content_equals_evidence_rate"] == 0.0