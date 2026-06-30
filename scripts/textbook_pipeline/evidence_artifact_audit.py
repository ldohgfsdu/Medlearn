"""Lightweight structural audit for EV1 evidence artifacts.

The audit is intentionally observational: it records table/list/figure-caption
risks without blocking normal text extraction or inventing missing structure.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from textbook_pipeline.evidence_artifact import EvidenceArtifact

CAPTION_LIKE_RE = re.compile(r"^\s*(?:图|表)\s*[\d一二三四五六七八九十\-－.．]+")
NOTE_LIKE_RE = re.compile(r"^\s*(?:注|注释|说明)\s*[:：]")
LIST_PREFIX_RE = re.compile(
    r"^\s*(?:[一二三四五六七八九十]+[、.．]|（[一二三四五六七八九十]+）|\([一二三四五六七八九十]+\)|\d+[、.．]|\(\d+\))"
)


def _bbox(artifact: EvidenceArtifact) -> tuple[float, float, float, float] | None:
    if not artifact.locator or not artifact.locator.bbox:
        return None
    values = tuple(float(v) for v in artifact.locator.bbox)
    return values if len(values) == 4 else None


def _table_column_count(markdown: str) -> int:
    for line in markdown.splitlines():
        stripped = line.strip()
        if "|" not in stripped:
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        meaningful = [cell for cell in cells if cell and not set(cell) <= {"-", ":"}]
        if meaningful:
            return len(cells)
    return 0


def _caption_kind(text: str) -> str | None:
    stripped = text.strip()
    if stripped.startswith("图") and CAPTION_LIKE_RE.match(stripped):
        return "figure_caption"
    if stripped.startswith("表") and CAPTION_LIKE_RE.match(stripped):
        return "table_caption"
    if NOTE_LIKE_RE.match(stripped):
        return "note"
    return None


def _layout_topology_hash(text: str) -> str:
    signatures: list[str] = []
    for line in text.splitlines():
        prefix = ""
        match = LIST_PREFIX_RE.match(line)
        if match:
            prefix = match.group(0).strip()
        leading = len(line) - len(line.lstrip())
        signatures.append(f"{leading}:{prefix}:{len(line.strip())}")
    return hashlib.sha256("\n".join(signatures).encode("utf-8")).hexdigest()[:16]


def _list_audit(artifact: EvidenceArtifact) -> dict[str, Any] | None:
    lines = [line for line in artifact.raw_text.splitlines() if line.strip()]
    prefixed = [line for line in lines if LIST_PREFIX_RE.match(line)]
    if len(lines) < 2 or len(prefixed) < 2:
        return None
    return {
        "artifact_id": artifact.id,
        "page": artifact.page_start,
        "line_count": len(lines),
        "prefixed_line_count": len(prefixed),
        "layout_topology_hash": _layout_topology_hash(artifact.raw_text),
        "render_type": "pre_formatted_list",
    }


def _image_blocks(pdf_path: Path, page_start: int, page_end: int) -> list[dict[str, Any]]:
    try:
        import pymupdf as fitz
    except Exception:
        return []

    blocks: list[dict[str, Any]] = []
    doc = fitz.open(str(pdf_path))
    try:
        for page_num in range(page_start, page_end + 1):
            if page_num < 1 or page_num > doc.page_count:
                continue
            page = doc[page_num - 1]
            for block in page.get_text("dict", sort=True).get("blocks") or []:
                if block.get("type") != 1:
                    continue
                bbox = tuple(float(v) for v in block.get("bbox", ()))
                if len(bbox) == 4:
                    blocks.append({"page": page_num, "bbox": bbox})
    finally:
        doc.close()
    return blocks


def _nearby_text(
    table: EvidenceArtifact,
    text_artifacts: list[EvidenceArtifact],
    *,
    above_px: float,
    below_px: float,
) -> tuple[list[EvidenceArtifact], list[EvidenceArtifact]]:
    table_bbox = _bbox(table)
    if table_bbox is None:
        return [], []
    x0, y0, x1, y1 = table_bbox
    above: list[EvidenceArtifact] = []
    below: list[EvidenceArtifact] = []
    for text in text_artifacts:
        if text.page_start != table.page_start:
            continue
        text_bbox = _bbox(text)
        if text_bbox is None:
            continue
        tx0, ty0, tx1, ty1 = text_bbox
        horizontal_overlap = min(x1, tx1) - max(x0, tx0)
        if horizontal_overlap <= 0:
            continue
        if y0 - above_px <= ty1 <= y0:
            above.append(text)
        if y1 <= ty0 <= y1 + below_px:
            below.append(text)
    return above, below


def audit_artifacts(
    artifacts: list[EvidenceArtifact],
    *,
    pdf_path: Path | None = None,
) -> dict[str, Any]:
    tables = [artifact for artifact in artifacts if artifact.artifact_type == "table"]
    texts = [artifact for artifact in artifacts if artifact.artifact_type == "text_block"]
    figures = [artifact for artifact in artifacts if artifact.artifact_type == "figure"]
    captions = [artifact for artifact in artifacts if artifact.artifact_type == "caption"]

    warnings: list[dict[str, Any]] = []
    caption_like: list[dict[str, Any]] = []
    for artifact in texts:
        kind = _caption_kind(artifact.raw_text)
        if not kind:
            continue
        item = {
            "artifact_id": artifact.id,
            "page": artifact.page_start,
            "kind": kind,
            "text": artifact.raw_text[:120],
        }
        caption_like.append(item)
        if kind == "figure_caption" and not any(fig.page_start == artifact.page_start for fig in figures):
            warnings.append({
                "type": "missing_figure_context_warning",
                "severity": "warning",
                "page": artifact.page_start,
                "artifact_id": artifact.id,
                "message": "caption-like figure text exists without a preserved figure artifact",
            })

    table_bindings: list[dict[str, Any]] = []
    for table in tables:
        above, below = _nearby_text(table, texts, above_px=50, below_px=80)
        title_ids = [
            artifact.id for artifact in above
            if _caption_kind(artifact.raw_text) in {"table_caption", "figure_caption"}
        ]
        note_ids = [
            artifact.id for artifact in below
            if _caption_kind(artifact.raw_text) == "note" or artifact.raw_text.strip().startswith("*")
        ]
        binding = {
            "table_id": table.id,
            "page": table.page_start,
            "column_count": _table_column_count(table.raw_text),
            "caption_artifact_ids": title_ids,
            "note_artifact_ids": note_ids,
        }
        table_bindings.append(binding)
        if not title_ids:
            warnings.append({
                "type": "table_caption_not_bound",
                "severity": "info",
                "page": table.page_start,
                "artifact_id": table.id,
                "message": "table has no nearby caption-like text within audit window",
            })

    possible_continued_tables: list[dict[str, Any]] = []
    sorted_tables = sorted(tables, key=lambda artifact: (artifact.page_start, artifact.source_order))
    for left, right in zip(sorted_tables, sorted_tables[1:]):
        if right.page_start != left.page_start + 1:
            continue
        left_bbox = _bbox(left)
        right_bbox = _bbox(right)
        if not left_bbox or not right_bbox:
            continue
        left_cols = _table_column_count(left.raw_text)
        right_cols = _table_column_count(right.raw_text)
        near_bottom = left_bbox[3] >= 680
        near_top = right_bbox[1] <= 180
        similar_cols = left_cols > 0 and right_cols > 0 and abs(left_cols - right_cols) <= 1
        if near_bottom and near_top and similar_cols:
            group_id = hashlib.sha256(f"{left.id}\0{right.id}".encode("utf-8")).hexdigest()[:12]
            possible_continued_tables.append({
                "group_id": f"table-cont-{group_id}",
                "table_artifact_ids": [left.id, right.id],
                "pages": [left.page_start, right.page_start],
                "column_counts": [left_cols, right_cols],
            })
            warnings.append({
                "type": "possible_continued_table",
                "severity": "warning",
                "page": left.page_start,
                "artifact_id": left.id,
                "message": f"possible continued table on pages {left.page_start}-{right.page_start}",
            })

    list_artifacts = [
        audit for audit in (_list_audit(artifact) for artifact in texts) if audit is not None
    ]

    image_blocks: list[dict[str, Any]] = []
    if pdf_path and artifacts:
        page_start = min(artifact.page_start for artifact in artifacts)
        page_end = max(artifact.page_end for artifact in artifacts)
        image_blocks = _image_blocks(pdf_path, page_start, page_end)
        for image in image_blocks:
            if not any(item["page"] == image["page"] and item["kind"] == "figure_caption" for item in caption_like):
                warnings.append({
                    "type": "image_without_caption_text",
                    "severity": "info",
                    "page": image["page"],
                    "artifact_id": None,
                    "message": "PDF image block exists without nearby caption-like text artifact",
                })

    return {
        "version": "ev1-artifact-audit-0.1.0",
        "summary": {
            "total_artifacts": len(artifacts),
            "text_block": len(texts),
            "table": len(tables),
            "figure": len(figures),
            "caption": len(captions),
            "caption_like_text": len(caption_like),
            "list_like_text": len(list_artifacts),
            "pdf_image_blocks": len(image_blocks),
            "warnings": len(warnings),
        },
        "caption_like_text": caption_like,
        "table_bindings": table_bindings,
        "possible_continued_tables": possible_continued_tables,
        "list_artifacts": list_artifacts,
        "image_blocks": image_blocks,
        "warnings": warnings,
    }
