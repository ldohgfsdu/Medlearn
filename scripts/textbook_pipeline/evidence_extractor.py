"""Evidence Extractor — Phase 1 of EV1 pipeline.

Deterministic extraction of evidence artifacts from PDF sections.
No LLM calls. Pure PDF/catalog logic.

Produces: list[EvidenceArtifact] per section.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .evidence_artifact import (
    EvidenceArtifact,
    EvidenceLocator,
    make_artifact,
)

# Heading patterns from pipeline_v3_extract.py
PART_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+篇")
CHAPTER_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+章")
SECTION_RE = re.compile(r"第[一二三四五六七八九十百零〇\d]+节")
SUBHEADING_RE = re.compile(
    r"^(?:【(.+?)】|(?:（[一二三四五六七八九十百]+）)"
    r"|[一二三四五六七八九十百]+[、.．])"
)

# Mixed （x） title + body: shortest title run until body sentence starts.
PAREN_HEADING_PREFIX_RE = re.compile(
    r"^([（(][一二三四五六七八九十百]+[）)]\s*"
    r"(?:[\u4e00-\u9fff（()）、・·，%％／/]|[A-Za-z0-9])+?)"
    r"(?=\s+[\u4e00-\u9fff]{2,}|\s*。|$)",
    re.UNICODE,
)

BRACKET_HEADING_SPLIT_RE = re.compile(r"^【([^】]+)】\s*(.*)$", re.DOTALL)

ARABIC_NUMBERED_RE = re.compile(r"^\d+\.\s")

# Known aspect normalization mapping
ASPECT_NORMALIZE: dict[str, str] = {
    "病因和发病机制": "病因",
    "诊断与鉴别诊断": "诊断",
    "实验室和其他辅助检查": "辅助检查",
    "个体化治疗方案": "治疗",
    "治疗原则": "治疗",
    "诊断原则": "诊断",
    "临床表现": "临床表现",
    "临床分型": "临床分型",
    "发病机制": "发病机制",
    "病理机制": "病理",
    "危险因素": "病因",
    "流行病学": "流行病学",
    "鉴别诊断": "诊断",
    "并发症": "并发症",
    "实验室检查": "辅助检查",
    "辅助检查": "辅助检查",
    "定义": "定义",
    "概念": "定义",
    "病因": "病因",
    "病理": "病理",
    "诊断": "诊断",
    "检查": "辅助检查",
    "治疗": "治疗",
    "预后": "预后",
    "预防": "预防",
}


def _normalize_aspect(heading: str) -> str | None:
    """Try to map a heading to a canonical aspect label."""
    cleaned = heading.strip()
    # Direct match
    if cleaned in ASPECT_NORMALIZE:
        return ASPECT_NORMALIZE[cleaned]
    # Strip brackets/brackets content
    stripped = re.sub(r"[【】（）()]", "", cleaned).strip()
    if stripped in ASPECT_NORMALIZE:
        return ASPECT_NORMALIZE[stripped]
    return None


def _is_structural_heading(text: str) -> bool:
    """Check if text is a part/chapter/section heading (not content sub-heading)."""
    return bool(
        PART_RE.search(text) or CHAPTER_RE.search(text) or SECTION_RE.search(text)
    )


def _detect_subheading(text: str) -> str | None:
    """Extract sub-heading text if present (e.g. 【病因】 or 一、定义)."""
    match = SUBHEADING_RE.match(text.strip())
    if match:
        return match.group(1) or match.group(0)
    return None


def _is_structural_heading_text(text: str) -> bool:
    """Check if text looks like a structural heading (not body text).

    Structural headings include:
    - Part/chapter/section titles (第X篇/章/节)
    - Bracketed headings (【病因】)
    - Numbered sub-headings (一、定义)
    - Short known aspect labels (临床表现, 诊断, 治疗)
    - 2-20 chars with no sentence-ending punctuation

    Returns False for body text (long sentences, periods, commas in middle).
    """
    text = text.strip()
    if not text:
        return False

    # Must be short (real headings are rarely > 60 chars)
    if len(text) > 60:
        return False

    # Part/chapter/section
    if PART_RE.search(text) or CHAPTER_RE.search(text) or SECTION_RE.search(text):
        return True

    # Bracketed headings: 【病因】
    if SUBHEADING_RE.match(text):
        return True

    # Known aspect labels
    normalized = re.sub(r"[【】（）()\s]", "", text)
    if normalized in ASPECT_NORMALIZE:
        return True

    # Short text without sentence-ending punctuation is likely a heading
    # Body text typically has 。；，etc.
    sentence_punct = set("。，；：、！？…")
    if len(text) <= 30 and not any(c in sentence_punct for c in text):
        return True

    return False


def _is_structural_prefix(text: str) -> bool:
    """Prefix-shaped headings bypass the large-font gate entirely."""
    stripped = text.strip()
    if stripped.startswith("【"):
        return True
    return bool(SUBHEADING_RE.match(stripped))


def _is_arabic_numbered_block(text: str) -> bool:
    return bool(ARABIC_NUMBERED_RE.match(text.strip()))


def _block_is_heading_flag(text: str, max_size: float, body_size: float) -> bool:
    """Whether this block updates the heading stack (not necessarily heading-only)."""
    stripped = text.strip()
    if _is_arabic_numbered_block(stripped):
        return False
    is_large = max_size >= body_size * 1.35 and len(stripped) <= 80
    is_structural_prefix = _is_structural_prefix(stripped)
    return is_structural_prefix or (
        is_large and _is_structural_heading_text(stripped)
    )


def _canonical_heading_label(heading_part: str) -> str:
    """Heading label stored on the stack / source_heading."""
    t = heading_part.strip().replace("\n", " ")
    bracket = re.match(r"^【([^】]+)】", t)
    if bracket:
        return bracket.group(1).strip()
    t = re.sub(r"^[（(][一二三四五六七八九十百]+[）)]\s*", "", t).strip()
    return t or heading_part.strip()


def _split_heading_body(text: str) -> tuple[str | None, str]:
    """Split a block into (heading_prefix, body). heading_prefix None => body-only block."""
    t = text.strip().replace("\n", " ")
    if not t:
        return None, ""

    if t.startswith("【"):
        match = BRACKET_HEADING_SPLIT_RE.match(t)
        if match:
            inner = match.group(1).strip()
            body = match.group(2).strip()
            return f"【{inner}】", body
        return t, ""

    if _is_arabic_numbered_block(t):
        return None, t

    paren = PAREN_HEADING_PREFIX_RE.match(t)
    if paren:
        heading_part = paren.group(1).strip()
        body_part = t[paren.end() :].strip()
        return heading_part, body_part

    if SUBHEADING_RE.match(t) and len(t) <= 60 and "。" not in t:
        return t, ""

    return None, t


def _block_text(block: dict[str, Any]) -> tuple[str, float]:
    """Extract text and max font size from a pymupdf text block."""
    lines: list[str] = []
    sizes: list[float] = []
    for line in block.get("lines") or []:
        spans = line.get("spans") or []
        value = "".join(str(span.get("text") or "") for span in spans).strip()
        if value:
            lines.append(value)
        sizes.extend(
            float(span.get("size") or 0)
            for span in spans
            if span.get("size")
        )
    return "\n".join(lines).strip(), (max(sizes) if sizes else 0.0)


def _bbox_overlap_ratio(bbox1: tuple, bbox2: tuple) -> float:
    """Calculate overlap ratio between two bounding boxes."""
    x0 = max(bbox1[0], bbox2[0])
    y0 = max(bbox1[1], bbox2[1])
    x1 = min(bbox1[2], bbox2[2])
    y1 = min(bbox1[3], bbox2[3])
    if x0 >= x1 or y0 >= y1:
        return 0.0
    intersection = (x1 - x0) * (y1 - y0)
    area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
    return intersection / area1 if area1 > 0 else 0.0


def _table_payloads(page) -> list[tuple[tuple[float, ...], str]]:
    """Extract tables from a pymupdf page."""
    try:
        tables = page.find_tables().tables
    except Exception:
        return []
    payloads = []
    for table in tables:
        try:
            markdown = table.to_markdown().strip()
        except Exception:
            continue
        bbox = tuple(float(v) for v in table.bbox)
        if markdown:
            payloads.append((bbox, markdown))
    return payloads


def extract_page_artifacts(
    pdf_path: Path,
    page_num: int,
) -> list[dict[str, Any]]:
    """Extract text blocks, tables, and figures from a single PDF page.

    Returns list of dicts with keys:
      text, artifact_type, bbox, page
    """
    import pymupdf as fitz

    doc = fitz.open(str(pdf_path))
    try:
        page = doc[page_num - 1]  # 0-indexed
        blocks = page.get_text("dict", sort=True).get("blocks") or []

        # Get tables first
        table_payloads = _table_payloads(page)
        table_bboxes = [tp[0] for tp in table_payloads]

        # Compute body font size
        body_sizes = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            text, max_size = _block_text(block)
            if len(text) >= 20 and max_size > 0:
                body_sizes.append(max_size)
        body_size = sorted(body_sizes)[len(body_sizes) // 2] if body_sizes else 10.0

        artifacts: list[dict[str, Any]] = []

        # Tables
        for bbox, markdown in table_payloads:
            artifacts.append({
                "text": markdown,
                "artifact_type": "table",
                "bbox": bbox,
                "page": page_num,
            })

        # Text blocks
        for block in blocks:
            if block.get("type") != 0:
                continue
            bbox = tuple(float(v) for v in block.get("bbox", ()))
            if not bbox or len(bbox) != 4:
                continue

            # Skip blocks overlapping with tables
            if any(_bbox_overlap_ratio(bbox, tb) >= 0.35 for tb in table_bboxes):
                continue

            text, max_size = _block_text(block)
            stripped = text.strip() if text else ""
            if not stripped:
                continue
            # Short structural headings (e.g. （三） 肺功能检查) must not be dropped.
            if len(stripped) < 10 and not _is_structural_prefix(stripped):
                continue

            # Heading: structural prefix bypasses large-font; otherwise large + pattern.
            is_large = max_size >= body_size * 1.35 and len(stripped) <= 80
            is_structural_prefix = _is_structural_prefix(stripped)
            is_heading = is_structural_prefix or (
                is_large and _is_structural_heading_text(stripped)
            )
            if _is_arabic_numbered_block(stripped):
                is_heading = False

            artifacts.append({
                "text": text,
                "artifact_type": "text_block",
                "bbox": bbox,
                "page": page_num,
                "is_heading": is_heading,
                "font_size": max_size,
            })

        return artifacts

    finally:
        doc.close()


def extract_section_evidence(
    pdf_path: Path,
    textbook_id: str,
    book_id: str,
    part_title: str,
    section_title: str,
    page_start: int,
    page_end: int,
) -> list[EvidenceArtifact]:
    """Extract all evidence artifacts from a PDF section.

    This is the main entry point for Phase 1.
    Deterministic, no LLM calls.
    """
    import pymupdf as fitz

    all_artifacts: list[EvidenceArtifact] = []
    source_order = 0

    doc = fitz.open(str(pdf_path))
    try:
        # Compute body font size across section for heading detection
        body_sizes: list[float] = []
        for pn in range(page_start, page_end + 1):
            if pn < 1 or pn > doc.page_count:
                continue
            page = doc[pn - 1]
            blocks = page.get_text("dict", sort=True).get("blocks") or []
            for block in blocks:
                if block.get("type") != 0:
                    continue
                text, max_size = _block_text(block)
                if len(text) >= 20 and max_size > 0:
                    body_sizes.append(max_size)
        body_size = sorted(body_sizes)[len(body_sizes) // 2] if body_sizes else 10.0

        # Track current heading context
        current_heading = section_title

        for pn in range(page_start, page_end + 1):
            if pn < 1 or pn > doc.page_count:
                continue

            page_artifacts = extract_page_artifacts(pdf_path, pn)

            for art in page_artifacts:
                text = art["text"]
                art_type = art["artifact_type"]
                bbox = art.get("bbox")
                max_size = float(art.get("font_size") or 0.0)

                if art_type == "text_block":
                    flat_text = text.strip().replace("\n", " ")

                    if _block_is_heading_flag(flat_text, max_size, body_size):
                        heading_part, body_part = _split_heading_body(flat_text)
                        if heading_part:
                            current_heading = _canonical_heading_label(heading_part)
                        if body_part and len(body_part.strip()) >= 15:
                            emit_text = body_part.strip()
                        else:
                            continue
                    else:
                        if len(text.strip()) < 15:
                            continue
                        emit_text = text
                else:
                    emit_text = text

                locator = EvidenceLocator(
                    page=pn,
                    kind=art_type,
                    bbox=tuple(bbox) if bbox else None,
                ) if bbox else None

                artifact = make_artifact(
                    textbook_id=textbook_id,
                    book_id=book_id,
                    part_title=part_title,
                    section_title=section_title,
                    source_heading=current_heading,
                    normalized_aspect=_normalize_aspect(current_heading),
                    source_order=source_order,
                    artifact_type=art_type,
                    raw_text=emit_text,
                    page_start=pn,
                    page_end=pn,
                    locator=locator,
                    verification_state="source_verified",
                )
                all_artifacts.append(artifact)
                source_order += 1

    finally:
        doc.close()

    return all_artifacts


def write_evidence_cache(
    artifacts: list[EvidenceArtifact],
    output_path: Path,
) -> Path:
    """Write evidence artifacts to JSON cache."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "ev1-0.1.0",
        "count": len(artifacts),
        "artifacts": [a.to_dict() for a in artifacts],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return output_path


def load_evidence_cache(output_path: Path) -> list[EvidenceArtifact]:
    """Load evidence artifacts from JSON cache."""
    with open(output_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return [EvidenceArtifact.from_dict(d) for d in payload.get("artifacts", [])]
