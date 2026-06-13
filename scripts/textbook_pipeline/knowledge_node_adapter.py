"""Adapt pipeline outputs to the App-aligned knowledge_nodes schema."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from textbook_identity import INTERNAL_MEDICINE_10, TextbookIdentity
from textbook_pipeline.ingestion_contract import ADAPTER_VERSION, DEPRECATION_NOTICE

SECTION_FIELD_LABELS: dict[str, str] = {
    "definition": "定义",
    "epidemiology": "流行病学",
    "etiology_and_pathogenesis": "病因与发病机制",
    "pathogenesis": "发病机制",
    "clinical_manifestations": "临床表现",
    "diagnostic_criteria": "诊断标准",
    "auxiliary_examinations": "辅助检查",
    "differential_diagnosis": "鉴别诊断",
    "treatment_principles": "治疗原则",
    "prognosis": "预后",
    "prevention": "预防",
    "mechanism_of_action": "作用机制",
    "indications": "适应证",
    "adverse_reactions": "不良反应",
    "contraindications": "禁忌证",
    "clinical_significance": "临床意义",
    "clinical_relevance": "临床意义",
    "related_concepts": "相关概念",
}

INVALID_TITLES = frozenset({"extraction failed", "extractionfailed", ""})


def normalized_title_key(title: str) -> str:
    return re.sub(r"\s+", "", (title or "").strip()).lower()


def content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()[:16]


def production_node_id(
    book_id: str,
    chapter: str,
    sub_chapter: str | None,
    title: str,
    *,
    source_anchor: str | None = None,
) -> str:
    parts = [
        book_id,
        chapter,
        sub_chapter or "",
        normalized_title_key(title),
    ]
    if source_anchor:
        parts.append(source_anchor)
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"kn-{digest}"


def is_valid_node_row(row: dict[str, Any]) -> bool:
    title = str(row.get("title") or "").strip()
    if not title or normalized_title_key(title) in INVALID_TITLES:
        return False
    if row.get("error"):
        return False

    content = str(row.get("content") or "").strip()
    sections = row.get("structured_sections") or []
    if isinstance(sections, list) and sections:
        return True
    return len(content) >= 15


def build_provenance(
    *,
    identity: TextbookIdentity,
    part_title: str,
    section_title: str,
    source_pdf: str,
    pipeline_version: str,
    created_from: str,
    page_start: int | None = None,
    page_end: int | None = None,
    source_anchor: str | None = None,
    content: str = "",
) -> dict[str, Any]:
    return {
        "textbook_id": identity.canonical_id,
        "textbook": identity.display_name,
        "subject": identity.subject_name,
        "edition": identity.edition,
        "part_title": part_title,
        "section_title": section_title,
        "source_pdf": source_pdf,
        "page_start": page_start,
        "page_end": page_end,
        "source_anchor": source_anchor,
        "extraction_pipeline_version": pipeline_version,
        "adapter_version": ADAPTER_VERSION,
        "content_hash": content_hash(content),
        "created_from": created_from,
    }


def attach_provenance(
    row: dict[str, Any],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    source_span = dict(row.get("source_span") or {})
    source_span["provenance"] = provenance
    row["source_span"] = source_span
    row["edition"] = provenance.get("edition")
    row["book_id"] = provenance.get("textbook_id")
    row["textbook"] = provenance.get("textbook_id")
    row["subject"] = provenance.get("subject")
    return row


def _extract_field_content(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("content", "text", "value"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner.strip()
    return ""


def flatten_v4_content(content: dict[str, Any]) -> tuple[str, list[dict[str, str]]]:
    sections: list[dict[str, str]] = []
    for field, label in SECTION_FIELD_LABELS.items():
        text = _extract_field_content(content.get(field))
        if text:
            sections.append({"title": label, "content": text})

    raw_text = _extract_field_content(content.get("raw_text"))
    if raw_text and not sections:
        sections.append({"title": "知识要点", "content": raw_text})

    joined = "\n\n".join(
        f"【{section['title']}】\n{section['content']}" for section in sections
    )
    return joined, sections


def map_v4_type(node_type: str | None) -> str:
    allowed = {"concept", "mechanism", "disease", "symptom", "treatment", "exam"}
    normalized = (node_type or "concept").strip().lower()
    return normalized if normalized in allowed else "concept"


def v4_structured_to_knowledge_node(
    item: dict[str, Any],
    identity: TextbookIdentity,
    *,
    chapter: str,
    sub_chapter: str | None = None,
    order_num: int = 0,
    provenance: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    knowledge_point = item.get("knowledge_point") or item
    title = str(knowledge_point.get("title") or "").strip()
    if not title or normalized_title_key(title) in INVALID_TITLES:
        return None

    report = item.get("extraction_report") or {}
    if report.get("error") or item.get("error"):
        return None

    content_blob = item.get("content") or {}
    if not isinstance(content_blob, dict):
        return None

    content, structured_sections = flatten_v4_content(content_blob)
    if len(content) < 15 and not structured_sections:
        return None

    node_type = map_v4_type(knowledge_point.get("type"))
    node_id = production_node_id(identity.canonical_id, chapter, sub_chapter, title)

    relations = item.get("relations") or []
    related_nodes: list[str] = []
    causal_links: list[dict[str, Any]] = []
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        target_name = str(relation.get("target_name") or relation.get("target") or "").strip()
        if not target_name:
            continue
        target_id = production_node_id(identity.canonical_id, chapter, sub_chapter, target_name)
        related_nodes.append(target_id)
        causal_links.append(
            {
                "from": title,
                "to": target_name,
                "target_id": target_id,
                "relation": str(relation.get("relation_type") or "associated_with"),
            }
        )

    row = {
        "id": node_id,
        "order_num": order_num,
        "level": 3,
        "type": node_type,
        "title": title,
        "subject": identity.subject_name,
        "chapter": chapter,
        "sub_chapter": sub_chapter,
        "knowledge_path": [part for part in [identity.subject_name, chapter, sub_chapter, title] if part],
        "content": content,
        "key_points": [],
        "structured_sections": structured_sections,
        "causal_links": causal_links,
        "related_nodes": list(dict.fromkeys(related_nodes)),
        "tags": [],
        "source": "pipeline_v4",
        "book_id": identity.canonical_id,
        "textbook": identity.canonical_id,
        "edition": identity.edition,
        "node_source": "llm_structured",
        "inferred": False,
        "standalone": True,
        "version": ADAPTER_VERSION,
    }
    if provenance:
        attach_provenance(row, provenance)
    return row


def finalize_knowledge_rows(
    rows: list[dict[str, Any]],
    identity: TextbookIdentity = INTERNAL_MEDICINE_10,
    *,
    provenance: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    finalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for index, row in enumerate(rows):
        if not is_valid_node_row(row):
            continue

        title = str(row.get("title") or "").strip()
        pdf_chapter = str(row.get("chapter") or "").strip() or None
        chapter = str(
            (provenance.get("part_title") if provenance else None)
            or row.get("chapter")
            or "未分类"
        ).strip()
        sub_chapter_text = str(
            (provenance.get("section_title") if provenance else None)
            or row.get("sub_chapter")
            or ""
        ).strip() or None

        source_span = row.get("source_span") or {}
        source_anchor = None
        if isinstance(source_span, dict):
            source_anchor = str(
                source_span.get("chunk_index")
                or source_span.get("segmentId")
                or ""
            ) or None

        node_id = production_node_id(
            identity.canonical_id,
            chapter,
            sub_chapter_text,
            title,
            source_anchor=source_anchor,
        )
        if node_id in seen_ids:
            continue
        seen_ids.add(node_id)

        structured_sections = row.get("structured_sections") or []
        if not isinstance(structured_sections, list):
            structured_sections = []

        content = str(row.get("content") or "").strip()
        if not structured_sections and content:
            structured_sections = [{"title": "知识要点", "content": content}]

        finalized_row = {
            **row,
            "id": node_id,
            "order_num": row.get("order_num", index),
            "title": title,
            "subject": identity.subject_name,
            "chapter": chapter,
            "sub_chapter": sub_chapter_text,
            "book_id": identity.canonical_id,
            "textbook": identity.canonical_id,
            "edition": identity.edition,
            "content": content,
            "structured_sections": structured_sections,
            "knowledge_path": [
                part
                for part in [identity.subject_name, chapter, sub_chapter_text, title]
                if part
            ],
            "version": ADAPTER_VERSION,
        }
        if provenance:
            row_provenance = {
                **provenance,
                "content_hash": content_hash(content),
                "source_anchor": source_anchor,
            }
            if pdf_chapter and pdf_chapter != chapter:
                row_provenance["pdf_part_title"] = pdf_chapter
            attach_provenance(finalized_row, row_provenance)
        finalized.append(finalized_row)
    return finalized


def load_v4_nodes(path: str) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        payload = json.loads(handle.read())
    if isinstance(payload, list):
        return payload
    return payload.get("nodes") or payload.get("results") or []


def convert_v4_file_to_knowledge_rows(
    path: str,
    *,
    identity: TextbookIdentity = INTERNAL_MEDICINE_10,
    chapter: str,
    sub_chapter: str | None = None,
    provenance: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(load_v4_nodes(path)):
        if not isinstance(item, dict):
            continue
        if "knowledge_point" in item and "content" in item:
            row = v4_structured_to_knowledge_node(
                item,
                identity,
                chapter=chapter,
                sub_chapter=sub_chapter,
                order_num=index,
                provenance=provenance,
            )
        else:
            title = str(item.get("title") or "").strip()
            if not title or item.get("error"):
                continue
            sample = _extract_field_content(item.get("raw_text_sample"))
            row = {
                "id": production_node_id(identity.canonical_id, chapter, sub_chapter, title),
                "order_num": index,
                "level": 3,
                "type": map_v4_type(item.get("type")),
                "title": title,
                "subject": identity.subject_name,
                "chapter": chapter,
                "sub_chapter": sub_chapter,
                "content": sample,
                "structured_sections": [{"title": "知识要点", "content": sample}] if sample else [],
                "source": "pipeline_v4",
                "book_id": identity.canonical_id,
                "textbook": identity.canonical_id,
                "edition": identity.edition,
                "node_source": "llm_structured",
            }
            if provenance:
                attach_provenance(row, provenance)
        if row and is_valid_node_row(row):
            rows.append(row)
    return finalize_knowledge_rows(rows, identity, provenance=provenance)


def load_v4_payload(path: str | Path) -> list[dict[str, Any]]:
    return load_v4_nodes(str(path))


def v4_payload_to_knowledge_rows(
    nodes: list[dict[str, Any]],
    *,
    textbook_id: str,
    subject: str,
    textbook: str,
    chapter: str,
    sub_chapter: str | None = None,
    source_pdf: str = "",
    pipeline_version: str = "v4",
) -> list[dict[str, Any]]:
    identity = TextbookIdentity(
        canonical_id=textbook_id,
        display_name=textbook,
        subject_name=subject,
        edition="",
        source_filename=Path(source_pdf).name if source_pdf else "",
        aliases=(textbook, textbook_id),
    )
    provenance = build_provenance(
        identity=identity,
        part_title=chapter,
        section_title=sub_chapter or chapter,
        source_pdf=source_pdf,
        pipeline_version=pipeline_version,
        created_from="v4_payload",
    )
    rows: list[dict[str, Any]] = []
    for index, item in enumerate(nodes):
        if not isinstance(item, dict):
            continue
        if "knowledge_point" in item and "content" in item:
            row = v4_structured_to_knowledge_node(
                item,
                identity,
                chapter=chapter,
                sub_chapter=sub_chapter,
                order_num=index,
                provenance=provenance,
            )
        else:
            title = str(item.get("title") or "").strip()
            if not title or item.get("error"):
                continue
            sample = _extract_field_content(item.get("raw_text_sample"))
            row = {
                "id": production_node_id(identity.canonical_id, chapter, sub_chapter, title),
                "order_num": index,
                "level": 3,
                "type": map_v4_type(item.get("type")),
                "title": title,
                "subject": identity.subject_name,
                "chapter": chapter,
                "sub_chapter": sub_chapter,
                "content": sample,
                "structured_sections": [{"title": "知识要点", "content": sample}] if sample else [],
                "source": pipeline_version,
                "book_id": identity.canonical_id,
                "textbook": identity.canonical_id,
                "edition": identity.edition,
                "node_source": "llm_structured",
            }
            attach_provenance(row, provenance)
        if row and is_valid_node_row(row):
            rows.append(row)
    return finalize_knowledge_rows(rows, identity, provenance=provenance)


def assert_knowledge_points_deprecated() -> None:
    if KNOWLEDGE_POINTS_DEPRECATED:
        raise RuntimeError(DEPRECATION_NOTICE)