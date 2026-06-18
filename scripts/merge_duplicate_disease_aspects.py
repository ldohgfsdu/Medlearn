"""Merge duplicate disease knowledge nodes that share one aspect.

Dry-run is the default. Pass --apply to update the primary node and mark
superseded nodes as invalid without deleting rows referenced elsewhere.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Any

from supabase import create_client

from merge_duplicate_quality import (
    assess_merge_group,
    render_merged_content,
    sanitize_sections,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "duplicate-disease-aspect-merge.json"
ASPECT_LABELS = {
    "definition": "定义",
    "epidemiology": "流行病学",
    "etiology": "病因",
    "pathogenesis": "发病机制",
    "clinical_manifestation": "临床表现",
    "diagnosis": "诊断与检查",
    "differential_diagnosis": "鉴别诊断",
    "treatment": "治疗方案",
    "prognosis": "预后",
    "prevention": "预防",
    "other": "其他",
}


def node_text(node: dict[str, Any]) -> str:
    content = str(node.get("content") or "").strip()
    if content:
        return content
    sections = node.get("structured_sections") or []
    section_text = "\n\n".join(
        str(section.get("content") or "").strip()
        for section in sections
        if isinstance(section, dict) and str(section.get("content") or "").strip()
    )
    if section_text:
        return section_text
    return "\n".join(str(value).strip() for value in node.get("key_points") or [] if str(value).strip())


def read_source_span(node: dict[str, Any]) -> dict[str, Any]:
    source_span = node.get("source_span") or {}
    return source_span if isinstance(source_span, dict) else {}


def group_key_for_node(
    node: dict[str, Any],
    *,
    schema_mode: str,
) -> tuple[str, ...] | None:
    if schema_mode == "converged":
        disease_id = str(node.get("disease_id") or "").strip()
        section_id = str(node.get("chapter_section_id") or "").strip()
        aspect = str(node.get("aspect") or "").strip()
        raw_aspect = str(node.get("raw_aspect") or "").strip()
        if not (disease_id and section_id and aspect):
            return None
        if aspect == "other" and not raw_aspect:
            return None
        discriminator = raw_aspect if aspect == "other" else aspect
        return (disease_id, section_id, aspect, discriminator)

    source_span = read_source_span(node)
    parent_entity = str(source_span.get("parent_entity") or "").strip()
    aspect = str(source_span.get("aspect") or "").strip()
    chapter = str(node.get("chapter") or "").strip()
    sub_chapter = str(node.get("sub_chapter") or "").strip()
    if not (parent_entity and aspect and chapter):
        return None
    return (chapter, sub_chapter, parent_entity, aspect)


def build_merge_plan(
    nodes: list[dict[str, Any]],
    *,
    schema_mode: str = "converged",
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        key = group_key_for_node(node, schema_mode=schema_mode)
        if key:
            grouped[key].append(node)

    plan: list[dict[str, Any]] = []
    for group_key, members in grouped.items():
        if len(members) < 2:
            continue
        ordered = sorted(
            members,
            key=lambda node: (int(node.get("order_num") or 0), str(node.get("id") or "")),
        )
        primary, *duplicates = ordered
        group_aspect = group_key[2] if schema_mode == "converged" else group_key[3]
        group_parent = ""
        raw_sections = [
            {
                "title": str(
                    node.get("display_title")
                    or node.get("title")
                    or ASPECT_LABELS.get(group_aspect, group_aspect)
                ).strip(),
                "content": node_text(node),
            }
            for node in ordered
            if node_text(node)
        ]
        sections = sanitize_sections(raw_sections)
        merged_content = render_merged_content(sections)
        aspect_label = ""
        group_parent = ""
        group_meta: dict[str, Any] = {"group_key": list(group_key)}
        if schema_mode == "converged":
            disease_id, section_id, aspect, discriminator = group_key
            aspect_label = (
                discriminator
                if aspect == "other"
                else ASPECT_LABELS.get(aspect, str(primary.get("raw_aspect") or aspect))
            )
            group_meta.update(
                {
                    "disease_id": disease_id,
                    "chapter_section_id": section_id,
                    "aspect": aspect,
                }
            )
        else:
            chapter, sub_chapter, parent_entity, aspect = group_key
            aspect_label = ASPECT_LABELS.get(aspect, aspect)
            group_parent = parent_entity
            group_meta.update(
                {
                    "chapter": chapter,
                    "sub_chapter": sub_chapter,
                    "parent_entity": parent_entity,
                    "aspect": aspect,
                }
            )

        for node in ordered:
            candidate = read_source_span(node).get("parent_entity")
            if isinstance(candidate, str) and candidate.strip():
                group_parent = candidate.strip()
                break

        primary_update: dict[str, Any] = {
            "content": merged_content,
            "structured_sections": sections,
            "key_points": list(dict.fromkeys(
                str(point).strip()
                for node in ordered
                for point in node.get("key_points") or []
                if str(point).strip()
            )),
        }
        if schema_mode == "converged":
            primary_update["display_title"] = aspect_label

        blockers = assess_merge_group(
            group_aspect=str(group_meta.get("aspect") or group_aspect),
            group_parent=group_parent,
            members=ordered,
            sections=sections,
        )

        plan.append(
            {
                **group_meta,
                "primary_id": primary["id"],
                "duplicate_ids": [node["id"] for node in duplicates],
                "member_ids": [node["id"] for node in ordered],
                "primary_update": primary_update,
                "blockers": blockers,
                "approved": not blockers,
            }
        )
    return plan


def partition_plan(plan: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    approved = [item for item in plan if item.get("approved")]
    blocked = [item for item in plan if not item.get("approved")]
    return approved, blocked


def summarize_blockers(plan: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for item in plan:
        for blocker in item.get("blockers") or []:
            reason = str(blocker).split(":", 1)[0]
            counts[reason] += 1
    return dict(sorted(counts.items()))


def detect_schema_mode(client: Any) -> str:
    from postgrest.exceptions import APIError

    try:
        probe = (
            client.table("knowledge_nodes")
            .select("id,disease_id,aspect,content_class")
            .limit(1)
            .execute()
        )
    except APIError:
        return "legacy"

    row = probe.data[0] if probe.data else {}
    if any(key in row for key in ("disease_id", "aspect", "content_class")):
        return "converged"
    return "legacy"


def fetch_nodes(
    client: Any,
    disease_id: str | None,
    *,
    schema_mode: str,
) -> list[dict[str, Any]]:
    if schema_mode == "converged":
        select_columns = (
            "id,title,display_title,aspect,raw_aspect,content,key_points,"
            "structured_sections,order_num,disease_id,chapter_section_id,content_class,source_span"
        )
    else:
        select_columns = (
            "id,title,content,key_points,structured_sections,order_num,"
            "chapter,sub_chapter,source_span"
        )

    rows: list[dict[str, Any]] = []
    page_size = 1000
    for start in range(0, 100_000, page_size):
        query = (
            client.table("knowledge_nodes")
            .select(select_columns)
            .range(start, start + page_size - 1)
        )
        if schema_mode == "converged":
            query = query.eq("content_class", "confirmed_disease")
            if disease_id:
                query = query.eq("disease_id", disease_id)
        batch = query.execute().data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
    return rows


def apply_plan(client: Any, plan: list[dict[str, Any]]) -> None:
    for item in plan:
        client.table("knowledge_nodes").update(item["primary_update"]).eq(
            "id", item["primary_id"]
        ).execute()
        for duplicate_id in item["duplicate_ids"]:
            client.table("knowledge_nodes").update(
                {"content_class": "invalid", "disease_id": None}
            ).eq("id", duplicate_id).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="合并同一疾病、章节和 aspect 下的重复知识节点"
    )
    parser.add_argument("--apply", action="store_true", help="执行数据库更新；默认仅生成报告")
    parser.add_argument("--disease-id", help="只处理一个 disease_id")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass

    args = parse_args()
    url = os.getenv("SUPABASE_URL") or os.getenv("EXPO_PUBLIC_SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError("需要 SUPABASE_URL 和 SUPABASE_SERVICE_ROLE_KEY")

    client = create_client(url, key)
    schema_mode = detect_schema_mode(client)
    if args.apply and schema_mode != "converged":
        raise RuntimeError(
            "远程库尚未应用 migration 022（缺少 disease_id/aspect/content_class）。"
            "请先部署迁移并回填身份字段，再执行 --apply。"
        )

    nodes = fetch_nodes(client, args.disease_id, schema_mode=schema_mode)
    plan = build_merge_plan(nodes, schema_mode=schema_mode)
    approved_plan, blocked_plan = partition_plan(plan)
    report = {
        "mode": "apply" if args.apply else "dry-run",
        "schema_mode": schema_mode,
        "scanned_nodes": len(nodes),
        "merged_groups": len(plan),
        "approved_groups": len(approved_plan),
        "blocked_groups": len(blocked_plan),
        "superseded_nodes": sum(len(item["duplicate_ids"]) for item in plan),
        "approved_superseded_nodes": sum(len(item["duplicate_ids"]) for item in approved_plan),
        "blocker_summary": summarize_blockers(plan),
        "execution_ready": len(blocked_plan) == 0,
        "note": (
            "legacy 报告仅作问题清单；正式 --apply 需在 migration 022 与身份回填后，"
            "以 converged dry-run 的 approved_groups 为准。"
        ),
        "groups": plan,
        "approved": approved_plan,
        "blocked": blocked_plan,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    if args.apply:
        if blocked_plan:
            raise RuntimeError(
                f"存在 {len(blocked_plan)} 组未通过质量门禁，拒绝 --apply。"
                "请先修复数据或仅保留 approved_groups。"
            )
        apply_plan(client, approved_plan)
    print(
        f"[{report['mode']}/{schema_mode}] 扫描 {len(nodes)} 个节点，"
        f"发现 {len(plan)} 组重复（可执行 {len(approved_plan)}，阻断 {len(blocked_plan)}），"
        f"涉及 {report['superseded_nodes']} 个冗余节点"
    )
    print(f"报告: {args.report}")


if __name__ == "__main__":
    main()
