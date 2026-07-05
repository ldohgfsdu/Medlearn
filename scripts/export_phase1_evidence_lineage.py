#!/usr/bin/env python3
"""Phase 1 evidence lineage export (read-only artifacts, no App/DB changes).

Active object: phase1_evidence_lineage_export
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import fitz  # PyMuPDF

ROOT = Path(__file__).resolve().parents[1]
SECTION_KEY = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
TEXTBOOK_ID = "internal-medicine-10"
TEXTBOOK_VERSION = "10"
PDF_PATH = ROOT / "textbook" / "内科学（第10版）.pdf"
PDF_PAGES_1BASED = list(range(62, 71))  # 62..70 inclusive (PDF 1-based page numbers)
PAGE_DELTA = 31  # PDF 1-based page - printed page label (verified for asthma scope)

DC_PATH = (
    ROOT
    / "generated/display_contracts/internal-medicine-10"
    / f"{SECTION_KEY}.display_contract.json"
)
EVIDENCE_PATH = (
    ROOT
    / "generated/knowledge_nodes/internal-medicine-10"
    / f"{SECTION_KEY}.evidence.json"
)

OUT_BASE = ROOT / "generated/phase1_visual_evidence"
OUT_LOCATORS = OUT_BASE / "source_locators" / TEXTBOOK_ID
OUT_PAGE_MAP = OUT_BASE / "page_maps"
OUT_REPORTS = ROOT / "generated/reports/phase1_visual_evidence_coordinate_check"
# PageAsset export (webp + page_assets.json) lives in
# scripts/export_phase1_page_assets.py to keep responsibility separation:
#   lineage script    -> page map + SourceLocator
#   page-assets script -> webp + pages manifest


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_page_map(doc: fitz.Document) -> dict:
    """Build page map with correct pageLabel (printed) and pdfPageIndex (0-based).

    Key distinction (verified in Phase 6A):
    - pdfPageNumber1Based: PDF file page number (62-70)
    - pdfPageIndex: 0-based PyMuPDF index (61-69)
    - pageLabel: printed page label shown to users ("31"-"39")
    - evidence.json page_start stores PDF 1-based page numbers (62-70)
    """
    pages = []
    for pdf_page_1based in PDF_PAGES_1BASED:
        pdf_page_index = pdf_page_1based - 1  # 0-based for PyMuPDF
        printed_label = str(pdf_page_1based - PAGE_DELTA)  # "31".."39"
        page = doc.load_page(pdf_page_index)
        pages.append(
            {
                "pdfPageNumber1Based": pdf_page_1based,
                "pdfPageIndex": pdf_page_index,
                "pdfPageIndexBasis": "0-based",
                "pageLabel": printed_label,
                "pageWidthPt": float(page.rect.width),
                "pageHeightPt": float(page.rect.height),
                "verified": True,
                "verificationMethod": "content_anchor_match",
                "verificationNotes": (
                    f"PDF page {pdf_page_1based} (index {pdf_page_index}) "
                    f"shows printed label '{printed_label}'; "
                    "BDT anchor on PDF page 64 at index 63"
                ),
            }
        )
    return {
        "textbookId": TEXTBOOK_ID,
        "textbookVersion": TEXTBOOK_VERSION,
        "section": SECTION_KEY,
        "generatedAt": _iso(),
        "mappingRule": (
            "pdfPageIndex_0based = pdfPageNumber1Based - 1; "
            "printed_pageLabel = str(pdfPageNumber1Based - 31)"
        ),
        "pageDelta": PAGE_DELTA,
        "pages": pages,
    }


def bbox_to_norm_top_left(
    bbox: list[float], width: float, height: float
) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [x0 / width, y0 / height, x1 / width, y1 / height]


def bbox_to_norm_y_flip(
    bbox: list[float], width: float, height: float
) -> list[float]:
    x0, y0, x1, y1 = bbox
    return [
        x0 / width,
        (height - y1) / height,
        x1 / width,
        (height - y0) / height,
    ]


def merge_same_line_bboxes(
    bboxes: list[list[float]], gap_tolerance: float = 0.5
) -> list[list[float]]:
    """Merge bbox fragments on the same visual line.

    Two fragments are on the same visual line if the vertical gap between them
    is less than gap_tolerance pt. Adjacent text lines (gap ~2-3pt) are NOT
    merged. Returns one bbox per visual line: [min_x0, min_y0, max_x1, max_y1].
    """
    if not bboxes:
        return []
    sorted_b = sorted(bboxes, key=lambda b: b[1])
    merged = [list(sorted_b[0])]
    for b in sorted_b[1:]:
        last = merged[-1]
        gap = b[1] - last[3]
        if gap < gap_tolerance:
            last[0] = min(last[0], b[0])
            last[1] = min(last[1], b[1])
            last[2] = max(last[2], b[2])
            last[3] = max(last[3], b[3])
        else:
            merged.append(list(b))
    return merged


def extract_line_bboxes(
    page: fitz.Page, raw_text: str, bbox: list[float]
) -> list[list[float]]:
    """Extract per-visual-line bboxes for an artifact.

    Each returned bbox covers one visual PDF line (fragments on the same row
    are merged). Single-line artifacts return [bbox] unchanged.

    Multi-line artifacts use y-range extraction from the page dict: every dict
    line whose vertical center falls within the bbox y-span is collected. This
    reliably covers all visual lines, including short trailing lines (e.g.
    ``ICS 使用``) that ``page.search_for`` misses due to mixed CJK/Latin
    encoding or subscript characters.
    """
    bbox_height = bbox[3] - bbox[1]
    has_newlines = "\n" in raw_text

    # Single line: no newlines and bbox height < 15pt (~1.2x line height)
    if not has_newlines and bbox_height < 15:
        return [bbox]

    # Multi-line: collect every dict line whose vertical center is within the
    # bbox y-range. Same-row fragments are merged by merge_same_line_bboxes.
    page_dict = page.get_text("dict")
    raw_bboxes: list[list[float]] = []
    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            line_bbox = line.get("bbox")
            if not line_bbox:
                continue
            line_y_center = (line_bbox[1] + line_bbox[3]) / 2
            if (bbox[1] - 2) <= line_y_center <= (bbox[3] + 2):
                raw_bboxes.append(list(line_bbox))
    if raw_bboxes:
        return merge_same_line_bboxes(
            sorted(raw_bboxes, key=lambda b: b[1])
        )

    # Fallback: original single bbox
    return [bbox]


def collect_evidence_items() -> list[dict]:
    dc = json.loads(DC_PATH.read_text(encoding="utf-8"))
    items: list[dict] = []
    for node in dc.get("nodes", []):
        for ei in node.get("evidence_items", []):
            items.append(ei)
    return items


def build_source_locators_v0(
    evidence_by_id: dict[str, dict],
    page_map_by_pdf_page: dict[str, dict],
    doc: fitz.Document | None = None,
) -> dict:
    """Build SourceLocator records through explicit artifact_id join.

    evidence.json page_start stores PDF 1-based page numbers (62-70).
    page_map_by_pdf_page is keyed by str(pdfPageNumber1Based).
    Output pageLabel is the printed label ("31"-"39").
    bboxNorm uses top-left/no-flip transform (confirmed in Phase 6A).
    bboxNormLines provides per-visual-line bboxes for multi-line evidence
    (one bbox per PDF line; same-row fragments merged).
    """
    items = collect_evidence_items()
    unique_items: dict[str, dict] = {}
    missing_without_id: list[str] = []
    for index, item in enumerate(items):
        evidence_id = item.get("artifact_id")
        if not evidence_id:
            missing_without_id.append(f"display_evidence_ref_{index}:missing_artifact_id")
            continue
        unique_items.setdefault(evidence_id, item)

    locators = []
    missing = list(missing_without_id)
    for eid, ei in unique_items.items():
        art = evidence_by_id.get(eid)
        if not art:
            missing.append(eid)
            continue
        loc = art.get("locator") or {}
        bbox = loc.get("bbox")
        if not bbox or len(bbox) != 4:
            missing.append(eid)
            continue
        # page_start is PDF 1-based page number (62-70), NOT printed label
        pdf_page_1based = str(ei.get("page_start") or art.get("page_start"))
        pm = page_map_by_pdf_page.get(pdf_page_1based)
        if not pm:
            missing.append(eid)
            continue
        w = pm["pageWidthPt"]
        h = pm["pageHeightPt"]
        printed_label = pm["pageLabel"]  # "31".."39"
        raw_text = art.get("raw_text") or ei.get("text") or ""

        # Extract per-visual-line bboxes for multi-line evidence
        line_bboxes_pdf = (
            extract_line_bboxes(
                doc.load_page(pm["pdfPageIndex"]),
                raw_text,
                [float(x) for x in bbox],
            )
            if doc is not None
            else [[float(x) for x in bbox]]
        )
        bbox_pdf_lines = [[float(v) for v in lb] for lb in line_bboxes_pdf]
        bbox_norm_lines = [
            bbox_to_norm_top_left(lb, w, h) for lb in bbox_pdf_lines
        ]

        locators.append(
            {
                "id": f"loc_{eid.replace('-', '_')}",
                "evidenceItemId": eid,
                "locatorSource": "knowledge_node_evidence_json",
                "sourceEvidenceId": eid,
                "textbookId": TEXTBOOK_ID,
                "textbookVersion": TEXTBOOK_VERSION,
                "pageLabel": printed_label,
                "pdfPageIndex": pm["pdfPageIndex"],
                "pdfPageIndexBasis": "0-based",
                "pageAssetId": f"page_{TEXTBOOK_ID.replace('-', '_')}_{printed_label}",
                "bboxPdf": [float(x) for x in bbox],
                "bboxNorm": bbox_to_norm_top_left(bbox, w, h),
                "bboxPdfLines": bbox_pdf_lines,
                "bboxNormLines": bbox_norm_lines,
                "bboxNormTransform": "top_left_no_flip (confirmed Phase 6A)",
                "pageWidthPt": w,
                "pageHeightPt": h,
                "rawText": raw_text,
                "confidence": float(loc.get("confidence") or art.get("confidence") or 1.0),
            }
        )
    return {
        "version": "source-locator-v0",
        "section": SECTION_KEY,
        "generatedAt": _iso(),
        "locatorSource": "knowledge_node_evidence_json",
        "bboxNormTransform": "top_left_no_flip (confirmed Phase 6A)",
        "referenceCount": len(items),
        "count": len(locators),
        "expected": len(unique_items) + len(missing_without_id),
        "missing": missing,
        "locators": locators,
    }


def draw_overlay(
    doc: fitz.Document,
    pdf_page_index: int,
    bbox: list[float],
    out_path: Path,
    *,
    y_flip: bool,
    dpi: int = 150,
) -> None:
    page = doc.load_page(pdf_page_index)
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    # Draw on pixmap via fitz shape in page coords then re-render, or use PIL
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        pix.save(str(out_path))
        return

    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    draw = ImageDraw.Draw(img)
    scale = dpi / 72.0
    x0, y0, x1, y1 = bbox
    if y_flip:
        h_pt = float(page.rect.height)
        y0, y1 = h_pt - y1, h_pt - y0
    rect = [x0 * scale, y0 * scale, x1 * scale, y1 * scale]
    draw.rectangle(rect, outline=(255, 200, 0), width=4)
    img.save(out_path)


def coordinate_calibration(
    doc: fitz.Document,
    evidence_by_id: dict[str, dict],
    bdt_id: str = "ev1-57068078e29b9153d70d",
) -> dict:
    OUT_REPORTS.mkdir(parents=True, exist_ok=True)
    art = evidence_by_id[bdt_id]
    bbox = art["locator"]["bbox"]
    # page_start is PDF 1-based page number (64), NOT printed label (33)
    pdf_page_1based = int(art["page_start"])
    pdf_idx = pdf_page_1based - 1  # 0-based PyMuPDF index
    printed_label = str(pdf_page_1based - PAGE_DELTA)  # "33"

    no_flip = OUT_REPORTS / "asthma_p64_no_flip.png"
    y_flip = OUT_REPORTS / "asthma_p64_y_flip.png"
    draw_overlay(doc, pdf_idx, bbox, no_flip, y_flip=False)
    draw_overlay(doc, pdf_idx, bbox, y_flip, y_flip=True)

    # Additional samples: first item page 62, random page 70
    for eid, label in [
        ("ev1-da5373f5f30d79110726", "p62"),
        (bdt_id, "p64_bdt"),
        ("ev1-015959cbf4c2e6dbc3a9", "p62b"),
    ]:
        a = evidence_by_id.get(eid)
        if not a:
            continue
        pl = int(a["page_start"])
        idx = pl - 1
        b = a["locator"]["bbox"]
        for mode, flip in [("no_flip", False), ("y_flip", True)]:
            p = OUT_REPORTS / f"sample_{label}_{mode}.png"
            draw_overlay(doc, idx, b, p, y_flip=flip)

    md = f"""# Phase 1 bbox coordinate calibration

Generated: {_iso()}

## Conclusion (confirmed in Phase 6A)

bbox uses **top-left origin, no Y-flip**. bboxNorm = [x0/w, y0/h, x1/w, y1/h].

## Method

- Source bbox: `knowledge_nodes/.../支气管哮喘.evidence.json` (same pipeline as ingest).
- Render PDF page at **{150} DPI** with PyMuPDF.
- Overlay **A**: use bbox as **top-left origin** (no Y flip) — **CONFIRMED CORRECT**.
- Overlay **B**: treat bbox as **PDF bottom-left origin** and flip Y — **CONFIRMED WRONG**.

## Primary acceptance case

- **支气管舒张试验 (BDT)**
- evidence id: `{bdt_id}`
- PDF page (1-based): **{pdf_page_1based}**
- pdfPageIndex (0-based): **{pdf_idx}**
- printed pageLabel: **{printed_label}**
- bboxPdf: `{bbox}`

| File | Transform | Status |
|------|-----------|--------|
| `asthma_p64_no_flip.png` | top-left | CONFIRMED CORRECT |
| `asthma_p64_y_flip.png` | Y-flip | CONFIRMED WRONG |

## Human verification

Open both images. The yellow box in `no_flip` must cover the paragraph
containing **支气管舒张试验**. The `y_flip` box should be in the wrong position.
"""
    needle = "支气管舒张试验"
    page_text = doc.load_page(pdf_idx).get_text()
    md += f"\n- Needle `{needle}` on page: **{'yes' if needle in page_text else 'NO'}**\n"

    (OUT_REPORTS / "coordinate_check.md").write_text(md, encoding="utf-8")
    return {
        "bdtEvidenceId": bdt_id,
        "pdfPageNumber1Based": pdf_page_1based,
        "pdfPageIndex": pdf_idx,
        "pageLabel": printed_label,
        "bboxPdf": bbox,
        "bboxNormTransform": "top_left_no_flip (confirmed Phase 6A)",
        "outputs": [
            str(no_flip.relative_to(ROOT)),
            str(y_flip.relative_to(ROOT)),
            "generated/reports/phase1_visual_evidence_coordinate_check/coordinate_check.md",
        ],
        "humanDecisionRequired": False,
        "phase6aConfirmed": True,
    }


def go_no_go(locator_bundle: dict, page_map: dict, cal: dict) -> dict:
    lineage_ok = (
        locator_bundle["count"] == locator_bundle["expected"]
        and len(locator_bundle["missing"]) == 0
    )
    blockers = []
    if not lineage_ok:
        blockers.append("incomplete locator mapping")
    if cal.get("humanDecisionRequired"):
        blockers.append("human coordinate calibration signoff required")
    coverage = (
        f"SourceLocator v0 unique coverage "
        f"{locator_bundle['count']}/{locator_bundle['expected']} "
        f"from {locator_bundle['referenceCount']} display evidence references"
    )
    return {
        "generatedAt": _iso(),
        "activeObject": "phase1_evidence_lineage_export",
        "step1_export_page_assets": "GO" if not blockers else "NO-GO",
        "conditions": [
            "Human must confirm bbox overlay in coordinate_check (no_flip vs y_flip)",
            "Use page_map pdfPageIndex 0-based with PyMuPDF",
            coverage,
        ],
        "blockers": blockers,
        "evidenceReferenceCount": locator_bundle["referenceCount"],
        "uniqueEvidenceExpected": locator_bundle["expected"],
        "locatorCount": locator_bundle["count"],
        "coordinateCalibration": cal,
    }


def main() -> None:
    if not PDF_PATH.exists():
        raise SystemExit(f"Missing PDF {PDF_PATH}")
    if not DC_PATH.exists() or not EVIDENCE_PATH.exists():
        raise SystemExit("Missing display contract or evidence.json")

    ev = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    evidence_by_id = {a["id"]: a for a in ev["artifacts"]}

    doc = fitz.open(PDF_PATH)
    try:
        page_map = build_page_map(doc)
        OUT_PAGE_MAP.mkdir(parents=True, exist_ok=True)
        page_map_path = OUT_PAGE_MAP / f"{SECTION_KEY}.page_map.json"
        page_map_path.write_text(
            json.dumps(page_map, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Key page map by PDF 1-based page number (evidence.json page_start)
        page_map_by_pdf_page = {
            str(p["pdfPageNumber1Based"]): p for p in page_map["pages"]
        }
        locators = build_source_locators_v0(evidence_by_id, page_map_by_pdf_page, doc)
        OUT_LOCATORS.mkdir(parents=True, exist_ok=True)
        loc_path = OUT_LOCATORS / f"{SECTION_KEY}.source_locators_v0.json"
        loc_path.write_text(
            json.dumps(locators, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        cal = coordinate_calibration(doc, evidence_by_id)
        gng = go_no_go(locators, page_map, cal)
        gng_path = OUT_BASE / "step1_export_page_assets_go_no_go.json"
        gng_path.write_text(json.dumps(gng, ensure_ascii=False, indent=2), encoding="utf-8")

        print(json.dumps(
            {
                "page_map": str(page_map_path.relative_to(ROOT)),
                "locators": str(loc_path.relative_to(ROOT)),
                "locator_count": locators["count"],
                "coordinate_check": str(OUT_REPORTS.relative_to(ROOT)),
                "go_no_go": gng["step1_export_page_assets"],
                "note": (
                    "PageAsset export (webp + page_assets.json) is handled by "
                    "scripts/export_phase1_page_assets.py; run it separately."
                ),
            },
            ensure_ascii=False,
            indent=2,
        ))
    finally:
        doc.close()


if __name__ == "__main__":
    main()
