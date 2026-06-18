"""Tests for SFT v2 dataset builder."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
sys.path.insert(0, str(PROJECT_ROOT / "training"))

from build_sft_dataset import compact_json, format_chat_text  # noqa: E402
from build_sft_dataset_v2 import build_dataset_v2, build_v2_row  # noqa: E402
from sft_dataset_audit_lib import audit_training_row, load_cleaning_rules  # noqa: E402

RULES = load_cleaning_rules(PROJECT_ROOT / "training" / "data_cleaning_rules.yaml")


def _accepted_row(sample_id: str) -> dict:
    source = (
        "细菌性肺炎是由细菌感染引起的肺部炎症，表现为发热、咳嗽和咳痰。"
        "诊断结合症状、体征和影像学检查。治疗以经验性抗生素为主。"
        "并发症包括脓胸和呼吸衰竭。"
    )
    user_prompt = f"""章节路径：呼吸系统 > 细菌性肺炎
教材原文：
{source}
/no_think"""
    nodes = [
        {
            "title": "细菌性肺炎的定义",
            "type": "disease",
            "parent_entity": "细菌性肺炎",
            "aspect": "定义",
            "content": "细菌性肺炎是由细菌感染引起的肺部炎症",
            "evidence": "细菌性肺炎是由细菌感染引起的肺部炎症，表现为发热、咳嗽和咳痰。",
            "tags": [],
        },
        {
            "title": "细菌性肺炎的诊断",
            "type": "disease",
            "parent_entity": "细菌性肺炎",
            "aspect": "诊断",
            "content": "细菌性肺炎的诊断结合症状、体征和影像学检查",
            "evidence": "诊断结合症状、体征和影像学检查。",
            "tags": [],
        },
        {
            "title": "细菌性肺炎的治疗",
            "type": "treatment",
            "parent_entity": "细菌性肺炎",
            "aspect": "治疗",
            "content": "细菌性肺炎的治疗以经验性抗生素为主",
            "evidence": "治疗以经验性抗生素为主。",
            "tags": [],
        },
    ]
    edges = [
        {
            "source": "细菌性肺炎",
            "target": "脓胸",
            "relation": "complication_of",
        }
    ]
    return {
        "id": sample_id,
        "source_file": "test.jsonl",
        "chunk_id": "1",
        "text": format_chat_text(user_prompt, compact_json({"nodes": nodes, "edges": edges})),
    }


def test_build_v2_row_strips_edges_from_training_target() -> None:
    row = _accepted_row("accepted-1")
    audited = audit_training_row(row, rules=RULES, source_file="test.jsonl")
    v2_row = build_v2_row(row, audited=audited, rules=RULES)

    assert v2_row["edge_count"] == 0
    assert len(v2_row["optional_edges"]) == 1
    assert '"edges":[]' in v2_row["text"]
    assert "complication_of" not in v2_row["text"]
    assert v2_row["training_focus"] == "nodes"


def test_build_dataset_v2_outputs_manifest_and_files(tmp_path: Path) -> None:
    train_v1 = tmp_path / "sft_train.jsonl"
    golden = tmp_path / "golden.jsonl"
    output_dir = tmp_path / "sft_v2"

    rows = [_accepted_row("accepted-1"), _accepted_row("accepted-2")]
    train_v1.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in rows),
        encoding="utf-8",
    )
    golden.write_text(
        json.dumps(
            {
                "id": "golden-1",
                "golden_title": "测试",
                "text": rows[0]["text"],
                "expected": json.loads(
                    rows[0]["text"].split("<|im_start|>assistant\n", 1)[1].replace("<|im_end|>", "")
                ),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest = build_dataset_v2(
        train_v1_path=train_v1,
        golden_eval_path=golden,
        pipeline_dir=tmp_path / "missing_pipeline",
        output_dir=output_dir,
        rules_path=PROJECT_ROOT / "training" / "data_cleaning_rules.yaml",
        include_pipeline=False,
        eval_holdout_rate=0.5,
        seed=42,
    )

    assert manifest["version"] == "sft_v2"
    assert manifest["accepted_samples"] == 2
    assert manifest["train_samples"] == 1
    assert manifest["internal_eval_samples"] == 1
    assert manifest["golden_eval_samples"] == 1
    assert (output_dir / "train.jsonl").exists()
    assert (output_dir / "eval.jsonl").exists()
    assert (output_dir / "rejected.jsonl").exists()
    assert (output_dir / "repair_candidates.jsonl").exists()
    assert (output_dir / "manifest.json").exists()

    train_rows = [
        json.loads(line)
        for line in (output_dir / "train.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert train_rows[0]["optional_edges"]
    assert train_rows[0]["task"] == "pipeline_v3_extract_v2_nodes"