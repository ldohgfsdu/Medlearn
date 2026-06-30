"""Shared guardrails against LLM over-generation and hallucinated nodes."""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

MAX_NODES_PER_CHUNK = 12
MAX_GENERIC_ASPECT_COUNT = 8
MAX_GENERIC_ASPECT_RATIO = 0.35

GENERIC_ASPECT_LABELS = frozenset({
    "治疗方案",
    "治疗措施",
    "治疗药物",
    "治疗目标",
    "使用方法",
    "给药方式",
    "联合用药",
    "作用机制",
    "分类",
})

CONJUNCTION_SPLIT_RE = re.compile(r"[与和及、/]")
CROSS_TOPIC_MARKERS = ("治疗", "合并", "并发", "鉴别", "对比")
UMBRELLA_SECTION_SUFFIXES = ("系统疾病", "感染性疾病", "相关疾病")
CHAPTER_ENTITY_RE = re.compile(r"^第[一二三四五六七八九十百零\d]+章\s*(.+)$")
SELF_REFERENTIAL_EVIDENCE_RE = re.compile(
    r"^(?:抗|吸入型|免疫|生物制剂|支气管).{4,48}可用于"
)
STANDARD_ASPECT_RULES = (
    ("定义", re.compile(r"定义|概念|特点|概述")),
    ("流行病学", re.compile(r"流行病学")),
    ("病因", re.compile(r"病因|危险因素|因素")),
    ("发病机制", re.compile(r"发病机制|病理生理|病理机制|机制|病理|Koch现象")),
    (
        "临床表现",
        re.compile(r"临床表现|临床特征|症状|体征|综合征|血症|血液学异常"),
    ),
    ("鉴别诊断", re.compile(r"鉴别诊断|诊断与鉴别")),
    ("诊断", re.compile(r"诊断|检查|检验|检测|影像|X线|分期")),
    (
        "预防",
        re.compile(r"预防|接种|控制策略|病例报告|病例登记|适用人群"),
    ),
    (
        "治疗",
        re.compile(
            r"治疗|用药|药物|手术|处理原则|激素|疗法|生物制剂|"
            r"替代选择|教育与管理|临床控制期|化疗|放疗|靶向"
        ),
    ),
    ("预后", re.compile(r"预后|并发症|病死率")),
)


def extract_section_entity(section_title: str) -> str:
    title = (section_title or "").strip()
    match = CHAPTER_ENTITY_RE.match(title)
    if match:
        return match.group(1).strip()
    return title


def chapter_entity_aliases(section_entity: str) -> set[str]:
    entity = (section_entity or "").strip()
    aliases = {entity} if entity else set()
    if len(entity) >= 4:
        for size in (4, 3):
            aliases.update(
                entity[index : index + size]
                for index in range(len(entity) - size + 1)
                if len(entity[index : index + size]) >= size
            )
    core = re.sub(r"(病|症|炎|癌|衰竭|高压|过低|不全|疾病)$", "", entity)
    if len(core) >= 2:
        aliases.add(core)
    return {value for value in aliases if len(value) >= 2}


def _entity_matches_section(name: str, aliases: set[str]) -> bool:
    cleaned = normalize_match_text(name)
    if not cleaned:
        return True
    return any(
        cleaned == normalize_match_text(alias)
        or alias in cleaned
        or cleaned in alias
        for alias in aliases
    )


def normalize_match_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def canonicalize_aspect_label(aspect: str) -> str:
    value = (aspect or "").strip()
    for canonical, pattern in STANDARD_ASPECT_RULES:
        if pattern.search(value):
            return canonical
    return value


def evidence_supported_by_source(
    evidence: str,
    source_text: str,
    *,
    min_len: int = 8,
) -> bool:
    evidence = (evidence or "").strip()
    source = normalize_match_text(source_text)
    if len(evidence) < min_len or not source:
        return False
    normalized = normalize_match_text(evidence)
    if normalized in source:
        return True
    if len(normalized) >= 12 and normalized[:12] in source:
        return True
    if len(normalized) >= 16 and normalized[:16] in source:
        return True
    return False


def is_cross_disease_expansion(
    title: str,
    parent_entity: str,
    *,
    section_entity: str | None = None,
) -> bool:
    title = (title or "").strip()
    parent_entity = (parent_entity or "").strip()
    if not section_entity:
        return False
    if section_entity.endswith(UMBRELLA_SECTION_SUFFIXES):
        return False

    aliases = chapter_entity_aliases(section_entity)
    if title.startswith(f"{section_entity}的"):
        return False
    if parent_entity and _entity_matches_section(parent_entity, aliases):
        return False

    if parent_entity and CONJUNCTION_SPLIT_RE.search(parent_entity):
        parts = [part.strip() for part in CONJUNCTION_SPLIT_RE.split(parent_entity) if part.strip()]
        if len(parts) >= 2 and not all(_entity_matches_section(part, aliases) for part in parts):
            return True

    if parent_entity and not _entity_matches_section(parent_entity, aliases):
        if any(marker in title for marker in CROSS_TOPIC_MARKERS):
            return True
        if any(marker in parent_entity for marker in CROSS_TOPIC_MARKERS):
            return True
    return False


def looks_self_referential_evidence(evidence: str, content: str) -> bool:
    evidence = (evidence or "").strip()
    content = (content or "").strip()
    if not evidence or not content:
        return False
    if SELF_REFERENTIAL_EVIDENCE_RE.match(evidence) and evidence in content:
        return True
    return False


def resolve_source_text_for_row(
    row: dict[str, Any],
    *,
    chunk_source_map: dict[str, str] | None = None,
    section_markdown: str = "",
) -> str:
    source_span = row.get("source_span") or {}
    chunk_index = None
    if isinstance(source_span, dict):
        chunk_index = source_span.get("chunk_index")
    if chunk_source_map and chunk_index is not None:
        keyed = chunk_source_map.get(str(chunk_index), "")
        if keyed:
            return keyed
    return section_markdown or ""


def guard_node_row(
    row: dict[str, Any],
    *,
    section_entity: str,
    source_text: str = "",
) -> tuple[bool, str | None]:
    title = str(row.get("title") or "").strip()
    content = str(row.get("content") or "").strip()
    source_span = row.get("source_span") or {}
    parent_entity = ""
    aspect = ""
    evidence = ""
    if isinstance(source_span, dict):
        parent_entity = str(source_span.get("parent_entity") or "").strip()
        aspect = canonicalize_aspect_label(
            str(source_span.get("aspect") or "").strip()
        )
        evidence = str(source_span.get("evidence") or "").strip()

    if not title or len(content) < 15:
        return False, "short_or_empty"

    if is_cross_disease_expansion(title, parent_entity, section_entity=section_entity):
        return False, "cross_disease_expansion"

    if looks_self_referential_evidence(evidence, content):
        return False, "self_referential_evidence"

    if source_text:
        if evidence and not evidence_supported_by_source(evidence, source_text):
            return False, "evidence_not_in_source"
    elif evidence:
        # Legacy cache without chunk text — cannot prove grounding.
        return False, "missing_source_text"

    if aspect in GENERIC_ASPECT_LABELS and title == aspect:
        return False, "aspect_only_title"

    return True, None


def filter_guarded_rows(
    rows: list[dict[str, Any]],
    *,
    section_entity: str,
    chunk_source_map: dict[str, str] | None = None,
    section_markdown: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for row in rows:
        source_text = resolve_source_text_for_row(
            row,
            chunk_source_map=chunk_source_map,
            section_markdown=section_markdown,
        )
        ok, reason = guard_node_row(
            row,
            section_entity=section_entity,
            source_text=source_text,
        )
        if ok:
            kept.append(row)
        else:
            rejected.append({
                "title": row.get("title"),
                "reason": reason,
                "parent_entity": (row.get("source_span") or {}).get("parent_entity"),
            })
    return kept, rejected


def count_generic_aspect_flood(rows: list[dict[str, Any]]) -> tuple[str | None, int]:
    aspect_counter: Counter[str] = Counter()
    for row in rows:
        source_span = row.get("source_span") or {}
        aspect = ""
        if isinstance(source_span, dict):
            aspect = str(source_span.get("aspect") or "").strip()
        if not aspect and row.get("structured_sections"):
            sections = row.get("structured_sections") or []
            if sections and isinstance(sections[0], dict):
                aspect = str(sections[0].get("title") or "").strip()
        if aspect in GENERIC_ASPECT_LABELS:
            aspect_counter[aspect] += 1

    if not aspect_counter:
        return None, 0

    label, count = aspect_counter.most_common(1)[0]
    return label, count


def count_duplicate_parent_aspects(rows: list[dict[str, Any]]) -> int:
    counts: Counter[tuple[str, str, str, str]] = Counter()
    for row in rows:
        source_span = row.get("source_span") or {}
        if not isinstance(source_span, dict):
            continue
        parent_entity = str(source_span.get("parent_entity") or "").strip()
        aspect = str(source_span.get("aspect") or "").strip()
        if not parent_entity or not aspect:
            continue
        counts[(
            str(row.get("chapter") or ""),
            str(row.get("sub_chapter") or ""),
            parent_entity,
            aspect,
        )] += 1
    return sum(count - 1 for count in counts.values() if count > 1)


def assess_guardrails(
    rows: list[dict[str, Any]],
    *,
    section_entity: str,
    chunk_source_map: dict[str, str] | None = None,
    section_markdown: str = "",
    rejections: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inline_rejections: list[dict[str, Any]] = []
    for row in rows:
        source_text = resolve_source_text_for_row(
            row,
            chunk_source_map=chunk_source_map,
            section_markdown=section_markdown,
        )
        ok, reason = guard_node_row(
            row,
            section_entity=section_entity,
            source_text=source_text,
        )
        if not ok:
            inline_rejections.append({
                "title": row.get("title"),
                "reason": reason,
                "parent_entity": (row.get("source_span") or {}).get("parent_entity"),
            })

    if rejections is None:
        rejections = inline_rejections
    else:
        rejections = [*rejections, *inline_rejections]

    total_considered = len(rows) + len(rejections)
    rejection_reasons = Counter(str(item.get("reason") or "unknown") for item in rejections)
    generic_label, generic_count = count_generic_aspect_flood(rows)
    generic_ratio = (generic_count / len(rows)) if rows else 0.0
    duplicate_parent_aspects = count_duplicate_parent_aspects(rows)

    reasons: list[str] = []
    warnings: list[str] = []
    if not rows:
        reasons.append("no_nodes_after_guardrails")
    if rejection_reasons.get("cross_disease_expansion", 0) > 0:
        reasons.append("cross_disease_expansion")
    if rejection_reasons.get("evidence_not_in_source", 0) > 0:
        reasons.append("unsupported_evidence")
    if rejection_reasons.get("missing_source_text", 0) > 0:
        reasons.append("legacy_cache_missing_source")
    if generic_label and generic_count > MAX_GENERIC_ASPECT_COUNT:
        warnings.append("generic_aspect_flood")
    if rows and generic_ratio > MAX_GENERIC_ASPECT_RATIO:
        warnings.append("generic_aspect_ratio_high")
    if generic_count >= 25 or generic_ratio > 0.5:
        reasons.append("generic_aspect_flood")
    if duplicate_parent_aspects:
        reasons.append("duplicate_parent_aspect_nodes")

    if inline_rejections:
        reasons.append("unsafe_nodes_present")

    hard_fail = {
        "no_nodes_after_guardrails",
        "cross_disease_expansion",
        "unsupported_evidence",
        "legacy_cache_missing_source",
        "generic_aspect_flood",
        "duplicate_parent_aspect_nodes",
        "unsafe_nodes_present",
    }
    passed = bool(rows) and not (set(reasons) & hard_fail)
    return {
        "passed": passed,
        "reasons": reasons,
        "metrics": {
            "kept_nodes": len(rows),
            "rejected_nodes": len(rejections),
            "rejection_reasons": dict(rejection_reasons),
            "generic_aspect_label": generic_label,
            "generic_aspect_count": generic_count,
            "generic_aspect_ratio": round(generic_ratio, 3),
            "duplicate_parent_aspect_nodes": duplicate_parent_aspects,
            "total_considered": total_considered,
        },
        "rejections_sample": rejections[:8],
        "warnings": warnings,
    }


def build_chunk_source_map(cache: dict[str, Any] | None) -> dict[str, str]:
    if not cache:
        return {}
    mapping: dict[str, str] = {}
    for key, result in (cache.get("chunks") or {}).items():
        if isinstance(result, dict):
            content = str(result.get("content") or "").strip()
            if content:
                mapping[str(key)] = content
    return mapping
