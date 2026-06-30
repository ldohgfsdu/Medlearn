"""Tests for evidence-copy curriculum construction."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from build_sft_dataset import compact_json, format_chat_text  # noqa: E402
from sft_curriculum_lib import (  # noqa: E402
    build_curriculum_row,
    build_stage1_assistant,
    build_stage2_assistant,
    build_stage3_assistant,
    parse_train_sample,
    validate_stage_row,
)
from sft_eval_metrics import extract_prompt_and_expected  # noqa: E402


def make_train_row() -> dict:
    source = (
        "【定义】2型糖尿病是胰岛素抵抗伴胰岛素分泌不足。"
        "【临床表现】临床表现为多饮、多尿、多食、体重下降。"
        "【诊断】诊断标准为空腹血糖≥7.0mmol/L或餐后2h血糖≥11.1mmol/L。"
        "【治疗】治疗包括生活方式干预、口服降糖药、胰岛素。"
    )
    nodes = [
        {
            "title": "2型糖尿病的定义",
            "type": "disease",
            "parent_entity": "2型糖尿病",
            "aspect": "定义",
            "content": "2型糖尿病的定义：2型糖尿病是胰岛素抵抗伴胰岛素分泌不足",
            "evidence": "2型糖尿病是胰岛素抵抗伴胰岛素分泌不足。",
            "tags": [],
        },
        {
            "title": "2型糖尿病的临床表现",
            "type": "symptom",
            "parent_entity": "2型糖尿病",
            "aspect": "临床表现",
            "content": "2型糖尿病的临床表现：临床表现为多饮、多尿、多食、体重下降",
            "evidence": "临床表现为多饮、多尿、多食、体重下降。",
            "tags": [],
        },
        {
            "title": "2型糖尿病的诊断",
            "type": "exam",
            "parent_entity": "2型糖尿病",
            "aspect": "诊断",
            "content": "2型糖尿病的诊断：诊断标准为空腹血糖≥7.0mmol/L或餐后2h血糖≥11.1mmol/L",
            "evidence": "诊断标准为空腹血糖≥7.0mmol/L或餐后2h血糖≥11.1mmol/L。",
            "tags": [],
        },
        {
            "title": "2型糖尿病的治疗",
            "type": "treatment",
            "parent_entity": "2型糖尿病",
            "aspect": "治疗",
            "content": "2型糖尿病的治疗：治疗包括生活方式干预、口服降糖药、胰岛素",
            "evidence": "治疗包括生活方式干预、口服降糖药、胰岛素。",
            "tags": [],
        },
    ]
    user_prompt = f"""章节路径：内分泌 > 2型糖尿病
教材原文：
{source}
/no_think"""
    return {
        "id": "curriculum-test::1",
        "chapter_path": "内分泌 > 2型糖尿病",
        "generation_method": "source_segmentation",
        "text": format_chat_text(user_prompt, compact_json({"nodes": nodes, "edges": []})),
        "optional_edges": [{"source": "A", "target": "B", "relation": "causes"}],
    }


def test_stage1_has_aspect_evidence_only() -> None:
    row = make_train_row()
    parsed = parse_train_sample(row)
    payload = build_stage1_assistant(parsed["nodes"])
    assert len(payload["nodes"]) == 4
    assert set(payload["nodes"][0]) == {"aspect", "evidence"}
    issues = validate_stage_row("stage1_evidence_copy", source_text=parsed["source_text"], assistant_payload=payload)
    assert issues == []


def test_stage2_requires_content_distill() -> None:
    row = make_train_row()
    parsed = parse_train_sample(row)
    payload = build_stage2_assistant(parsed["nodes"])
    assert all("content" in node for node in payload["nodes"])
    issues = validate_stage_row(
        "stage2_evidence_content_distill",
        source_text=parsed["source_text"],
        assistant_payload=payload,
    )
    assert issues == []


def test_stage3_nodes_only_edges_empty() -> None:
    row = make_train_row()
    parsed = parse_train_sample(row)
    payload = build_stage3_assistant(parsed["nodes"], optional_edges=row["optional_edges"])
    assert payload["edges"] == []
    assert len(payload["nodes"]) == 4
    assert "optional_edges" in payload
    issues = validate_stage_row(
        "stage3_full_nodes_only",
        source_text=parsed["source_text"],
        assistant_payload=payload,
    )
    assert issues == []


def test_build_all_curriculum_stages() -> None:
    row = make_train_row()
    parsed = parse_train_sample(row)
    for stage in (
        "stage1_evidence_copy",
        "stage2_evidence_content_distill",
        "stage3_full_nodes_only",
    ):
        built = build_curriculum_row(parsed, stage=stage, stage_index=1)
        assert built is not None
        assert built["stage"] == stage
        _, expected = extract_prompt_and_expected(built)
        assert expected is not None
        assert len(expected.get("nodes") or []) >= 3