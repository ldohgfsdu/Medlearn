"""Backfill chapter/disease identities and write a deterministic audit report.

Dry-run is the default. Pass --apply to write chapter_sections,
disease_entities, and knowledge_nodes identity fields to Supabase.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import create_client


ROOT = Path(__file__).resolve().parents[1]
AUDIT_PATH = ROOT / "reports" / "entity-resolution-audit.json"
NORMALIZATION_VERSION = 1
RESOLUTION_VERSION = 1

NON_DISEASE_RE = re.compile(
    r"(总论|概述|诊疗原则|治疗原则|常见症状|临床思维|分类|检查方法|抗感染治疗|"
    r"系统疾病|心血管疾病|危重症医学|烟草病学)$"
)
DISEASE_HINT_RE = re.compile(
    r"(病|炎|癌|瘤|综合征|障碍|衰竭|梗死|栓塞|中毒|中毒症|损伤|感染|贫血|"
    r"白血病|淋巴瘤|心绞痛|休克|高血压|心律失常|心动过速|期前收缩|"
    r"颤动|扑动|传导阻滞|未闭|缺损|反流|狭窄|夹层|气胸|胸腔积液|"
    r"肺水肿|肥厚|痉挛|猝死|骤停|硬化|破裂|功能失调|哮喘|脓肿|"
    r"肺动脉高压|呼吸暂停|栓塞症|纤维化|扩张症|功能不全|房颤|"
    r"风湿热|急症|流感|脓胸|四联症|结核|心动过缓|停搏|血栓形成|"
    r"增多症|闭塞症|神经症|血症|瘘)$"
)
NON_DISEASE_ENTITY_RE = re.compile(
    r"(药物|制剂|抑制剂|拮抗剂|激动剂|利尿剂|他汀类|糖皮质激素|"
    r"治疗|手术|移植术|置换术|封堵术|植入术|介入术|消融|穿刺|活检|"
    r"检查|造影|监测|评估|检测|康复|结构|机制|屏障|系统|"
    r"吸烟|烟草|电子烟|暴露|微生态|医学|导管|瓣膜置换术)$"
)
NON_DISEASE_EXACT = frozenset({
    "ICS",
    "SABA",
    "地高辛",
    "心脏",
    "冠状动脉",
    "左冠状动脉",
    "肠道微生态",
})
KNOWN_DISEASE_ABBREVIATIONS = frozenset({
    "ACS",
    "ARDS",
    "COPD",
    "CTEPD",
    "CTEPH",
    "DVT",
    "NTM肺病",
    "PTE",
    "STEMI",
    "先天性二叶主动脉瓣",
    "心肌桥",
})
DISEASE_ABBREVIATION_RE = re.compile(
    r"(?:ACS|ARDS|COPD|CTEPD|CTEPH|DVT|PTE|STEMI)$",
    re.IGNORECASE,
)
ASPECT_RULES = (
    ("definition", re.compile(r"定义|概念|概述")),
    ("epidemiology", re.compile(r"流行病学")),
    ("etiology", re.compile(r"病因|危险因素")),
    ("pathogenesis", re.compile(r"发病机制|病理生理|机制")),
    ("clinical_manifestation", re.compile(r"临床表现|临床特征|症状|体征")),
    ("differential_diagnosis", re.compile(r"鉴别诊断|诊断与鉴别")),
    ("diagnosis", re.compile(r"诊断|检查|检验|影像")),
    ("treatment", re.compile(r"治疗|用药|手术|处理原则")),
    ("prognosis", re.compile(r"预后|并发症")),
    ("prevention", re.compile(r"预防")),
)

GOLDEN_DISEASES: dict[str, dict[str, Any]] = {
    "慢性阻塞性肺疾病": {
        "aliases": ["COPD", "慢阻肺", "慢阻肺病"],
        "sub_chapter": "第三章 慢性阻塞性肺疾病",
    },
    "支气管哮喘": {
        "aliases": ["哮喘"],
        "sub_chapter": "第四章 支气管哮喘",
    },
    "肺炎链球菌肺炎": {
        "aliases": ["肺炎球菌肺炎", "链球菌肺炎"],
        "sub_chapter": "第六章 肺部感染性疾病",
    },
    "肺结核": {
        "aliases": ["结核病", "肺痨"],
        "sub_chapter": "第八章 肺结核",
    },
    "肺癌": {
        "aliases": ["原发性支气管癌", "原发性支气管肺癌"],
        "sub_chapter": "第九章 肺癌",
    },
}
OVERVIEW_ENTITIES = frozenset({"肺炎", "肺部感染性疾病"})


def stable_id(prefix: str, *parts: str) -> str:
    payload = "|".join(("v1", *parts))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]
    return f"{prefix}-{digest}"


def normalize_catalog_path(value: str) -> str:
    value = value.replace("｜", "|").replace("|", "/")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"/+", "/", value)
    return value.strip("/")


def normalize_disease_name(value: str) -> str:
    value = re.sub(r"^第[一二三四五六七八九十百零〇\d]+(?:章|节)\s*", "", value.strip())
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"[，。；：、（）()【】《》\"'“”‘’]", "", value).lower()
    duplicated_pneumonia = re.match(r"^肺炎(.+肺炎)$", value)
    return duplicated_pneumonia.group(1) if duplicated_pneumonia else value


def split_explicit_aliases(value: str) -> tuple[str, list[str]]:
    aliases: list[str] = []
    for group in re.findall(r"[（(]([^）)]+)[）)]", value):
        aliases.extend(
            alias.strip()
            for alias in re.split(r"[/、,，]", group)
            if alias.strip()
        )
    canonical = re.sub(r"[（(][^）)]+[）)]", "", value).strip()
    return canonical or value.strip(), aliases


def golden_alias_registry() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for canonical, config in GOLDEN_DISEASES.items():
        aliases[normalize_disease_name(canonical)] = canonical
        for alias in config["aliases"]:
            aliases[normalize_disease_name(alias)] = canonical
    return aliases


def canonicalize_candidate(value: str) -> tuple[str, list[str]]:
    canonical, explicit_aliases = split_explicit_aliases(value)
    golden_name = golden_alias_registry().get(normalize_disease_name(canonical))
    if not golden_name:
        return canonical, explicit_aliases
    configured_aliases = GOLDEN_DISEASES[golden_name]["aliases"]
    return golden_name, list(dict.fromkeys([*configured_aliases, *explicit_aliases]))


def has_page_evidence(node: dict[str, Any]) -> bool:
    source_span = node.get("source_span") or {}
    provenance = source_span.get("provenance") or {}
    return (
        source_span.get("page_start") is not None
        or provenance.get("page_start") is not None
    ) and bool(str(source_span.get("evidence") or "").strip())


def disease_content_status(
    canonical_name: str,
    nodes: list[dict[str, Any]],
) -> str:
    config = GOLDEN_DISEASES.get(canonical_name)
    if not config:
        return "in_progress"
    expected_nodes = [
        node
        for node in nodes
        if str(node.get("sub_chapter") or "") == config["sub_chapter"]
    ]
    if not expected_nodes:
        return "in_progress"
    aspects = {
        map_aspect(str((node.get("source_span") or {}).get("aspect") or ""))
        for node in expected_nodes
    }
    enough_grounded_content = (
        len(expected_nodes) >= 3
        and len(aspects - {"other"}) >= 3
        and all(has_page_evidence(node) for node in expected_nodes)
    )
    return "available" if enough_grounded_content else "in_progress"


def build_golden_acceptance(
    nodes: list[dict[str, Any]],
    diseases: list[dict[str, Any]],
    updates: list[dict[str, Any]],
) -> dict[str, Any]:
    updates_by_id = {str(update["id"]): update for update in updates}
    diseases_by_name = {
        str(disease["canonical_disease_name"]): disease for disease in diseases
    }
    summaries: list[dict[str, Any]] = []

    for canonical_name, config in GOLDEN_DISEASES.items():
        matching_nodes = [
            node
            for node in nodes
            if canonicalize_candidate(parse_topic(node)[0])[0] == canonical_name
        ]
        expected_nodes = [
            node
            for node in matching_nodes
            if str(node.get("sub_chapter") or "") == config["sub_chapter"]
        ]
        wrong_chapter_nodes = [
            node
            for node in matching_nodes
            if str(node.get("sub_chapter") or "") != config["sub_chapter"]
        ]
        aspects = sorted({
            str(updates_by_id[str(node["id"])].get("aspect") or "other")
            for node in expected_nodes
            if str(node["id"]) in updates_by_id
        })
        entity = diseases_by_name.get(canonical_name)
        failures: list[str] = []
        if not expected_nodes:
            failures.append("missing_expected_chapter_nodes")
        if not entity:
            failures.append("missing_disease_entity")
        elif entity.get("node_type") != "disease":
            failures.append("invalid_node_type")
        if len(set(aspects) - {"other"}) < 3:
            failures.append("insufficient_standard_aspects")
        if expected_nodes and not all(has_page_evidence(node) for node in expected_nodes):
            failures.append("missing_page_evidence")
        if not entity or entity.get("content_status") != "available":
            failures.append("content_not_available")

        summaries.append({
            "canonical_name": canonical_name,
            "aliases": config["aliases"],
            "expected_sub_chapter": config["sub_chapter"],
            "node_type": entity.get("node_type") if entity else None,
            "content_status": entity.get("content_status") if entity else None,
            "expected_chapter_node_count": len(expected_nodes),
            "wrong_chapter_node_count": len(wrong_chapter_nodes),
            "standard_aspects": aspects,
            "nodes_with_evidence": sum(
                bool(str((node.get("source_span") or {}).get("evidence") or "").strip())
                for node in expected_nodes
            ),
            "nodes_with_page": sum(has_page_evidence(node) for node in expected_nodes),
            "hard_failures": failures,
        })

    pneumonia_nodes = [
        node
        for node in nodes
        if canonicalize_candidate(parse_topic(node)[0])[0] == "肺炎"
    ]
    pneumonia_classes = sorted({
        str(updates_by_id[str(node["id"])].get("content_class") or "")
        for node in pneumonia_nodes
        if str(node["id"]) in updates_by_id
    })
    overview_failures = (
        ["pneumonia_overview_classified_as_disease"]
        if "confirmed_disease" in pneumonia_classes
        else []
    )
    all_failures = [
        f"{summary['canonical_name']}:{failure}"
        for summary in summaries
        for failure in summary["hard_failures"]
    ]
    all_failures.extend(overview_failures)
    return {
        "execution_ready": not all_failures,
        "hard_failures": all_failures,
        "golden_diseases": summaries,
        "pneumonia_overview": {
            "node_count": len(pneumonia_nodes),
            "content_classes": pneumonia_classes,
            "hard_failures": overview_failures,
        },
    }


def parse_topic(node: dict[str, Any]) -> tuple[str, str]:
    span = node.get("source_span") or {}
    parent = str(span.get("parent_entity") or "").strip()
    raw_aspect = str(span.get("aspect") or "").strip()
    if parent:
        return parent, raw_aspect

    title = str(node.get("title") or "").strip()
    match = re.match(r"^(.+?)的(.+)$", title)
    if match:
        return match.group(1).strip(), raw_aspect or match.group(2).strip()

    chapter = re.sub(
        r"^第[一二三四五六七八九十百零〇\d]+章\s*", "", str(node.get("sub_chapter") or "")
    ).strip()
    return chapter or title, raw_aspect or title


def map_aspect(raw_aspect: str) -> str:
    for aspect, pattern in ASPECT_RULES:
        if pattern.search(raw_aspect):
            return aspect
    return "other"


def textbook_series_id(node: dict[str, Any]) -> str:
    book_id = str(node.get("book_id") or node.get("textbook") or "unknown")
    return re.sub(r"-\d+$", "", book_id)


def classify_candidate(
    name: str,
    node_type: str,
    evidence_count: int = 0,
    aspect_count: int = 0,
) -> tuple[str, str, float]:
    if not name:
        return "invalid", "缺少可解析的知识实体名称", 0
    if name in OVERVIEW_ENTITIES:
        return "non_disease_knowledge", "目录总览节点不得作为疾病实体", 1
    if name in NON_DISEASE_EXACT or NON_DISEASE_RE.search(name) or NON_DISEASE_ENTITY_RE.search(name):
        return "non_disease_knowledge", "目录标题属于合法非疾病教材知识", 0.98
    if re.search(r"[、与及或]", name):
        return "non_disease_knowledge", "标题包含多个并列实体，作为章节知识承接", 0.96
    if (
        name in KNOWN_DISEASE_ABBREVIATIONS
        or DISEASE_ABBREVIATION_RE.search(name)
        or DISEASE_HINT_RE.search(name)
    ):
        return "confirmed_disease", "名称具有明确疾病或临床状态语义", 0.92
    return "suspected_disease", "实体名称疑似疾病但缺少确定性证据，进入审核", 0.5


def build_rows(nodes: list[dict[str, Any]]) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    sections: dict[str, dict] = {}
    diseases: dict[tuple[str, str], dict] = {}
    updates: list[dict] = []
    audit: list[dict] = []
    alias_registry: dict[tuple[str, str], tuple[str, str, list[str]]] = {}
    candidate_stats: dict[tuple[str, str], dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "aspects": set(), "nodes": [], "sub_chapters": set()}
    )

    for node in nodes:
        series_id = textbook_series_id(node)
        candidate_name, raw_aspect = parse_topic(node)
        canonical_name, aliases = canonicalize_candidate(candidate_name)
        canonical_key = normalize_disease_name(canonical_name)
        stats = candidate_stats[(series_id, canonical_key)]
        stats["count"] += 1
        stats["aspects"].add(map_aspect(raw_aspect))
        stats["nodes"].append(node)
        stats["sub_chapters"].add(str(node.get("sub_chapter") or ""))
        if not aliases:
            continue
        for alias in aliases:
            alias_registry[(series_id, normalize_disease_name(alias))] = (
                canonical_name,
                canonical_key,
                aliases,
            )

    for node in nodes:
        series_id = textbook_series_id(node)
        path_parts = [
            str(node.get("chapter") or "").strip(),
            str(node.get("sub_chapter") or "").strip(),
        ]
        normalized_parts = [
            normalize_catalog_path(part) for part in path_parts if part
        ]
        catalog_path = normalize_catalog_path("/".join(normalized_parts))
        if not catalog_path:
            catalog_path = normalize_catalog_path(str(node.get("title") or "未分类"))
        parent_section_id = None
        version_id = str(node.get("book_id") or node.get("textbook") or series_id)
        if len(normalized_parts) > 1:
            parent_path = normalized_parts[0]
            parent_section_id = stable_id("section", series_id, parent_path)
            parent = sections.setdefault(
                parent_section_id,
                {
                    "chapter_section_id": parent_section_id,
                    "textbook_series_id": series_id,
                    "source_textbook_version_ids": [],
                    "catalog_path": parent_path,
                    "display_title": path_parts[0],
                    "parent_section_id": None,
                    "order_index": int(node.get("order_num") or 0),
                },
            )
            if version_id not in parent["source_textbook_version_ids"]:
                parent["source_textbook_version_ids"].append(version_id)

        chapter_section_id = stable_id("section", series_id, catalog_path)
        section = sections.setdefault(
            chapter_section_id,
            {
                "chapter_section_id": chapter_section_id,
                "textbook_series_id": series_id,
                "source_textbook_version_ids": [],
                "catalog_path": catalog_path,
                "display_title": path_parts[-1] or str(node.get("title") or "未分类"),
                "parent_section_id": parent_section_id,
                "order_index": int(node.get("order_num") or 0),
            },
        )
        if version_id not in section["source_textbook_version_ids"]:
            section["source_textbook_version_ids"].append(version_id)

        raw_candidate_name, raw_aspect = parse_topic(node)
        candidate_name, explicit_aliases = canonicalize_candidate(raw_candidate_name)
        candidate_key = normalize_disease_name(candidate_name)
        alias_match = alias_registry.get((series_id, candidate_key))
        if alias_match:
            candidate_name, candidate_key, registered_aliases = alias_match
            explicit_aliases = list({*explicit_aliases, *registered_aliases, raw_candidate_name})
        stats = candidate_stats[(series_id, candidate_key)]
        content_class, reason, confidence = classify_candidate(
            candidate_name,
            str(node.get("type") or ""),
            evidence_count=stats["count"],
            aspect_count=len(stats["aspects"]),
        )
        golden_config = GOLDEN_DISEASES.get(candidate_name)
        current_sub_chapter = str(node.get("sub_chapter") or "")
        if golden_config and current_sub_chapter != golden_config["sub_chapter"]:
            content_class = "invalid"
            reason = (
                f"黄金疾病实体跨章归属冲突：期望 {golden_config['sub_chapter']}，"
                f"实际 {current_sub_chapter or '未知章节'}"
            )
            confidence = 0
        disease_id = None

        if content_class == "confirmed_disease":
            disease_id = stable_id("disease", series_id, candidate_key)
            key = (series_id, candidate_key)
            disease = diseases.setdefault(
                key,
                {
                    "disease_id": disease_id,
                    "canonical_disease_name": candidate_name,
                    "canonical_key": candidate_key,
                    "aliases": explicit_aliases,
                    "source_textbook_series_id": series_id,
                    "source_chapter_section_ids": [],
                    "confidence": confidence,
                    "resolution_status": "confirmed",
                    "resolution_reason": reason,
                    "resolved_at": datetime.now(timezone.utc).isoformat(),
                    "resolved_by": "script",
                    "resolution_version": RESOLUTION_VERSION,
                    "normalization_version": NORMALIZATION_VERSION,
                    "node_type": "disease",
                    "content_status": disease_content_status(
                        candidate_name,
                        list(stats["nodes"]),
                    ),
                },
            )
            if chapter_section_id not in disease["source_chapter_section_ids"]:
                disease["source_chapter_section_ids"].append(chapter_section_id)
            for alias in explicit_aliases:
                if alias != candidate_name and alias not in disease["aliases"]:
                    disease["aliases"].append(alias)

        aspect = map_aspect(raw_aspect)
        updates.append(
            {
                "id": node["id"],
                "disease_id": disease_id,
                "chapter_section_id": chapter_section_id,
                "aspect": aspect,
                "raw_aspect": raw_aspect or None,
                "display_title": raw_aspect or str(node.get("title") or ""),
                "content_class": content_class,
            }
        )
        audit.append(
            {
                "candidate_id": stable_id("candidate", str(node["id"]), candidate_key),
                "knowledge_node_id": node["id"],
                "candidate_name": candidate_name,
                "candidate_key": candidate_key,
                "matched_entity_id": disease_id,
                "content_class": content_class,
                "resolution_status": (
                    "confirmed"
                    if disease_id
                    else "rejected"
                    if content_class == "invalid"
                    else "review_required"
                    if content_class == "suspected_disease"
                    else None
                ),
                "confidence": confidence,
                "evidence_refs": [
                    {
                        "chapter": node.get("chapter"),
                        "sub_chapter": node.get("sub_chapter"),
                        "source_span": node.get("source_span"),
                    }
                ],
                "reason": reason,
                "normalization_version": NORMALIZATION_VERSION,
            }
        )

    return list(sections.values()), list(diseases.values()), updates, audit


def upsert_batches(client: Any, table: str, rows: list[dict], batch_size: int = 100) -> None:
    for index in range(0, len(rows), batch_size):
        client.table(table).upsert(rows[index:index + batch_size]).execute()


def update_rows_by_id(client: Any, table: str, rows: list[dict]) -> None:
    total = len(rows)
    for index, row in enumerate(rows, start=1):
        row_id = row["id"]
        payload = {key: value for key, value in row.items() if key != "id"}
        client.table(table).update(payload).eq("id", row_id).execute()
        if index % 100 == 0 or index == total:
            print(f"  [+] {table} identities {index}/{total}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write resolved identities to Supabase")
    parser.add_argument("--audit-path", type=Path, default=AUDIT_PATH)
    args = parser.parse_args()

    url = os.environ.get("EXPO_PUBLIC_SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise SystemExit("EXPO_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")

    client = create_client(url, key)
    nodes: list[dict[str, Any]] = []
    page_size = 1000
    for start in range(0, 100_000, page_size):
        response = (
            client.table("knowledge_nodes")
            .select(
                "id,title,type,chapter,sub_chapter,order_num,book_id,textbook,"
                "structured_sections,source_span,content_class"
            )
            .range(start, start + page_size - 1)
            .execute()
        )
        page = response.data or []
        nodes.extend(
            node for node in page if node.get("content_class") != "invalid"
        )
        if len(page) < page_size:
            break
    sections, diseases, updates, audit = build_rows(nodes)
    acceptance = build_golden_acceptance(nodes, diseases, updates)

    args.audit_path.parent.mkdir(parents=True, exist_ok=True)
    args.audit_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "normalization_version": NORMALIZATION_VERSION,
                "counts": {
                    "chapter_sections": len(sections),
                    "disease_entities": len(diseases),
                    "knowledge_nodes": len(updates),
                },
                "summary": {
                    content_class: sum(
                        1
                        for candidate in audit
                        if candidate["content_class"] == content_class
                    )
                    for content_class in (
                        "confirmed_disease",
                        "non_disease_knowledge",
                        "suspected_disease",
                        "invalid",
                    )
                },
                "acceptance": acceptance,
                "disease_entities": diseases,
                "candidates": audit,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    if args.apply and not acceptance["execution_ready"]:
        raise SystemExit(
            "--apply refused: golden disease acceptance has hard failures"
        )

    if args.apply:
        upsert_batches(client, "chapter_sections", sections)
        upsert_batches(client, "disease_entities", diseases)
        update_rows_by_id(client, "knowledge_nodes", updates)

    mode = "applied" if args.apply else "dry-run"
    print(
        f"{mode}: sections={len(sections)} diseases={len(diseases)} "
        f"nodes={len(updates)} audit={args.audit_path}"
    )


if __name__ == "__main__":
    main()
