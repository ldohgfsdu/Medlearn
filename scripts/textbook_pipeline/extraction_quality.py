"""Quality assessment and chunk filtering for V3 extraction."""
from __future__ import annotations

import re
from typing import Any

from textbook_pipeline.node_guardrails import assess_guardrails

BOILERPLATE_RE = re.compile(
    r"^(?:第[一二三四五六七八九十百零\d]+[章节篇]|目录|索引|附录|参考文献|彩图|"
    r"推荐阅读|学习小结|思考题|图\d|表\d|\d+\s*$)",
    re.MULTILINE,
)
PAGE_MARKER_RE = re.compile(r"<!--\s*PDF page \d+\s*-->")


def clean_chunk_text(text: str) -> str:
    text = PAGE_MARKER_RE.sub("", text or "")
    return re.sub(r"\s+", " ", text).strip()


def is_extractable_chunk(text: str, *, min_chars: int = 80) -> bool:
    cleaned = clean_chunk_text(text)
    if len(cleaned) < min_chars:
        return False
    if BOILERPLATE_RE.fullmatch(cleaned[:120]):
        return False
    cjk = len(re.findall(r"[\u4e00-\u9fff]", cleaned))
    return cjk >= max(30, len(cleaned) // 8)


def enrich_row_content(row: dict[str, Any]) -> dict[str, Any]:
    """Ensure content names parent_entity when title already does."""
    source_span = row.get("source_span") or {}
    parent = ""
    if isinstance(source_span, dict):
        parent = str(source_span.get("parent_entity") or "").strip()
    title = str(row.get("title") or "").strip()
    content = str(row.get("content") or "").strip()
    if parent and parent in title and parent not in content:
        row["content"] = f"{parent}：{content}" if content else parent
        sections = row.get("structured_sections") or []
        if isinstance(sections, list) and sections:
            first = sections[0]
            if isinstance(first, dict) and not str(first.get("content") or "").startswith(parent):
                first["content"] = row["content"]
    return row


def assess_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "node_count": 0,
            "passed": False,
            "reasons": ["empty"],
            "metrics": {},
        }

    with_evidence = 0
    with_parent = 0
    dup_titles = 0
    seen_titles: set[str] = set()
    short_content = 0

    for row in rows:
        title_key = re.sub(r"\s+", "", str(row.get("title") or "").lower())
        if title_key in seen_titles:
            dup_titles += 1
        seen_titles.add(title_key)

        content = str(row.get("content") or "").strip()
        if len(content) < 15:
            short_content += 1

        span = row.get("source_span") or {}
        if isinstance(span, dict):
            if str(span.get("evidence") or "").strip():
                with_evidence += 1
            parent = str(span.get("parent_entity") or "").strip()
            if parent and parent in content:
                with_parent += 1

    total = len(rows)
    metrics = {
        "node_count": total,
        "evidence_ratio": round(with_evidence / total, 3),
        "parent_in_content_ratio": round(with_parent / total, 3),
        "duplicate_titles": dup_titles,
        "short_content": short_content,
    }
    reasons: list[str] = []
    if total < 1:
        reasons.append("no_nodes")
    if with_evidence / total < 0.5:
        reasons.append("low_evidence_ratio")
    if with_parent / total < 0.4:
        reasons.append("low_parent_ratio")
    if short_content / total > 0.2:
        reasons.append("too_many_short_nodes")

    passed = (
        total >= 1
        and with_evidence / total >= 0.5
        and with_parent / total >= 0.4
        and short_content / total <= 0.25
    )
    return {
        "node_count": total,
        "passed": passed,
        "reasons": reasons,
        "metrics": metrics,
    }


def merge_quality_reports(*reports: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, Any] = {}
    passed = True

    for report in reports:
        if not report:
            continue
        metrics.update(report.get("metrics") or {})
        if not report.get("passed", True):
            passed = False
        for reason in report.get("reasons") or []:
            if reason not in reasons:
                reasons.append(reason)
        for warning in report.get("warnings") or []:
            if warning not in warnings:
                warnings.append(warning)

    return {
        "passed": passed,
        "reasons": reasons,
        "warnings": warnings,
        "metrics": metrics,
    }


def assess_rows_with_guardrails(
    rows: list[dict[str, Any]],
    *,
    section_entity: str,
    chunk_source_map: dict[str, str] | None = None,
    section_markdown: str = "",
) -> dict[str, Any]:
    base = assess_rows(rows)
    guardrails = assess_guardrails(
        rows,
        section_entity=section_entity,
        chunk_source_map=chunk_source_map,
        section_markdown=section_markdown,
    )
    merged = merge_quality_reports(base, guardrails)
    merged["guardrails"] = guardrails
    return merged


def assess_chunk_coverage(
    total_chunks: int,
    cached_chunks: int,
    *,
    min_ratio: float = 0.8,
    min_cached: int = 3,
) -> dict[str, Any]:
    ratio = (cached_chunks / total_chunks) if total_chunks else 0.0
    if total_chunks == 0:
        passed = True
    elif total_chunks < min_cached:
        passed = cached_chunks == total_chunks
    else:
        passed = ratio >= min_ratio and cached_chunks >= min_cached
    return {
        "total_chunks": total_chunks,
        "cached_chunks": cached_chunks,
        "coverage_ratio": round(ratio, 3),
        "min_ratio": min_ratio,
        "min_cached": min_cached,
        "passed": passed,
    }