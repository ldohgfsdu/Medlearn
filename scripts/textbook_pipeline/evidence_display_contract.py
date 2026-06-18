"""Build EV1 frontend display contracts from grounded pipeline artifacts.

The display contract is a frontend-facing view model. It intentionally hides
EV1 pipeline internals behind render-ready fields while preserving evidence
items, page references, and child provenance for audit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


DISPLAY_CONTRACT_VERSION = "ev1-display-contract-0.1.0"


@dataclass(frozen=True)
class DisplayContractOptions:
    merge_adjacent_same_heading: bool = True
    include_evidence_only: bool = True
    group_related_items: bool = True


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _page_label(page_start: Any, page_end: Any) -> str:
    if isinstance(page_start, int) and isinstance(page_end, int):
        return f"p.{page_start}" if page_start == page_end else f"pp.{page_start}-{page_end}"
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


def _evidence_item_from_source(source: dict[str, Any], *, fallback_order: Any = 0) -> dict[str, Any]:
    page_start = source.get("page_start")
    page_end = source.get("page_end") or page_start
    return {
        "artifact_id": _clean_text(source.get("artifact_id")),
        "text": _clean_text(source.get("evidence")),
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


def _organized_view_node(row: dict[str, Any]) -> dict[str, Any]:
    source = _source_span(row)
    page_start = source.get("page_start")
    page_end = source.get("page_end") or page_start
    source_heading = (
        _clean_text(source.get("source_heading"))
        or _clean_text(source.get("normalized_aspect"))
        or _clean_text(row.get("sub_chapter"))
    )
    evidence_item = _evidence_item_from_source(source, fallback_order=row.get("order_num", 0))
    row_id = _clean_text(row.get("id"))
    return {
        "id": f"view-{row_id}",
        "render_type": "normal",
        "publication_state": "organized",
        "quality_badges": ["textbook_grounded", "page_bound"],
        "display": {
            "title": _node_title(row, source),
            "body": _clean_text(row.get("content")),
            "page_label": _page_label(page_start, page_end),
            "source_heading": source_heading,
        },
        "source_node_ids": [row_id] if row_id else [],
        "evidence_items": [evidence_item] if evidence_item["text"] else [],
    }


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
    return right_page <= left_page + 1


def _join_fragments(left: str, right: str) -> str:
    left = _clean_text(left)
    right = _clean_text(right)
    if not left:
        return right
    if not right:
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
)

CLASSIFICATION_STOP_TERMS = (
    "诊断",
    "标准",
    "检查",
    "治疗",
    "预防",
    "评估",
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

TOPIC_LABELS = {
    "classification": "分类",
    "treatment": "治疗",
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


def _explicit_topic_bucket(node: dict[str, Any]) -> str | None:
    text = _topic_text(node)
    if "分类" in text:
        return "classification"
    if any(term in text for term in TREATMENT_TERMS):
        return "treatment"
    return None


def _continuation_topic_bucket(active_bucket: str | None, node: dict[str, Any]) -> str | None:
    if active_bucket != "classification":
        return None
    text = _topic_text(node)
    if any(term in text for term in CLASSIFICATION_STOP_TERMS):
        return None
    if any(term in text for term in CLASSIFICATION_CONTINUATION_TERMS):
        return "classification"
    return "classification"


def _can_group(left: dict[str, Any], right: dict[str, Any], bucket: str) -> bool:
    if left.get("display", {}).get("source_heading") != right.get("display", {}).get("source_heading"):
        return False
    if _first_page(right) > _last_page(left) + 1:
        return False
    if bucket == "classification":
        return True
    if bucket == "treatment":
        return True
    return False


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
    display.update(
        {
            "title": title,
            "body": "",
            "page_label": _page_label(first_page, last_page),
            "items": [
                {
                    "title": _clean_text(node.get("display", {}).get("title")),
                    "body": _clean_text(node.get("display", {}).get("body"))
                    or _clean_text((node.get("evidence_items") or [{}])[0].get("text")),
                    "page_label": _clean_text(node.get("display", {}).get("page_label")),
                    "publication_state": node.get("publication_state"),
                }
                for node in nodes
            ],
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

    def flush() -> None:
        nonlocal current, current_bucket
        if current_bucket and len(current) >= 2:
            grouped.append(_group_node(current_bucket, current))
        else:
            grouped.extend(current)
        current = []
        current_bucket = None

    for node in nodes:
        explicit_bucket = _explicit_topic_bucket(node)
        bucket = explicit_bucket or _continuation_topic_bucket(current_bucket, node)
        if not bucket:
            flush()
            grouped.append(node)
            continue
        if current and current_bucket == bucket and _can_group(current[-1], node, bucket):
            current.append(node)
        else:
            flush()
            current = [node]
            current_bucket = bucket

    flush()
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
    return {
        "id": f"view-evidence-{artifact_id}-{item.get('item_index', 0)}",
        "render_type": "evidence_only",
        "publication_state": "evidence_only",
        "quality_badges": ["page_bound", "conservative_fallback"],
        "display": {
            "title": _clean_text(item.get("title")) or source_heading or "Textbook evidence",
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
    view_nodes = [_organized_view_node(row) for row in nodes if isinstance(row, dict)]
    if options.merge_adjacent_same_heading:
        view_nodes = merge_adjacent_view_nodes(view_nodes)

    if options.include_evidence_only and candidate_payload:
        candidate_items = candidate_payload.get("candidate_items") or []
        if isinstance(candidate_items, list):
            for candidate_order, item in enumerate(candidate_items):
                if not isinstance(item, dict):
                    continue
                ordered_item = {**item, "_candidate_order": candidate_order}
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
