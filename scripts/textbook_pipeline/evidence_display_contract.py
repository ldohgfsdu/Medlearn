"""Build EV1 frontend display contracts from grounded pipeline artifacts.

The display contract is a frontend-facing view model. It intentionally hides
EV1 pipeline internals behind render-ready fields while preserving evidence
items, page references, and child provenance for audit.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .paragraph_reconstruction import normalize_display_text


DISPLAY_CONTRACT_VERSION = "ev1-display-contract-0.1.0"
MAX_EVIDENCE_ONLY_GROUP_BODY_CHARS = 720


@dataclass(frozen=True)
class DisplayContractOptions:
    merge_adjacent_same_heading: bool = True
    include_evidence_only: bool = True
    group_related_items: bool = True
    apply_display_normalization: bool = True


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = "".join(
        char
        for char in text
        if unicodedata.category(char)[0] != "C" or char in {"\n", "\t"}
    )
    return text.strip()


def _normalize_loose(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).lower()
    return re.sub(r"[\W_]+", "", text, flags=re.UNICODE)


def _loose_contains(haystack: Any, needle: Any) -> bool:
    normalized_haystack = _normalize_loose(haystack)
    normalized_needle = _normalize_loose(needle)
    return bool(normalized_needle and normalized_needle in normalized_haystack)


def _is_generic_source_heading(source_heading: str, item: dict[str, Any]) -> bool:
    heading = _normalize_loose(source_heading)
    if not heading:
        return True
    section_title = _normalize_loose(item.get("_section_title"))
    part_title = _normalize_loose(item.get("_part_title"))
    if heading in {section_title, part_title}:
        return True
    generic_source_headings = {
        _normalize_loose(value)
        for value in (
            "病因",
            "发病机制",
            "病理",
            "临床表现",
            "实验室检查",
            "辅助检查",
            "诊断",
            "鉴别诊断",
            "治疗",
            "药物治疗",
            "肺功能检查",
            "预防",
            "预后",
        )
    }
    if heading in generic_source_headings:
        return True
    if source_heading.replace("\n", "").strip().startswith("本章数字资源"):
        return True
    return bool(re.fullmatch(r"第[一二三四五六七八九十百零〇0-9]+[篇章节].*", source_heading.replace("\n", "")))


def _evidence_only_display_title(
    *,
    evidence: str,
    item: dict[str, Any],
    source_heading: str,
) -> str:
    item_title = _clean_text(item.get("title"))
    if _loose_contains(evidence, item_title):
        return item_title
    if source_heading and not _is_generic_source_heading(source_heading, item):
        return source_heading
    return "原文证据"


def _page_label(page_start: Any, page_end: Any) -> str:
    if isinstance(page_start, int) and isinstance(page_end, int):
        return f"p.{page_start}" if page_start == page_end else f"p.{page_start}-{page_end}"
    if isinstance(page_start, int):
        return f"p.{page_start}"
    return "p.?"


def _first_page(node: dict[str, Any]) -> int:
    evidence_items = node.get("evidence_items") or []
    if not evidence_items:
        return 0
    page_start = evidence_items[0].get("page_start")
    return page_start if isinstance(page_start, int) else 0


def _last_page(node: dict[str, Any]) -> int:
    evidence_items = node.get("evidence_items") or []
    if not evidence_items:
        return _first_page(node)
    page_end = evidence_items[-1].get("page_end") or evidence_items[-1].get("page_start")
    return page_end if isinstance(page_end, int) else _first_page(node)


def _first_source_order(node: dict[str, Any]) -> int:
    evidence_items = node.get("evidence_items") or []
    if not evidence_items:
        return 0
    source_order = evidence_items[0].get("source_order")
    return source_order if isinstance(source_order, int) else 0


def sort_view_nodes_by_source(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        nodes,
        key=lambda node: (
            _first_page(node),
            _first_source_order(node),
            node.get("id") or "",
        ),
    )


def _source_span(row: dict[str, Any]) -> dict[str, Any]:
    source = row.get("source_span") or {}
    return source if isinstance(source, dict) else {}


def _evidence_item_from_source(
    source: dict[str, Any],
    *,
    fallback_order: Any = 0,
    apply_display_normalization: bool = True,
) -> dict[str, Any]:
    page_start = source.get("page_start")
    page_end = source.get("page_end") or page_start
    raw_text = _clean_text(source.get("evidence"))
    display_text = normalize_display_text(raw_text) if apply_display_normalization else raw_text
    return {
        "artifact_id": _clean_text(source.get("artifact_id")),
        "text": display_text,
        "raw_text": raw_text,
        "display_text": display_text,
        "page_start": page_start,
        "page_end": page_end,
        "source_order": source.get("source_order", fallback_order),
    }


def _node_title(row: dict[str, Any], source: dict[str, Any]) -> str:
    return (
        _clean_text(row.get("title"))
        or _clean_text(source.get("source_heading"))
        or "Untitled knowledge node"
    )


def _organized_view_node(
    row: dict[str, Any],
    *,
    apply_display_normalization: bool = True,
) -> dict[str, Any]:
    source = _source_span(row)
    page_start = source.get("page_start")
    page_end = source.get("page_end") or page_start
    source_heading = (
        _clean_text(source.get("source_heading"))
        or _clean_text(source.get("normalized_aspect"))
        or _clean_text(row.get("sub_chapter"))
    )
    evidence_item = _evidence_item_from_source(
        source,
        fallback_order=row.get("order_num", 0),
        apply_display_normalization=apply_display_normalization,
    )
    raw_body = _clean_text(row.get("content"))
    display_body = normalize_display_text(raw_body) if apply_display_normalization else raw_body
    row_id = _clean_text(row.get("id"))
    return {
        "id": f"view-{row_id}",
        "render_type": "normal",
        "publication_state": "organized",
        "quality_badges": ["textbook_grounded", "page_bound"],
        "display": {
            "title": _node_title(row, source),
            "body": display_body,
            "raw_body": raw_body,
            "page_label": _page_label(page_start, page_end),
            "source_heading": source_heading,
        },
        "source_node_ids": [row_id] if row_id else [],
        "evidence_items": [evidence_item] if evidence_item["text"] else [],
    }



LUNG_FUNC_KEYWORDS = {"通气功能", "激发试验", "舒张试验", "BPT", "BDT", "PEF变异率"}

def _distinguishable_lung_func(title_a: str, title_b: str) -> bool:
    kw_a = {k for k in LUNG_FUNC_KEYWORDS if k in title_a}
    kw_b = {k for k in LUNG_FUNC_KEYWORDS if k in title_b}
    return bool(kw_a) and bool(kw_b) and kw_a != kw_b

def _can_merge(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("publication_state") != "organized" or right.get("publication_state") != "organized":
        return False
    if left.get("render_type") not in ("normal", "merged") or right.get("render_type") != "normal":
        return False
    if left.get("display", {}).get("source_heading") != right.get("display", {}).get("source_heading"):
        return False
    if left.get("display", {}).get("title") != right.get("display", {}).get("title"):
        return False
    left_evidence = left.get("evidence_items") or []
    right_evidence = right.get("evidence_items") or []
    if not left_evidence or not right_evidence:
        return False
    left_page = left_evidence[-1].get("page_end")
    right_page = right_evidence[0].get("page_start")
    if not isinstance(left_page, int) or not isinstance(right_page, int):
        return False
    left_title = left.get("display", {}).get("title", "")
    right_title = right.get("display", {}).get("title", "")
    if _distinguishable_lung_func(left_title, right_title):
        return False
    return right_page <= left_page + 1


def _join_fragments(left: str, right: str) -> str:
    left = _clean_text(left)
    right = _clean_text(right)
    if not left:
        return right
    if not right:
        return left
    if _normalize_loose(left) == _normalize_loose(right):
        return left
    if left[-1].isascii() and left[-1].isalnum() and right[0].isascii() and right[0].isalnum():
        return f"{left} {right}"
    return left + right


def _merge_nodes(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    source_node_ids = [
        *(left.get("source_node_ids") or []),
        *(right.get("source_node_ids") or []),
    ]
    evidence_items = [
        *(left.get("evidence_items") or []),
        *(right.get("evidence_items") or []),
    ]
    artifact_ids = [
        item.get("artifact_id")
        for item in evidence_items
        if _clean_text(item.get("artifact_id"))
    ]
    display = dict(left.get("display") or {})
    display["body"] = _join_fragments(display.get("body", ""), right.get("display", {}).get("body", ""))
    display["raw_body"] = _join_fragments(
        display.get("raw_body", display.get("body", "")),
        right.get("display", {}).get("raw_body", right.get("display", {}).get("body", "")),
    )
    if evidence_items:
        first_page = evidence_items[0].get("page_start")
        last_page = evidence_items[-1].get("page_end") or evidence_items[-1].get("page_start")
        display["page_label"] = _page_label(first_page, last_page)
    return {
        **left,
        "id": f"view-merged-{'-'.join(source_node_ids)[:48]}",
        "render_type": "merged",
        "quality_badges": sorted(set([*(left.get("quality_badges") or []), "merged"])),
        "display": display,
        "source_node_ids": source_node_ids,
        "evidence_items": evidence_items,
        "merge": {
            "strategy": "adjacent_same_heading",
            "child_node_ids": source_node_ids,
            "child_artifact_ids": artifact_ids,
        },
    }


def merge_adjacent_view_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for node in nodes:
        if merged and _can_merge(merged[-1], node):
            merged[-1] = _merge_nodes(merged[-1], node)
        else:
            merged.append(node)
    return merged


CLASSIFICATION_CONTINUATION_TERMS = (
    "大叶性",
    "小叶性",
    "间质性",
    "细菌性",
    "非典型",
    "病毒性",
    "真菌",
    "其他病原体",
    "理化因素",
    "患病环境",
    "CAP",
    "HAP",
    "社区获得性",
    "医院获得性",
    "潜伏感染",
    "活动性结核病",
    "病变部位",
    "原发性肺结核",
    "血行播散",
    "继发性肺结核",
    "气管、支气管结核",
    "气管支气管结核",
    "结核性胸膜炎",
    "肺外结核",
    "病原学阳性",
    "病原学阴性",
    "病原学未查",
    "病原学检测阴性",
    "耐药肺结核",
    "单耐药",
    "多耐药",
    "广泛耐药",
    "利福平耐药",
    "初治肺结核",
    "复治肺结核",
    "初治的定义",
    "复治的定义",
    "痰菌检查记录格式",
    "WS 196",
)

CLASSIFICATION_FALSE_START_TITLE_TERMS = (
    "治疗方案分类",
    "菌群分类",
    "传染病分类",
    "肺结核的记录方式",
    "肺结核菌群分类",
)

CLASSIFICATION_SPURIOUS_EVIDENCE_TERMS = (
    "常见病原体感染",
    "肺炎的胸部影像学",
    "SAT）技术",
    "testing，SAT",
)

CLASSIFICATION_STOP_TITLE_TERMS = (
    "诊断原则",
    "鉴别诊断",
    "治疗方案",
    "药物治疗",
    "化学治疗",
    "手术治疗",
    "预防性化学治疗",
    "传染病分类",
    "记录方式",
    "治疗方案分类",
    "菌群分类",
)

TREATMENT_TERMS = (
    "治疗",
    "抗菌",
    "抗感染",
    "药物",
    "用药",
    "停用",
    "疗程",
    "联合用药",
    "氧疗",
    "机械通气",
    "气道管理",
    "ICU",
    "处理",
    "防治",
)

AUXILIARY_EXAM_START_TERMS = (
    "实验室和其他检查",
    "实验室检查",
    "辅助检查",
    "痰嗜酸性粒细胞计数",
    "外周血嗜酸性粒细胞计数",
    "通气功能检测",
    "肺功能检查",
    "支气管激发试验",
    "支气管舒张试验",
    "呼气峰流量",
    "胸部X线",
    "胸部CT",
    "特异性变应原检测",
    "动脉血气分析",
    "呼出气一氧化氮",
    "FeNO",
)

AUXILIARY_EXAM_CONTINUATION_TERMS = (
    *AUXILIARY_EXAM_START_TERMS,
    "肺功能指标",
    "通气功能",
    "嗜酸性粒细胞",
    "气流受限",
    "可逆性",
    "气道高反应性",
    "变应原",
    "IgE",
    "FEV1",
    "FVC",
    "PD20",
    "PC20",
    "PEF",
    "PaCO2",
    "pH",
    "呼吸性碱中毒",
    "呼吸性酸中毒",
    "激素治疗反应",
    "药物的选择",
    "治疗后反应",
    "≥200ml",
)

AUXILIARY_EXAM_STOP_TITLE_TERMS = (
    "诊断标准",
    "诊断方法",
    "典型症状",
    "临床症状",
    "症状和体征",
    "分期",
    "控制水平",
    "严重程度",
    "治疗",
    "管理",
    "预防",
    "预后",
)

TOPIC_LABELS = {
    "classification": "分类",
    "treatment": "治疗",
    "auxiliary_exam": "实验室和其他检查",
    "source_evidence": "原文证据",
}


def _topic_text(node: dict[str, Any]) -> str:
    display = node.get("display") or {}
    evidence = " ".join(_clean_text(item.get("text")) for item in node.get("evidence_items") or [])
    return " ".join(
        [
            _clean_text(display.get("title")),
            _clean_text(display.get("body")),
            evidence,
        ]
    )



AUX_EXAM_SOURCE_HEADINGS = {
    "实验室和其他检查", "肺功能检查", "辅助检查", "实验室检查", "其他检查"
}

def _looks_like_auxiliary_exam_start(node: dict[str, Any]) -> bool:
    display = node.get("display") or {}
    source_heading = _clean_text(display.get("source_heading"))
    if source_heading and source_heading in AUX_EXAM_SOURCE_HEADINGS:
        return True
    title = _clean_text(display.get("title"))
    if any(term in title for term in AUXILIARY_EXAM_START_TERMS):
        return True
    evidence = " ".join(_clean_text(item.get("text")) for item in node.get("evidence_items") or [])
    return "实验室和其他检查" in evidence or "实验室检查" in evidence or "辅助检查" in evidence


def _looks_like_list_item(node: dict[str, Any]) -> bool:
    display = node.get("display") or {}
    candidates = [
        _clean_text(display.get("title")),
        _clean_text(display.get("body")),
        *[_clean_text(item.get("text")) for item in node.get("evidence_items") or []],
    ]
    list_prefix = re.compile(
        r"^\s*(?:"
        r"[0-9]+[\.、．)]|"
        r"[（(][一二三四五六七八九十百零〇]+[）)]|"
        r"[一二三四五六七八九十百零〇]+[、．.]|"
        r"[①②③④⑤⑥⑦⑧⑨⑩]"
        r")"
    )
    return any(list_prefix.match(candidate) for candidate in candidates if candidate)


def _looks_like_classification_member(node: dict[str, Any]) -> bool:
    display = node.get("display") or {}
    title = _clean_text(display.get("title"))
    text = _topic_text(node)
    if title in CLASSIFICATION_FALSE_START_TITLE_TERMS:
        return False
    if ("分类" in title or title.startswith("按")) and not any(
        term in title for term in CLASSIFICATION_STOP_TITLE_TERMS
    ):
        return True
    if _classification_axis_title_from_node(node) or _classification_top_level_title(
        {
            "title": title,
            "body": _clean_text(display.get("body")),
        }
    ):
        return True
    return any(term in text for term in CLASSIFICATION_CONTINUATION_TERMS)


def _classification_should_stop(node: dict[str, Any]) -> bool:
    display = node.get("display") or {}
    title = _clean_text(display.get("title"))
    text = _topic_text(node)
    if _looks_like_classification_member(node):
        return False
    if _classification_axis_title_from_node(node):
        return False
    if any(term in title for term in CLASSIFICATION_STOP_TITLE_TERMS):
        return True
    if any(term in title for term in CLASSIFICATION_FALSE_START_TITLE_TERMS):
        return True
    if re.search(r"诊断原则|鉴别诊断|治疗方案|药物治疗|化学治疗|手术治疗|预防性化学治疗", text):
        return True
    if re.search(r"【肺结核的记录方式】|记录方式", text):
        return True
    if re.search(r"应与.+相鉴别", text):
        return True
    if title in {"治疗", "预防", "预后"}:
        return True
    return False


def _looks_like_classification_explicit_start(node: dict[str, Any]) -> bool:
    text = _topic_text(node)
    title = _clean_text((node.get("display") or {}).get("title"))
    if title in CLASSIFICATION_FALSE_START_TITLE_TERMS:
        return False
    if title in CLASSIFICATION_STOP_TITLE_TERMS:
        return False
    display_item = {
        "title": title,
        "body": _clean_text((node.get("display") or {}).get("body")),
    }
    if _classification_intro_item(display_item):
        return True
    if re.search(r"分类标准|病原学检测阴性肺结核", text):
        return True
    if (
        re.search(r"结核分枝杆菌潜伏感染者|（一）.*潜伏感染", text)
        and not re.search(r"预防性治疗|治疗方案|推荐使用", text)
    ):
        return True
    if title.startswith("按") and "分类" in title:
        return True
    if title.endswith("耐药分类"):
        return True
    if title in {"肺结核的病变部位", "肺结核的耐药分类"}:
        return True
    return False


def _classification_group_has_tb_intro(nodes: list[dict[str, Any]]) -> bool:
    for node in nodes:
        display_item = _display_item_from_node(node)
        if _classification_intro_item(display_item):
            return True
        if "WS 196" in _topic_text(node):
            return True
        title = _clean_text((node.get("display") or {}).get("title"))
        if title == "结核病的分类标准":
            return True
    return False


def _classification_spurious_evidence_only(node: dict[str, Any]) -> bool:
    if node.get("publication_state") != "evidence_only":
        return False
    text = _topic_text(node)
    if any(term in text for term in CLASSIFICATION_SPURIOUS_EVIDENCE_TERMS):
        return True
    if re.search(r"肺炎|病原体感染治疗", text) and "结核" not in text:
        return True
    return False


def _classification_evidence_only_continues(node: dict[str, Any]) -> bool:
    if _classification_spurious_evidence_only(node):
        return False
    text = _topic_text(node)
    if any(term in text for term in CLASSIFICATION_CONTINUATION_TERMS):
        return True
    if re.search(r"结核分枝杆菌|γ-干扰素|γ- 干扰素", text):
        return True
    return False


def _classification_in_tb_band(node: dict[str, Any]) -> bool:
    order = _first_source_order(node)
    page = _first_page(node)
    if 156 <= order <= 229:
        return True
    return page is not None and 106 <= page <= 109


def _classification_tb_section_continues(
    node: dict[str, Any],
    current: list[dict[str, Any]],
) -> bool:
    if not current or not _classification_group_has_tb_intro(current):
        return False
    if _classification_spurious_evidence_only(node):
        return False
    page = _first_page(node)
    if page is not None and not (106 <= page <= 109):
        return False
    order = _first_source_order(node)
    if order >= 230:
        return False
    title = _clean_text((node.get("display") or {}).get("title"))
    text = _topic_text(node)
    if title in CLASSIFICATION_FALSE_START_TITLE_TERMS:
        return False
    if re.search(r"【肺结核的记录方式】", text):
        return False
    if re.search(r"应与.+相鉴别", text):
        return False
    if node.get("publication_state") == "evidence_only":
        return _classification_evidence_only_continues(node)
    return 156 <= order <= 229


NON_TREATMENT_GENERIC_SOURCE_HEADINGS = {
    "病因",
    "发病机制",
    "病理",
    "临床表现",
    "实验室检查",
    "辅助检查",
    "诊断",
    "鉴别诊断",
    "预防",
    "预后",
}


def _explicit_topic_bucket(node: dict[str, Any]) -> str | None:
    text = _topic_text(node)
    title = _clean_text((node.get("display") or {}).get("title"))
    if _looks_like_classification_explicit_start(node):
        return "classification"
    if _looks_like_auxiliary_exam_start(node):
        return "auxiliary_exam"
    source_heading = _clean_text((node.get("display") or {}).get("source_heading"))
    if node.get("publication_state") == "evidence_only":
        display = node.get("display") or {}
        title = _clean_text(display.get("title"))
        if (
            title
            and title not in {"原文证据", "Untitled knowledge node"}
            and any(term in text for term in TREATMENT_TERMS)
            and not _looks_like_classification_member(node)
            and source_heading not in NON_TREATMENT_GENERIC_SOURCE_HEADINGS
        ):
            return "treatment"
        return None
    if (
        any(term in text for term in TREATMENT_TERMS)
        and source_heading not in NON_TREATMENT_GENERIC_SOURCE_HEADINGS
    ):
        return "treatment"
    return None


def _continuation_topic_bucket(
    active_bucket: str | None,
    node: dict[str, Any],
    current: list[dict[str, Any]] | None = None,
) -> str | None:
    if active_bucket == "auxiliary_exam":
        title = _clean_text((node.get("display") or {}).get("title"))
        source_heading = _clean_text((node.get("display") or {}).get("source_heading"))
        text = _topic_text(node)
        if node.get("publication_state") == "evidence_only":
            if (source_heading and source_heading in AUX_EXAM_SOURCE_HEADINGS) or any(
                term in text for term in AUXILIARY_EXAM_CONTINUATION_TERMS
            ):
                return "auxiliary_exam"
            return None
        if source_heading and source_heading in AUX_EXAM_SOURCE_HEADINGS:
            return "auxiliary_exam"
        if any(term in text for term in AUXILIARY_EXAM_CONTINUATION_TERMS):
            return "auxiliary_exam"
        if any(term in title for term in AUXILIARY_EXAM_STOP_TITLE_TERMS):
            return None
        if _looks_like_list_item(node):
            return "auxiliary_exam"
        return None

    if active_bucket != "classification":
        return None
    if current and _classification_tb_section_continues(node, current):
        return "classification"
    if _classification_should_stop(node):
        return None
    if _looks_like_classification_member(node):
        return "classification"
    if _looks_like_list_item(node):
        return "classification"
    return None


def _can_group(left: dict[str, Any], right: dict[str, Any], bucket: str) -> bool:
    if left.get("display", {}).get("source_heading") != right.get("display", {}).get("source_heading"):
        return False
    if _first_page(right) > _last_page(left) + 1:
        return False
    if bucket == "classification":
        if _classification_spurious_evidence_only(right):
            return False
        left_order = _first_source_order(left)
        right_order = _first_source_order(right)
        if isinstance(left_order, int) and isinstance(right_order, int):
            if right_order < left_order and not (
                _classification_in_tb_band(left) and _classification_in_tb_band(right)
            ):
                return False
            if right_order - left_order > 15 and not (
                _classification_in_tb_band(left) and _classification_in_tb_band(right)
            ):
                return False
        return True
    if bucket == "treatment":
        return True
    if bucket == "auxiliary_exam":
        return True
    return False


def _is_contiguous_evidence_only(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    max_order_gap: int = 1,
) -> bool:
    if left.get("publication_state") != "evidence_only" or right.get("publication_state") != "evidence_only":
        return False
    if left.get("display", {}).get("source_heading") != right.get("display", {}).get("source_heading"):
        return False
    if _first_page(right) > _last_page(left) + 1:
        return False
    left_order = _first_source_order(left)
    right_order = _first_source_order(right)
    return isinstance(left_order, int) and isinstance(right_order, int) and left_order <= right_order <= left_order + max_order_gap


def _evidence_only_topic_bucket(
    current_bucket: str | None,
    node: dict[str, Any],
    current: list[dict[str, Any]] | None = None,
) -> str | None:
    if node.get("publication_state") != "evidence_only":
        return None
    if current_bucket == "classification":
        if _classification_spurious_evidence_only(node):
            return "source_evidence"
        if not _classification_evidence_only_continues(node):
            return "source_evidence"
        return "classification"
    if current_bucket == "treatment":
        node_heading = _clean_text((node.get("display") or {}).get("source_heading"))
        first_heading = (
            _clean_text((current[0].get("display") or {}).get("source_heading"))
            if current
            else ""
        )
        if node_heading and first_heading and node_heading != first_heading:
            return "source_evidence"
        return "treatment"
    if current_bucket == "auxiliary_exam":
        source_heading = _clean_text((node.get("display") or {}).get("source_heading"))
        text = _topic_text(node)
        if (source_heading and source_heading in AUX_EXAM_SOURCE_HEADINGS) or any(
            term in text for term in AUXILIARY_EXAM_CONTINUATION_TERMS
        ):
            return "auxiliary_exam"
        return "source_evidence"
    return "source_evidence"


def _join_evidence_texts(nodes: list[dict[str, Any]]) -> str:
    fragments = [
        _clean_text(evidence.get("text"))
        for node in nodes
        for evidence in (node.get("evidence_items") or [])
        if _clean_text(evidence.get("text"))
    ]
    text = ""
    for fragment in fragments:
        text = _join_fragments(text, fragment)
    return text


def _evidence_only_group_display_items(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current_nodes: list[dict[str, Any]] = []
    current_body = ""

    def flush() -> None:
        nonlocal current_nodes, current_body
        if not current_nodes:
            return
        first = current_nodes[0]
        title = (
            _clean_text(first.get("display", {}).get("title"))
            if not items
            else "原文证据"
        )
        items.append(
            {
                "title": title or "原文证据",
                "body": current_body,
                "page_label": _page_label(_first_page(first), _last_page(current_nodes[-1])),
                "publication_state": "evidence_only",
            }
        )
        current_nodes = []
        current_body = ""

    for node in nodes:
        fragment = _join_evidence_texts([node])
        if not fragment:
            continue
        candidate_body = _join_fragments(current_body, fragment)
        if current_nodes and len(candidate_body) > MAX_EVIDENCE_ONLY_GROUP_BODY_CHARS:
            flush()
            candidate_body = fragment
        current_nodes.append(node)
        current_body = candidate_body

    flush()
    return items


def _group_display_items(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if nodes and all(node.get("publication_state") == "evidence_only" for node in nodes):
        return _evidence_only_group_display_items(nodes)

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in nodes:
        display = node.get("display", {})
        body = _clean_text(display.get("body")) or _clean_text((node.get("evidence_items") or [{}])[0].get("text"))
        if node.get("publication_state") == "evidence_only":
            title = "原文证据"
        else:
            title = _clean_text(display.get("title"))
        item = {
            "title": title,
            "body": body,
            "page_label": _clean_text(display.get("page_label")),
            "publication_state": node.get("publication_state"),
        }
        key = _normalize_loose(body) or _normalize_loose(item["title"])
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        items.append(item)
    return items


def _display_item_from_node(node: dict[str, Any]) -> dict[str, Any]:
    display = node.get("display", {})
    body = _clean_text(display.get("body")) or _clean_text((node.get("evidence_items") or [{}])[0].get("text"))
    artifact_ids = [
        _clean_text(item.get("artifact_id"))
        for item in node.get("evidence_items") or []
        if _clean_text(item.get("artifact_id"))
    ]
    return {
        "title": _clean_text(display.get("title")),
        "body": body,
        "page_label": _clean_text(display.get("page_label")),
        "publication_state": node.get("publication_state"),
        "evidence_artifact_ids": artifact_ids,
    }


def _item_text(item: dict[str, Any]) -> str:
    return " ".join(
        [
            _clean_text(item.get("title")),
            _clean_text(item.get("body")),
        ]
    )


def _auxiliary_top_title(item: dict[str, Any]) -> str | None:
    text = _item_text(item)
    if "痰嗜酸性粒细胞计数" in text:
        return "痰嗜酸性粒细胞计数"
    if "外周血嗜酸性粒细胞计数" in text or "外周血嗜酸性粒细胞增高" in text:
        return "外周血嗜酸性粒细胞计数"
    if re.search(r"胸部X\s*线|胸部CT|胸部X线/CT检查|胸部X线/CT", text):
        return "胸部X线/CT检查"
    if re.search(r"特异性变应原检测|变应原特异性IgE|血清总IgE|变应原皮肤点刺|变应原激发试验", text):
        return "特异性变应原检测"
    if re.search(r"动脉血气分析|PaCO2|呼吸性碱中毒|呼吸性酸中毒", text):
        return "动脉血气分析"
    if "呼出气一氧化氮" in text or "FeNO" in text:
        return "呼出气一氧化氮（FeNO）检测"
    return None


def _auxiliary_lung_function_title(item: dict[str, Any]) -> str | None:
    text = _item_text(item)
    if re.search(r"通气功能检测|FVC|FEV1/FVC|气流受限|阻塞性通气功能障碍", text):
        return "通气功能检测"
    if re.search(r"支气管激发试验|BPT|PD20|PC20|气道高反应性|FEV1\s*下降≥?20", text):
        return "支气管激发试验（BPT）"
    if re.search(r"PEF|呼气峰流量|昼夜变异率|周变异率", text):
        return "呼气峰流量（PEF）及其变异率测定"
    if re.search(r"支气管舒张试验|BDT|支气管扩张剂|增加≥?12|增加≥?200ml|可逆性的气道阻塞", text):
        return "支气管舒张试验（BDT）"
    return None


def _merge_display_item(base: dict[str, Any], addition: dict[str, Any]) -> None:
    base["body"] = _join_fragments(_clean_text(base.get("body")), _clean_text(addition.get("body")))
    page_label = _clean_text(addition.get("page_label"))
    if page_label and page_label not in _clean_text(base.get("page_label")):
        base["page_label"] = _page_label_from_item_labels([_clean_text(base.get("page_label")), page_label])
    artifact_ids = list(dict.fromkeys([
        *(_clean_text(item) for item in base.get("evidence_artifact_ids") or []),
        *(_clean_text(item) for item in addition.get("evidence_artifact_ids") or []),
    ]))
    if artifact_ids:
        base["evidence_artifact_ids"] = artifact_ids
    base["publication_state"] = (
        "evidence_only"
        if base.get("publication_state") == "evidence_only" and addition.get("publication_state") == "evidence_only"
        else "organized"
    )


def _page_label_from_item_labels(labels: list[str]) -> str:
    page_numbers: list[int] = []
    for label in labels:
        for match in re.finditer(r"p\.(\d+)(?:-(\d+))?", label or ""):
            page_numbers.append(int(match.group(1)))
            page_numbers.append(int(match.group(2) or match.group(1)))
    if page_numbers:
        return _page_label(min(page_numbers), max(page_numbers))
    cleaned = [label for label in labels if label]
    return "、".join(dict.fromkeys(cleaned))


def _append_child(parent: dict[str, Any], child: dict[str, Any]) -> None:
    children = parent.setdefault("children", [])
    children.append(child)
    parent["page_label"] = _page_label_from_item_labels([parent.get("page_label", ""), child.get("page_label", "")])


def _replace_evidence_only_shell_with_organized(existing: dict[str, Any], seed: dict[str, Any], title: str) -> None:
    evidence_child = dict(existing)
    existing.clear()
    existing.update(seed)
    existing["title"] = title
    previous_children = evidence_child.pop("children", [])
    evidence_child["children"] = previous_children
    _append_child(existing, evidence_child)


def _get_or_create_auxiliary_item(items: list[dict[str, Any]], title: str, seed: dict[str, Any]) -> dict[str, Any]:
    for item in items:
        if item.get("title") == title:
            if seed.get("publication_state") == "evidence_only":
                _append_child(item, seed)
            elif item.get("publication_state") == "evidence_only":
                _replace_evidence_only_shell_with_organized(item, seed, title)
            else:
                _merge_display_item(item, seed)
            return item
    item = dict(seed)
    item["title"] = title
    items.append(item)
    return item


def _get_or_create_lung_function(items: list[dict[str, Any]], seed: dict[str, Any]) -> dict[str, Any]:
    for item in items:
        if item.get("title") == "肺功能检查":
            return item
    item = {
        "title": "肺功能检查",
        "body": "",
        "page_label": _clean_text(seed.get("page_label")),
        "publication_state": "organized",
        "evidence_artifact_ids": [],
        "children": [],
    }
    items.append(item)
    return item


def _get_or_create_auxiliary_child(parent: dict[str, Any], title: str, seed: dict[str, Any]) -> dict[str, Any]:
    children = parent.setdefault("children", [])
    for child in children:
        if child.get("title") == title:
            if seed.get("publication_state") == "evidence_only":
                _append_child(child, seed)
            elif child.get("publication_state") == "evidence_only":
                _replace_evidence_only_shell_with_organized(child, seed, title)
            else:
                _merge_display_item(child, seed)
            parent["page_label"] = _page_label_from_item_labels([parent.get("page_label", ""), child.get("page_label", "")])
            return child
    child = dict(seed)
    child["title"] = title
    _append_child(parent, child)
    return child


def _auxiliary_exam_display_items(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    current_top: dict[str, Any] | None = None
    current_top_allows_continuation = False
    current_lung_child: dict[str, Any] | None = None

    for node in nodes:
        item = _display_item_from_node(node)
        lung_title = _auxiliary_lung_function_title(item)
        if lung_title:
            lung_function = _get_or_create_lung_function(items, item)
            current_top = lung_function
            current_top_allows_continuation = True
            current_lung_child = _get_or_create_auxiliary_child(lung_function, lung_title, item)
            continue

        top_title = _auxiliary_top_title(item)
        if top_title:
            current_top = _get_or_create_auxiliary_item(items, top_title, item)
            current_top_allows_continuation = True
            current_lung_child = None
            continue

        if current_lung_child and item.get("publication_state") == "evidence_only":
            _append_child(current_lung_child, item)
        elif current_lung_child:
            _merge_display_item(current_lung_child, item)
        elif current_top and current_top_allows_continuation and item.get("publication_state") == "evidence_only":
            _append_child(current_top, item)
        else:
            items.append(item)
            current_top = item
            current_top_allows_continuation = False

    return items


def _classification_axis_title_from_node(node: dict[str, Any]) -> str | None:
    display = node.get("display") or {}
    return _classification_axis_title(
        {
            "title": _clean_text(display.get("title")),
            "body": _clean_text(display.get("body"))
            or _clean_text((node.get("evidence_items") or [{}])[0].get("text")),
        }
    )


def _classification_axis_title(item: dict[str, Any]) -> str | None:
    text = _item_text(item)
    title = _clean_text(item.get("title"))
    if title == "肺结核的病变部位" or re.search(r"按照病变部位", text):
        return "按病变部位分类"
    if title.startswith("按") and "分类" in title:
        return title
    if title.endswith("耐药分类") or re.search(r"按耐药状况分类", text):
        return "按耐药状况分类"
    if re.search(r"^\d+\.\s*按[^。；;]+分类", text):
        match = re.search(r"按[^。；;]+分类", text)
        return match.group(0) if match else None
    return None


def _classification_is_tb_context(items: list[dict[str, Any]]) -> bool:
    return any(
        re.search(r"潜伏感染|活动性结核|WS 196|按病变部位|结核分枝杆菌", _item_text(item))
        for item in items
    )


def _classification_intro_item(item: dict[str, Any]) -> bool:
    text = _item_text(item)
    title = _clean_text(item.get("title"))
    return bool(re.search(r"分类标准|分类依据|可按不同", text)) or title.endswith("的分类")


def _classification_top_level_title(item: dict[str, Any]) -> str | None:
    text = _item_text(item)
    title = _clean_text(item.get("title"))
    if re.search(r"[（(]一[）)].*潜伏感染|结核分枝杆菌潜伏感染|潜伏感染者", text):
        return "结核分枝杆菌潜伏感染者"
    if re.search(r"[（(]三[）)].*病原学检测阴性肺结核", text):
        return "病原学检测阴性肺结核"
    if re.search(r"病原学检测阴性肺结核", title):
        return "病原学检测阴性肺结核"
    if re.search(r"[（(]二[）)].*活动性结核|活动性结核病", text) or (
        re.search(r"活动性结核", title) and "定义" in title
    ):
        return "活动性结核病"
    if re.search(r"活动性结核", title):
        return "活动性结核病"
    return None


def _display_classification_axis_label(title: str) -> str:
    if title in {"按解剖分类", "按病因分类", "按患病环境分类"}:
        return title.replace("按", "", 1)
    return title


def _classification_site_subtype_title(item: dict[str, Any]) -> str | None:
    text = _item_text(item)
    title = _clean_text(item.get("title"))
    if re.search(r"原发性肺结核", text):
        return "原发性肺结核"
    if re.search(r"血行播散性肺结核", text) and "鉴别" not in text:
        return "血行播散性肺结核"
    if re.search(r"继发性肺结核", text) and "记录" not in text:
        return "继发性肺结核"
    if re.search(r"气管、支气管结核|气管支气管结核", text):
        return "气管、支气管结核"
    if title == "结核性胸膜炎" or re.search(r"结核性胸膜炎", text):
        return "结核性胸膜炎"
    if re.search(r"肺外结核", text):
        return "肺外结核"
    if re.search(r"大叶性", text):
        return "大叶性（肺泡性）肺炎"
    if re.search(r"小叶性|支气管性", text):
        return "小叶性（支气管性）肺炎"
    if re.search(r"间质性肺炎", text):
        return "间质性肺炎"
    if re.search(r"社区获得性", text):
        return "社区获得性肺炎"
    if re.search(r"医院获得性", text):
        return "医院获得性肺炎"
    if re.search(r"细菌性肺炎", text):
        return "细菌性肺炎"
    return None


def _classification_treatment_history_title(item: dict[str, Any]) -> str | None:
    text = _item_text(item)
    title = _clean_text(item.get("title"))
    if re.search(r"初治", text) and "复治" not in title:
        return "初治肺结核"
    if re.search(r"复治", text):
        return "复治肺结核"
    return None


def _is_classification_axis_heading(item: dict[str, Any], axis_title: str) -> bool:
    title = _clean_text(item.get("title"))
    normalized_title = title.replace("按", "")
    normalized_axis = axis_title.replace("按", "")
    return title == axis_title or normalized_title == normalized_axis


def _get_or_create_classification_root(
    roots: list[dict[str, Any]],
    title: str,
    seed: dict[str, Any],
) -> dict[str, Any]:
    for item in roots:
        if item.get("title") == title:
            _merge_display_item(item, seed)
            return item
    item = dict(seed)
    item["title"] = title
    item["children"] = []
    roots.append(item)
    return item


def _get_or_create_classification_child(
    parent: dict[str, Any],
    title: str,
    seed: dict[str, Any],
) -> dict[str, Any]:
    children = parent.setdefault("children", [])
    for child in children:
        if child.get("title") == title:
            if seed.get("publication_state") == "evidence_only":
                _append_child(child, seed)
            elif child.get("publication_state") == "evidence_only":
                _replace_evidence_only_shell_with_organized(child, seed, title)
            else:
                _merge_display_item(child, seed)
            parent["page_label"] = _page_label_from_item_labels(
                [parent.get("page_label", ""), child.get("page_label", "")]
            )
            return child
    child = dict(seed)
    child["title"] = title
    child["children"] = child.get("children") or []
    _append_child(parent, child)
    return child


def _ensure_active_tb_top(roots: list[dict[str, Any]], seed: dict[str, Any]) -> dict[str, Any]:
    for item in roots:
        if item.get("title") == "活动性结核病":
            return item
    return _get_or_create_classification_root(roots, "活动性结核病", seed)


def _classification_display_items(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered_nodes = [node for node in nodes if not _classification_spurious_evidence_only(node)]
    flat_items = [_display_item_from_node(node) for node in filtered_nodes]
    tb_context = _classification_is_tb_context(flat_items)
    roots: list[dict[str, Any]] = []
    current_top: dict[str, Any] | None = None
    current_axis: dict[str, Any] | None = None
    current_leaf: dict[str, Any] | None = None

    for item in flat_items:
        if _classification_intro_item(item):
            continue

        top_title = _classification_top_level_title(item) if tb_context else None
        if top_title:
            current_top = _get_or_create_classification_root(roots, top_title, item)
            current_axis = None
            current_leaf = current_top
            continue

        axis_title = _classification_axis_title(item)
        if axis_title:
            if tb_context:
                parent = current_top or _ensure_active_tb_top(roots, item)
                current_top = parent
                current_axis = _get_or_create_classification_child(parent, axis_title, item)
            else:
                current_top = None
                current_axis = _get_or_create_classification_root(
                    roots,
                    _display_classification_axis_label(axis_title),
                    item,
                )
            current_leaf = current_axis
            if _is_classification_axis_heading(item, axis_title):
                continue
            continue

        subtype_title = _classification_site_subtype_title(item)
        if subtype_title and tb_context and subtype_title.endswith("肺炎"):
            subtype_title = None
        if subtype_title and current_axis:
            current_leaf = _get_or_create_classification_child(current_axis, subtype_title, item)
            continue

        if current_axis and "既往治疗史" in _clean_text(current_axis.get("title")):
            history_title = _classification_treatment_history_title(item)
            if history_title:
                current_leaf = _get_or_create_classification_child(current_axis, history_title, item)
                continue

        if current_leaf:
            if item.get("publication_state") == "evidence_only":
                _append_child(current_leaf, item)
            else:
                _merge_display_item(current_leaf, item)
            continue

        roots.append(dict(item))
        current_leaf = roots[-1]
        current_top = None
        current_axis = None

    useful_roots = [
        item
        for item in roots
        if _clean_text(item.get("body"))
        or item.get("children")
        or item.get("publication_state") == "evidence_only"
    ]
    has_tree = any(item.get("children") for item in useful_roots)
    if has_tree or (tb_context and len(useful_roots) >= 2):
        return useful_roots
    return flat_items


def _group_node(bucket: str, nodes: list[dict[str, Any]]) -> dict[str, Any]:
    source_node_ids = [node_id for node in nodes for node_id in (node.get("source_node_ids") or [])]
    evidence_items = [item for node in nodes for item in (node.get("evidence_items") or [])]
    artifact_ids = [
        item.get("artifact_id")
        for item in evidence_items
        if _clean_text(item.get("artifact_id"))
    ]
    quality_badges = sorted(
        set(
            [
                badge
                for node in nodes
                for badge in (node.get("quality_badges") or [])
            ]
            + ["grouped", f"group:{bucket}"]
        )
    )
    publication_state = (
        "evidence_only"
        if all(node.get("publication_state") == "evidence_only" for node in nodes)
        else "organized"
    )
    first = nodes[0]
    display = dict(first.get("display") or {})
    first_page = _first_page(first)
    last_page = _last_page(nodes[-1])
    title = _clean_text(display.get("title")) or TOPIC_LABELS[bucket]
    if bucket == "treatment" and "治疗" not in title:
        title = "治疗"
    if bucket == "auxiliary_exam":
        title = TOPIC_LABELS[bucket]
    if bucket == "classification":
        first_title = _clean_text(display.get("title"))
        if "分类" in first_title:
            title = first_title
        else:
            title = TOPIC_LABELS[bucket]
    if bucket == "classification":
        display_items = _classification_display_items(nodes)
    elif bucket == "auxiliary_exam":
        display_items = _auxiliary_exam_display_items(nodes)
    else:
        display_items = _group_display_items(nodes)
    intro_body = ""
    if bucket == "classification" and nodes:
        intro_body = _join_evidence_texts([nodes[0]]) if _classification_intro_item(_display_item_from_node(nodes[0])) else ""
    display.update(
        {
            "title": title,
            "body": intro_body,
            "page_label": _page_label(first_page, last_page),
            "items": display_items,
        }
    )
    return {
        "id": f"view-grouped-{bucket}-{'-'.join((node.get('id') or '') for node in nodes)[:48]}",
        "render_type": "grouped",
        "publication_state": publication_state,
        "quality_badges": quality_badges,
        "display": display,
        "source_node_ids": source_node_ids,
        "evidence_items": evidence_items,
        "group": {
            "strategy": f"adjacent_{bucket}",
            "topic": bucket,
            "child_view_ids": [node.get("id") for node in nodes],
            "child_node_ids": source_node_ids,
            "child_artifact_ids": artifact_ids,
        },
    }


def group_related_view_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_bucket: str | None = None
    has_organized = any(n.get("publication_state") == "organized" for n in nodes)

    def flush() -> None:
        nonlocal current, current_bucket
        if current_bucket and len(current) >= 2:
            grouped.append(_group_node(current_bucket, current))
        else:
            grouped.extend(current)
        current = []
        current_bucket = None

    for node in nodes:
        if current_bucket == "classification" and current and _classification_group_has_tb_intro(current):
            page = _first_page(node)
            order = _first_source_order(node)
            if (
                page is not None
                and 106 <= page <= 109
                and not (156 <= order <= 229)
            ):
                grouped.append(node)
                continue
        if current_bucket == "classification" and (
            _classification_spurious_evidence_only(node)
            or (
                node.get("publication_state") == "evidence_only"
                and current
                and _first_source_order(node) > max(_first_source_order(item) for item in current) + 3
            )
        ):
            grouped.append(node)
            continue
        continuation_bucket = _continuation_topic_bucket(current_bucket, node, current)
        explicit_bucket = _explicit_topic_bucket(node)
        bucket = continuation_bucket or explicit_bucket or _evidence_only_topic_bucket(current_bucket, node, current)
        if not bucket:
            flush()
            grouped.append(node)
            continue
        contiguous_max_gap = 5 if (has_organized and bucket == "source_evidence") else 1
        if current and current_bucket == bucket and (
            _can_group(current[-1], node, bucket)
            or (
                bucket in {"treatment", "auxiliary_exam", "classification", "source_evidence"}
                and _is_contiguous_evidence_only(current[-1], node, max_order_gap=contiguous_max_gap)
            )
        ):
            current.append(node)
        else:
            flush()
            current = [node]
            current_bucket = bucket

    flush()
    # A repeated display title is not structural evidence that two groups share
    # the same content identity. In particular, treatment headings repeat for
    # adjacent diseases. Looking back across an intervening node used to merge
    # those independent source runs and could bind high-risk evidence to the
    # wrong disease. Only the contiguous grouping pass above is authoritative.
    return grouped


def _evidence_only_view_node(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("verification_state") != "needs_review":
        return None
    evidence = _clean_text(item.get("evidence"))
    artifact_id = _clean_text(item.get("artifact_id"))
    page_start = item.get("page_start")
    page_end = item.get("page_end") or page_start
    if not evidence or not artifact_id:
        return None
    source_heading = _clean_text(item.get("source_heading")) or _clean_text(item.get("aspect"))
    display_title = _evidence_only_display_title(
        evidence=evidence,
        item=item,
        source_heading=source_heading,
    )
    return {
        "id": f"view-evidence-{artifact_id}-{item.get('item_index', 0)}",
        "render_type": "evidence_only",
        "publication_state": "evidence_only",
        "quality_badges": ["page_bound", "conservative_fallback"],
        "display": {
            "title": display_title,
            "body": "",
            "page_label": _page_label(page_start, page_end),
            "source_heading": source_heading,
        },
        "source_node_ids": [],
        "evidence_items": [
            {
                "artifact_id": artifact_id,
                "text": evidence,
                "page_start": page_start,
                "page_end": page_end,
                "source_order": item.get("source_order", item.get("_candidate_order", item.get("item_index", 0))),
            }
        ],
    }


def build_display_contract_payload(
    normalized_payload: dict[str, Any],
    *,
    candidate_payload: dict[str, Any] | None = None,
    options: DisplayContractOptions | None = None,
) -> dict[str, Any]:
    """Build a frontend display contract from EV1 normalized/candidate caches."""
    options = options or DisplayContractOptions()
    nodes = normalized_payload.get("nodes") or []
    if not isinstance(nodes, list):
        nodes = []
    view_nodes = [
        _organized_view_node(
            row,
            apply_display_normalization=options.apply_display_normalization,
        )
        for row in nodes
        if isinstance(row, dict)
    ]
    if options.merge_adjacent_same_heading:
        view_nodes = merge_adjacent_view_nodes(view_nodes)

    if options.include_evidence_only and candidate_payload:
        candidate_items = candidate_payload.get("candidate_items") or []
        if isinstance(candidate_items, list):
            for candidate_order, item in enumerate(candidate_items):
                if not isinstance(item, dict):
                    continue
                ordered_item = {
                    **item,
                    "_candidate_order": candidate_order,
                    "_part_title": candidate_payload.get("part_title"),
                    "_section_title": candidate_payload.get("section_title"),
                }
                view_node = _evidence_only_view_node(ordered_item)
                if view_node:
                    view_nodes.append(view_node)

    view_nodes = sort_view_nodes_by_source(view_nodes)
    if options.group_related_items:
        view_nodes = group_related_view_nodes(view_nodes)

    return {
        "version": DISPLAY_CONTRACT_VERSION,
        "textbook_id": normalized_payload.get("textbook_id"),
        "part_title": normalized_payload.get("part_title"),
        "section_title": normalized_payload.get("section_title"),
        "source_path": normalized_payload.get("source_path"),
        "node_count": len(view_nodes),
        "nodes": view_nodes,
        "summary": {
            "organized": sum(1 for node in view_nodes if node.get("publication_state") == "organized"),
            "evidence_only": sum(1 for node in view_nodes if node.get("publication_state") == "evidence_only"),
            "merged": sum(1 for node in view_nodes if node.get("render_type") == "merged"),
            "grouped": sum(1 for node in view_nodes if node.get("render_type") == "grouped"),
        },
    }
