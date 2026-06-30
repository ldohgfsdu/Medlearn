#!/usr/bin/env python
"""Build gated SFT dataset for pipeline_v3_extract only.

Outputs:
  training/sft_train.jsonl
  training/sft_smoke_eval.jsonl   # golden 8, frozen smoke eval
  training/rejected_samples.jsonl
  training/data_quality_report.json

Does NOT train. Does NOT export to Ollama.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pipeline_v3_extract import ALLOWED_TYPES  # noqa: F401 — keep import parity
from sft_quality_gates import (
    ALLOWED_EDGE_RELATIONS,
    validate_extraction_payload,
    validate_node_grounding,
    validate_node_schema,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PIPELINE_DIR = PROJECT_ROOT / "generated" / "pipeline_v3"
DEFAULT_GOLDEN = PROJECT_ROOT / "golden_dataset" / "mini_golden_set.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "training"

SYSTEM_PROMPT = (
    "你是 Medlearn 医学教材知识抽取模型。严格依据输入原文回答，不补充原文未提供的医学事实。\n"
    "需要结构化输出时，只返回符合要求的 JSON，不要添加 Markdown 代码块或额外解释。\n"
    "/no_think"
)

MAX_NODES_PER_CHUNK = 12
PAGE_MARKER_RE = re.compile(r"<!--\s*PDF page \d+\s*-->")


def clean_source_text(text: str) -> str:
    text = PAGE_MARKER_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def build_user_prompt(headings: list[str], content: str) -> str:
    path = " > ".join(filter(None, headings)) or "未识别"
    trimmed = content[:6000]
    return f"""你是医学教材“原子知识块”抽取器。仅根据给定原文抽取，不补充原文外事实。

要求：
1. nodes.type 只能是 concept、mechanism、disease、symptom、treatment、exam。
2. 每个节点代表 parent_entity 的一个知识面向；疾病章节中 parent_entity 必须是章节疾病或明确疾病亚型。
3. title 建议写“parent_entity + 的 + aspect”；content 首句必须写出 parent_entity 全称，不能用“该病、其、上述”。
4. aspect 填原文面向；evidence 必须是原文中的连续片段，禁止改写或编造。
5. 只抽取当前章节主体相关内容。
6. 同一个 parent_entity + aspect 只能输出一个 node。
7. 最多输出 {MAX_NODES_PER_CHUNK} 个 nodes。
8. edges.relation 用 causes、characteristic_of、treated_by、complication_of、associated_with。
9. 只输出合法 JSON，不要输出空 nodes。

JSON 格式：
{{
  "nodes": [{{"title": "主体的知识面向", "type": "disease", "parent_entity": "主体名", "aspect": "面向", "content": "含主体的结论", "evidence": "原文片段", "tags": []}}],
  "edges": [{{"source": "节点A", "target": "节点B", "relation": "causes"}}]
}}

章节路径：{path}
教材原文：
{trimmed}
/no_think"""


def format_chat_text(user_prompt: str, assistant_json: str) -> str:
    return (
        f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
        f"<|im_start|>user\n{user_prompt}<|im_end|>\n"
        f"<|im_start|>assistant\n{assistant_json}<|im_end|>"
    )


def compact_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def salvage_valid_payload(
    payload: dict[str, Any],
    source_text: str,
) -> dict[str, Any] | None:
    """Keep independently valid nodes and only fully resolved edges."""
    valid_nodes: list[dict[str, Any]] = []
    seen_aspects: set[tuple[str, str]] = set()

    for node in payload.get("nodes") or []:
        schema_ok, _ = validate_node_schema(node)
        if not schema_ok:
            continue
        grounding_ok, _ = validate_node_grounding(node, source_text)
        if not grounding_ok:
            continue
        key = (
            str(node.get("parent_entity") or "").strip(),
            str(node.get("aspect") or "").strip(),
        )
        if key in seen_aspects:
            continue
        seen_aspects.add(key)
        valid_nodes.append(node)
        if len(valid_nodes) >= MAX_NODES_PER_CHUNK:
            break

    if not valid_nodes:
        return None

    identifiers = {
        str(value).strip()
        for node in valid_nodes
        for value in (node.get("title"), node.get("parent_entity"))
        if str(value or "").strip()
    }
    valid_edges: list[dict[str, str]] = []
    for edge in payload.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        source = str(edge.get("source") or "").strip()
        target = str(edge.get("target") or "").strip()
        relation = str(edge.get("relation") or "").strip()
        if (
            source in identifiers
            and target in identifiers
            and relation in ALLOWED_EDGE_RELATIONS
        ):
            valid_edges.append(
                {"source": source, "target": target, "relation": relation}
            )

    salvaged = {"nodes": valid_nodes, "edges": valid_edges}
    accepted, _, _ = validate_extraction_payload(salvaged, source_text)
    return salvaged if accepted else None


def golden_to_extraction(golden: dict[str, Any]) -> dict[str, Any]:
    """Best-effort conversion of golden expected_content → pipeline_v3 nodes."""
    title = str(golden.get("title") or "").strip()
    raw_text = str(golden.get("source_chunk", {}).get("raw_text") or "").strip()
    expected = golden.get("expected_content") or {}
    entity_type = str(golden.get("type") or "concept")
    mapped_type = {
        "disease": "disease",
        "drug": "treatment",
        "test": "exam",
        "concept": "concept",
    }.get(entity_type, "concept")

    nodes: list[dict[str, Any]] = []
    for aspect, value in expected.items():
        if not value:
            continue
        content = f"{title}的{aspect}：{value}" if title else str(value)
        evidence = raw_text[: min(len(raw_text), 240)]
        nodes.append(
            {
                "title": f"{title}的{aspect}",
                "type": mapped_type,
                "parent_entity": title,
                "aspect": aspect,
                "content": content,
                "evidence": evidence,
                "tags": [],
            }
        )

    edges = []
    for rel in golden.get("expected_relations") or []:
        target = str(rel.get("target_name") or "").strip()
        relation = str(rel.get("relation_type") or "associated_with")
        relation_map = {
            "complication": "complication_of",
            "treatment": "treated_by",
            "related": "associated_with",
            "related_test": "associated_with",
            "related_concept": "associated_with",
            "contrast": "associated_with",
        }
        edges.append(
            {
                "source": title,
                "target": target,
                "relation": relation_map.get(relation, "associated_with"),
            }
        )

    return {"nodes": nodes, "edges": edges}


def iter_pipeline_chunks(pipeline_dir: Path) -> list[dict[str, Any]]:
    samples: list[dict[str, Any]] = []
    resolved_pipeline_dir = pipeline_dir.resolve()
    for path in sorted(resolved_pipeline_dir.glob("*.extraction.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        chunks = data.get("chunks") or {}
        for chunk_id, chunk in chunks.items():
            if not isinstance(chunk, dict):
                continue
            samples.append(
                {
                    "source_file": str(path.relative_to(PROJECT_ROOT.resolve())),
                    "chunk_id": str(chunk_id),
                    "headings": chunk.get("headings") or [],
                    "content": str(chunk.get("content") or ""),
                    "nodes": chunk.get("nodes") or [],
                    "edges": chunk.get("edges") or [],
                }
            )
    return samples


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_dataset(
    *,
    pipeline_dir: Path,
    golden_path: Path,
    output_dir: Path,
    include_empty_negatives: bool = True,
    max_empty_negatives: int = 20,
) -> dict[str, Any]:
    train_rows: list[dict[str, Any]] = []
    smoke_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    stats = {
        "total_input": 0,
        "schema_valid": 0,
        "evidence_matched": 0,
        "edge_resolved": 0,
        "accepted": 0,
        "rejected": 0,
        "empty_negative_included": 0,
        "golden_smoke_eval": 0,
        "rejection_reasons": {},
    }

    for sample in iter_pipeline_chunks(pipeline_dir):
        stats["total_input"] += 1
        source_text = clean_source_text(sample["content"])
        headings = sample["headings"]
        payload = {"nodes": sample["nodes"], "edges": sample["edges"]}

        user_prompt = build_user_prompt(headings, source_text)
        allow_empty = include_empty_negatives and not payload["nodes"]

        accepted, reasons, metrics = validate_extraction_payload(
            payload,
            source_text,
            allow_empty=allow_empty,
        )

        if metrics.get("schema_valid"):
            stats["schema_valid"] += 1
        if metrics.get("evidence_matched", 0) == metrics.get("node_count", 0) and metrics.get(
            "node_count", 0
        ) > 0:
            stats["evidence_matched"] += 1
        if metrics.get("edge_resolved"):
            stats["edge_resolved"] += 1

        record_base = {
            "id": f"{sample['source_file']}::{sample['chunk_id']}",
            "source_file": sample["source_file"],
            "chunk_id": sample["chunk_id"],
            "task": "pipeline_v3_extract",
        }

        if accepted:
            stats["accepted"] += 1
            assistant = compact_json(payload)
            train_rows.append(
                {
                    **record_base,
                    "text": format_chat_text(user_prompt, assistant),
                    "node_count": len(payload["nodes"]),
                    "edge_count": len(payload["edges"]),
                }
            )
            if not payload["nodes"]:
                stats["empty_negative_included"] += 1
        else:
            salvaged = salvage_valid_payload(payload, source_text)
            if salvaged is not None:
                stats["accepted"] += 1
                train_rows.append(
                    {
                        **record_base,
                        "text": format_chat_text(
                            user_prompt,
                            compact_json(salvaged),
                        ),
                        "node_count": len(salvaged["nodes"]),
                        "edge_count": len(salvaged["edges"]),
                        "salvaged_from_partial_chunk": True,
                    }
                )
            stats["rejected"] += 1
            for reason in reasons:
                if reason.startswith("node_") and ":" in reason:
                    key = reason.split(":", 1)[1]
                else:
                    key = reason
                stats["rejection_reasons"][key] = stats["rejection_reasons"].get(key, 0) + 1
            rejected_rows.append(
                {
                    **record_base,
                    "reasons": reasons,
                    "metrics": metrics,
                    "node_count": len(payload.get("nodes") or []),
                }
            )

    if include_empty_negatives:
        empty_candidates = [
            row
            for row in rejected_rows
            if row.get("node_count") == 0
            and "empty_nodes" in (row.get("reasons") or [])
        ]
        for row in empty_candidates[:max_empty_negatives]:
            # Re-include short/boilerplate chunks as explicit negative examples.
            sample = next(
                (
                    s
                    for s in iter_pipeline_chunks(pipeline_dir)
                    if f"{s['source_file']}::{s['chunk_id']}" == row["id"]
                ),
                None,
            )
            if not sample:
                continue
            source_text = clean_source_text(sample["content"])
            if len(source_text) < 80:
                continue
            user_prompt = build_user_prompt(sample["headings"], source_text)
            assistant = compact_json({"nodes": [], "edges": []})
            train_rows.append(
                {
                    "id": row["id"] + "::negative",
                    "source_file": row["source_file"],
                    "chunk_id": row["chunk_id"],
                    "task": "pipeline_v3_extract",
                    "text": format_chat_text(user_prompt, assistant),
                    "node_count": 0,
                    "edge_count": 0,
                    "is_negative_example": True,
                }
            )
            stats["empty_negative_included"] += 1

    golden = json.loads(golden_path.read_text(encoding="utf-8"))
    for item in golden:
        raw_text = str(item.get("source_chunk", {}).get("raw_text") or "").strip()
        headings = [
            str(item.get("source_chunk", {}).get("chapter") or "未识别"),
            str(item.get("title") or ""),
        ]
        payload = golden_to_extraction(item)
        user_prompt = build_user_prompt(headings, raw_text)
        assistant = compact_json(payload)
        smoke_rows.append(
            {
                "id": item.get("id"),
                "task": "pipeline_v3_extract_smoke_eval",
                "golden_title": item.get("title"),
                "text": format_chat_text(user_prompt, assistant),
                "expected": payload,
                "must_have_terms": item.get("must_have_terms") or [],
                "forbidden_terms": item.get("forbidden_terms") or [],
            }
        )
        stats["golden_smoke_eval"] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task": "pipeline_v3_extract",
        "pipeline_dir": str(pipeline_dir),
        "golden_path": str(golden_path),
        "stats": stats,
        "acceptance_rate": round(stats["accepted"] / max(stats["total_input"], 1), 4),
        "notes": [
            "golden 8 retained for smoke eval only; not included in sft_train.jsonl",
            "sft_val.jsonl reserved for future 30-50 human-reviewed samples",
            "rejected pipeline outputs are never silently promoted to train",
        ],
        "outputs": {
            "train": str(output_dir / "sft_train.jsonl"),
            "smoke_eval": str(output_dir / "sft_smoke_eval.jsonl"),
            "rejected": str(output_dir / "rejected_samples.jsonl"),
        },
    }

    write_jsonl(output_dir / "sft_train.jsonl", train_rows)
    write_jsonl(output_dir / "sft_smoke_eval.jsonl", smoke_rows)
    write_jsonl(output_dir / "rejected_samples.jsonl", rejected_rows)
    (output_dir / "data_quality_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Build gated SFT dataset for pipeline_v3_extract")
    parser.add_argument("--pipeline-dir", type=Path, default=DEFAULT_PIPELINE_DIR)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--no-empty-negatives", action="store_true")
    args = parser.parse_args()

    report = build_dataset(
        pipeline_dir=args.pipeline_dir,
        golden_path=args.golden,
        output_dir=args.output_dir,
        include_empty_negatives=not args.no_empty_negatives,
    )

    stats = report["stats"]
    print("SFT dataset build complete")
    print("=" * 60)
    for key in (
        "total_input",
        "schema_valid",
        "evidence_matched",
        "edge_resolved",
        "accepted",
        "rejected",
        "empty_negative_included",
        "golden_smoke_eval",
    ):
        print(f"{key:<24}: {stats[key]}")
    print(f"{'acceptance_rate':<24}: {report['acceptance_rate']:.1%}")
    print("=" * 60)
    if stats["rejection_reasons"]:
        print("Top rejection reasons:")
        for reason, count in sorted(
            stats["rejection_reasons"].items(),
            key=lambda item: item[1],
            reverse=True,
        )[:10]:
            print(f"  {reason}: {count}")
    print(f"\nReport: {args.output_dir / 'data_quality_report.json'}")


if __name__ == "__main__":
    main()
