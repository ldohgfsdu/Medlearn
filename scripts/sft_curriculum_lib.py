"""Construct three-stage evidence-copy curriculum rows from Tier A train samples."""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
TRAINING_DIR = SCRIPTS_DIR.parent / "training"
for path in (SCRIPTS_DIR, TRAINING_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from build_sft_dataset import compact_json, format_chat_text  # noqa: E402
from sft_eval_metrics import extract_prompt_and_expected, extract_source_text  # noqa: E402
from sft_repair_lib import extract_parent_entity_from_chapter  # noqa: E402
from textbook_pipeline.node_guardrails import (  # noqa: E402
    canonicalize_aspect_label,
    evidence_supported_by_source,
    normalize_match_text,
)

CHAPTER_PATH_RE = re.compile(r"章节路径：(.+?)\n", re.DOTALL)
STAGE1_MAX_SOURCE = 6000
STAGE2_MAX_SOURCE = 6000
STAGE3_MAX_SOURCE = 6000


def parse_train_sample(row: dict[str, Any]) -> dict[str, Any]:
    _, expected = extract_prompt_and_expected(row)
    nodes = list((expected or {}).get("nodes") or [])
    source_text = extract_source_text(str(row.get("text") or ""))
    chapter_path = str(row.get("chapter_path") or "").strip()
    if not chapter_path:
        match = CHAPTER_PATH_RE.search(str(row.get("text") or ""))
        chapter_path = match.group(1).strip() if match else "未识别"
    parent_entity = extract_parent_entity_from_chapter(chapter_path)
    aspects = sorted(
        {
            canonicalize_aspect_label(str(node.get("aspect") or "").strip())
            for node in nodes
            if str(node.get("aspect") or "").strip()
        }
    )
    return {
        "id": str(row.get("id") or ""),
        "source_text": source_text,
        "chapter_path": chapter_path,
        "parent_entity": parent_entity,
        "candidate_aspects": aspects,
        "nodes": nodes,
        "generation_method": str(row.get("generation_method") or "unknown"),
        "optional_edges": list(row.get("optional_edges") or []),
    }


def build_stage1_user_prompt(
    *,
    chapter_path: str,
    parent_entity: str,
    candidate_aspects: list[str],
    source_text: str,
) -> str:
    aspects_text = "、".join(candidate_aspects) if candidate_aspects else "未提供"
    trimmed = source_text[:STAGE1_MAX_SOURCE]
    return f"""你是医学教材 evidence 抽取器。仅根据给定原文，为每个候选 aspect 输出 source_text 中的逐字连续 evidence 片段。

要求：
1. evidence 必须是教材原文中的连续片段，禁止改写、翻译、概括或编造。
2. 每个 aspect 只输出一个 node；只包含 aspect 与 evidence 字段。
3. 不要输出 content、title、type、parent_entity。
4. 只输出合法 JSON，格式：{{"nodes":[{{"aspect":"...","evidence":"..."}}],"edges":[]}}

章节路径：{chapter_path}
主体实体：{parent_entity}
候选 aspects：{aspects_text}
教材原文：
{trimmed}
/no_think"""


def build_stage2_user_prompt(
    *,
    chapter_path: str,
    parent_entity: str,
    candidate_aspects: list[str],
    source_text: str,
) -> str:
    aspects_text = "、".join(candidate_aspects) if candidate_aspects else "未提供"
    trimmed = source_text[:STAGE2_MAX_SOURCE]
    return f"""你是医学教材知识提炼器。在 evidence 必须逐字来自原文的前提下，为每个 aspect 生成医学语义 content。

要求：
1. evidence 必须是教材原文中的连续片段，禁止改写。
2. content 必须是对 evidence 的语义提炼，不得引入 source_text 外的新事实。
3. content 不得与 evidence 完全相同。
4. 每个 aspect 只输出一个 node；字段仅包含 aspect、evidence、content。
5. 只输出合法 JSON，格式：{{"nodes":[{{"aspect":"...","evidence":"...","content":"..."}}],"edges":[]}}

章节路径：{chapter_path}
主体实体：{parent_entity}
候选 aspects：{aspects_text}
教材原文：
{trimmed}
/no_think"""


def build_stage3_user_prompt(
    *,
    chapter_path: str,
    source_text: str,
) -> str:
    trimmed = source_text[:STAGE3_MAX_SOURCE]
    return f"""你是医学教材“原子知识块”抽取器。仅根据给定原文抽取，不补充原文外事实。

要求：
1. nodes.type 只能是 concept、mechanism、disease、symptom、treatment、exam。
2. 每个节点代表 parent_entity 的一个知识面向；疾病章节中 parent_entity 必须是章节疾病或明确疾病亚型。
3. title 建议写“parent_entity + 的 + aspect”；content 首句必须写出 parent_entity 全称，不能用“该病、其、上述”。
4. aspect 填原文面向；evidence 必须是原文中的连续片段，禁止改写或编造。
5. content 必须是对 evidence 的语义提炼，且 content != evidence。
6. 同一个 parent_entity + aspect 只能输出一个 node。
7. 最多输出 12 个 nodes。
8. 只输出 nodes，edges 必须为空数组：{{"nodes":[...],"edges":[]}}

JSON 格式：
{{
  "nodes": [{{"title": "主体的知识面向", "type": "disease", "parent_entity": "主体名", "aspect": "面向", "content": "含主体的结论", "evidence": "原文片段", "tags": []}}],
  "edges": []
}}

章节路径：{chapter_path}
教材原文：
{trimmed}
/no_think"""


def build_stage1_assistant(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    staged_nodes = []
    for node in nodes:
        aspect = canonicalize_aspect_label(str(node.get("aspect") or "").strip())
        evidence = str(node.get("evidence") or "").strip()
        if not aspect or not evidence:
            continue
        staged_nodes.append({"aspect": aspect, "evidence": evidence})
    return {"nodes": staged_nodes, "edges": []}


def build_stage2_assistant(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    staged_nodes = []
    for node in nodes:
        aspect = canonicalize_aspect_label(str(node.get("aspect") or "").strip())
        evidence = str(node.get("evidence") or "").strip()
        content = str(node.get("content") or "").strip()
        if not aspect or not evidence or not content:
            continue
        staged_nodes.append(
            {
                "aspect": aspect,
                "evidence": evidence,
                "content": content,
            }
        )
    return {"nodes": staged_nodes, "edges": []}


def build_stage3_assistant(
    nodes: list[dict[str, Any]],
    *,
    optional_edges: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    staged_nodes = []
    for node in nodes:
        staged = {
            "title": str(node.get("title") or "").strip(),
            "type": str(node.get("type") or "").strip(),
            "parent_entity": str(node.get("parent_entity") or "").strip(),
            "aspect": canonicalize_aspect_label(str(node.get("aspect") or "").strip()),
            "content": str(node.get("content") or "").strip(),
            "evidence": str(node.get("evidence") or "").strip(),
            "tags": list(node.get("tags") or []),
        }
        if all(staged[field] for field in ("title", "type", "parent_entity", "aspect", "content", "evidence")):
            staged_nodes.append(staged)
    payload = {"nodes": staged_nodes, "edges": []}
    if optional_edges:
        payload["optional_edges"] = copy.deepcopy(optional_edges)
    return payload


def validate_stage_row(
    stage: str,
    *,
    source_text: str,
    assistant_payload: dict[str, Any],
) -> list[str]:
    issues: list[str] = []
    nodes = assistant_payload.get("nodes") or []
    if len(nodes) < 3:
        issues.append("insufficient_nodes")

    for node in nodes:
        evidence = str(node.get("evidence") or "").strip()
        if not evidence_supported_by_source(evidence, source_text):
            issues.append("evidence_not_in_source")
            break

    if stage in {"stage2_evidence_content_distill", "stage3_full_nodes_only"}:
        for node in nodes:
            content = str(node.get("content") or "").strip()
            evidence = str(node.get("evidence") or "").strip()
            if content and evidence and normalize_match_text(content) == normalize_match_text(evidence):
                issues.append("content_equals_evidence")
                break

    if stage == "stage1_evidence_copy":
        for node in nodes:
            if "content" in node:
                issues.append("stage1_has_content_field")
                break

    edges = assistant_payload.get("edges")
    if edges not in (None, []):
        issues.append("edges_must_be_empty")

    return sorted(set(issues))


def build_curriculum_row(
    parsed: dict[str, Any],
    *,
    stage: str,
    stage_index: int,
) -> dict[str, Any] | None:
    source_text = parsed["source_text"]
    nodes = parsed["nodes"]
    if not source_text or len(nodes) < 3:
        return None

    if stage == "stage1_evidence_copy":
        user_prompt = build_stage1_user_prompt(
            chapter_path=parsed["chapter_path"],
            parent_entity=parsed["parent_entity"],
            candidate_aspects=parsed["candidate_aspects"],
            source_text=source_text,
        )
        assistant_payload = build_stage1_assistant(nodes)
    elif stage == "stage2_evidence_content_distill":
        user_prompt = build_stage2_user_prompt(
            chapter_path=parsed["chapter_path"],
            parent_entity=parsed["parent_entity"],
            candidate_aspects=parsed["candidate_aspects"],
            source_text=source_text,
        )
        assistant_payload = build_stage2_assistant(nodes)
    elif stage == "stage3_full_nodes_only":
        user_prompt = build_stage3_user_prompt(
            chapter_path=parsed["chapter_path"],
            source_text=source_text,
        )
        assistant_payload = build_stage3_assistant(
            nodes,
            optional_edges=parsed.get("optional_edges"),
        )
    else:
        raise ValueError(f"unknown stage: {stage}")

    issues = validate_stage_row(stage, source_text=source_text, assistant_payload=assistant_payload)
    if issues:
        return None

    sample_id = parsed["id"]
    return {
        "id": f"{sample_id}::{stage}",
        "source_sample_id": sample_id,
        "stage": stage,
        "stage_index": stage_index,
        "curriculum_task": stage,
        "chapter_path": parsed["chapter_path"],
        "parent_entity": parsed["parent_entity"],
        "generation_method": parsed["generation_method"],
        "node_count": len(assistant_payload.get("nodes") or []),
        "text": format_chat_text(user_prompt, compact_json({"nodes": assistant_payload["nodes"], "edges": []})),
        "optional_edges": parsed.get("optional_edges") or [],
    }


def build_sampling_policy(distribution_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "dataset_version": distribution_report.get("dataset_version", "sft_v2_expanded_182"),
        "total_samples": distribution_report.get("total_samples", 0),
        "skew_flags": distribution_report.get("skew_flags", []),
        "sampler_recommendations": distribution_report.get("sampler_recommendations", []),
        "defaults": {
            "stage_order": [
                "stage1_evidence_copy",
                "stage2_evidence_content_distill",
                "stage3_full_nodes_only",
            ],
            "max_per_parent_entity_per_batch": 2,
            "hydrated_non_hydrated_ratio_target": "1:1",
            "chapter_balanced_batches": True,
        },
        "note": "Do not delete Tier A samples; apply these controls during curriculum training only.",
    }