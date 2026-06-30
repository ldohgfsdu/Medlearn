"""Read-only bbox / PageIdentity audit for Phase 6A.

Scope: asthma PDF 62-70 only. Verifies:
1. PageIdentity map (PDF 1-based, pdfPageIndex 0-based, printed pageLabel)
2. evidence.json page_start semantics (PDF 1-based, NOT printed label)
3. bbox coordinate system (origin, units, Y-axis direction) via BDT calibration
4. Explicit ID join: artifact_id → evidence.json (no fuzzy text matching)
5. 10-item sample: ID, page identity, raw_text, bbox回查

Does NOT modify Document Tree, display contract, App, APK, DB, or remote.
If explicit ID connection or coordinate direction cannot be proven, stops.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import fitz  # noqa: E402

PDF_PATH = ROOT / "textbook" / "内科学（第10版）.pdf"
EVIDENCE_PATH = (
    ROOT / "generated/knowledge_nodes/internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.evidence.json"
)
DISPLAY_CONTRACT_PATH = (
    ROOT / "generated/display_contracts/internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.display_contract.json"
)
OUT_DIR = ROOT / "generated/reports/phase6a_bbox_pageidentity_audit"

# BDT evidence ID (支气管舒张试验) — the primary calibration target
BDT_EVIDENCE_ID = "ev1-57068078e29b9153d70d"
BDT_NEEDLE = "支气管舒张试验"

# Verified page identity from ADR-011 / SourceScopeManifest
PDF_PAGE_START_1BASED = 62
PDF_PAGE_END_1BASED = 70
PRINTED_PAGE_START = 31
PRINTED_PAGE_END = 39
PAGE_DELTA = PDF_PAGE_START_1BASED - PRINTED_PAGE_START  # 31


def load_evidence() -> dict[str, Any]:
    ev = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))
    return {a["id"]: a for a in ev["artifacts"]}


def load_display_evidence_refs() -> list[dict[str, Any]]:
    dc = json.loads(DISPLAY_CONTRACT_PATH.read_text(encoding="utf-8"))
    refs = []
    for node in dc.get("nodes", []):
        for ei in node.get("evidence_items", []):
            refs.append(ei)
    return refs


def verify_page_identity(doc: fitz.Document) -> dict[str, Any]:
    """Verify PDF page dimensions and printed page label for pages 62-70."""
    pages = []
    for pdf_page_1based in range(PDF_PAGE_START_1BASED, PDF_PAGE_END_1BASED + 1):
        pdf_page_index = pdf_page_1based - 1
        page = doc.load_page(pdf_page_index)
        rect = page.rect
        printed_label = str(pdf_page_1based - PAGE_DELTA)

        # Verify printed label appears in page text (usually in header/footer)
        page_text = page.get_text()
        label_found = printed_label in page_text

        pages.append({
            "pdf_page_number_1based": pdf_page_1based,
            "pdf_page_index_0based": pdf_page_index,
            "printed_page_label": printed_label,
            "page_width_pt": float(rect.width),
            "page_height_pt": float(rect.height),
            "printed_label_in_page_text": label_found,
        })

    all_labels_found = all(p["printed_label_in_page_text"] for p in pages)
    consistent_dims = len({(p["page_width_pt"], p["page_height_pt"]) for p in pages}) == 1

    return {
        "scope": "asthma",
        "pdf_page_range_1based": [PDF_PAGE_START_1BASED, PDF_PAGE_END_1BASED],
        "pdf_page_index_range_0based": [PDF_PAGE_START_1BASED - 1, PDF_PAGE_END_1BASED - 1],
        "printed_page_label_range": [str(PRINTED_PAGE_START), str(PRINTED_PAGE_END)],
        "page_delta": PAGE_DELTA,
        "all_printed_labels_found_in_text": all_labels_found,
        "consistent_page_dimensions": consistent_dims,
        "sample_dimensions": {
            "width_pt": pages[0]["page_width_pt"],
            "height_pt": pages[0]["page_height_pt"],
        },
        "pages": pages,
    }


def verify_evidence_page_semantics(evidence_by_id: dict[str, Any]) -> dict[str, Any]:
    """Verify evidence.json page_start stores PDF 1-based page numbers, not printed labels."""
    page_starts = [a.get("page_start") for a in evidence_by_id.values() if a.get("page_start")]
    min_ps, max_ps = min(page_starts), max(page_starts)

    # Evidence page_start should be 62-70 (PDF 1-based), NOT 31-39 (printed)
    in_pdf_range = all(PDF_PAGE_START_1BASED <= ps <= PDF_PAGE_END_1BASED for ps in page_starts)
    in_printed_range = all(PRINTED_PAGE_START <= ps <= PRINTED_PAGE_END for ps in page_starts)

    return {
        "evidence_page_start_min": min_ps,
        "evidence_page_start_max": max_ps,
        "all_in_pdf_range_62_70": in_pdf_range,
        "all_in_printed_range_31_39": in_printed_range,
        "conclusion": "page_start stores PDF 1-based page numbers"
        if in_pdf_range and not in_printed_range
        else "AMBIGUOUS — needs manual check",
        "existing_script_error": (
            "export_phase1_evidence_lineage.py treats page_start (62-70) as pageLabel; "
            "actual printed pageLabel is 31-39. pdfPageIndex = page_start - 1 is correct "
            "for PyMuPDF 0-based indexing, but the field is misnamed pageLabel."
        ),
    }


def verify_bbox_coordinate_system(
    doc: fitz.Document, evidence_by_id: dict[str, Any]
) -> dict[str, Any]:
    """Verify bbox origin and Y-axis direction using BDT calibration.

    Method: the evidence.json locator.bbox is a BLOCK-level bbox (full block
    width, line height). Find the BDT needle text in rawdict and verify the
    needle's char bbox is CONTAINED within the evidence bbox.

    Y direction: if needle Y falls inside evidence Y without flipping →
    top-left origin (no flip). If needle Y only fits after Y-flip →
    bottom-left origin (flip required). If neither → INCONCLUSIVE.
    """
    if BDT_EVIDENCE_ID not in evidence_by_id:
        return {"error": f"BDT evidence {BDT_EVIDENCE_ID} not found", "status": "BLOCKED"}

    art = evidence_by_id[BDT_EVIDENCE_ID]
    bbox = art.get("locator", {}).get("bbox")
    page_start = art.get("page_start")
    if not bbox or not page_start:
        return {"error": "BDT missing bbox or page_start", "status": "BLOCKED"}

    pdf_page_index = page_start - 1
    page = doc.load_page(pdf_page_index)
    page_height = float(page.rect.height)
    page_width = float(page.rect.width)

    # Find BDT needle in rawdict and get its char bbox (first occurrence only)
    raw = page.get_text("rawdict", sort=True)
    needle_char_bboxes: list[list[float]] = []
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                chars = span.get("chars", [])
                full_text = "".join(ch.get("c", "") for ch in chars)
                pos = full_text.find(BDT_NEEDLE)
                if pos >= 0:
                    for i in range(pos, pos + len(BDT_NEEDLE)):
                        cb = chars[i].get("bbox")
                        if cb:
                            needle_char_bboxes.append([float(x) for x in cb])
                    break  # first occurrence only
            if needle_char_bboxes:
                break
        if needle_char_bboxes:
            break

    if not needle_char_bboxes:
        return {
            "error": f"needle '{BDT_NEEDLE}' not found in rawdict on page {page_start}",
            "status": "BLOCKED",
        }

    # Compute needle's combined bbox from rawdict (first occurrence)
    raw_x0 = min(b[0] for b in needle_char_bboxes)
    raw_y0 = min(b[1] for b in needle_char_bboxes)
    raw_x1 = max(b[2] for b in needle_char_bboxes)
    raw_y1 = max(b[3] for b in needle_char_bboxes)
    raw_bbox = [raw_x0, raw_y0, raw_x1, raw_y1]

    # Evidence bbox (block-level)
    ev_x0, ev_y0, ev_x1, ev_y1 = bbox

    # Containment check: needle must be inside evidence bbox
    # No-flip: needle Y directly inside evidence Y
    no_flip_x_contains = ev_x0 <= raw_x0 and raw_x1 <= ev_x1
    no_flip_y_contains = ev_y0 <= raw_y0 and raw_y1 <= ev_y1
    no_flip_contains = no_flip_x_contains and no_flip_y_contains

    # Y-flip: flip needle Y and check containment
    flipped_raw_y0 = page_height - raw_y1
    flipped_raw_y1 = page_height - raw_y0
    y_flip_y_contains = ev_y0 <= flipped_raw_y0 and flipped_raw_y1 <= ev_y1
    y_flip_contains = no_flip_x_contains and y_flip_y_contains

    if no_flip_contains:
        conclusion = "top_left_origin_no_flip"
        transform = "bboxNorm = [x0/w, y0/h, x1/w, y1/h]"
    elif y_flip_contains:
        conclusion = "bottom_left_origin_y_flip_required"
        transform = "bboxNorm = [x0/w, (h-y1)/h, x1/w, (h-y0)/h]"
    else:
        conclusion = "INCONCLUSIVE — needle not contained in evidence bbox either way"
        transform = "UNKNOWN"

    return {
        "bdt_evidence_id": BDT_EVIDENCE_ID,
        "bdt_needle": BDT_NEEDLE,
        "pdf_page_1based": page_start,
        "pdf_page_index_0based": pdf_page_index,
        "page_width_pt": page_width,
        "page_height_pt": page_height,
        "evidence_bbox": bbox,
        "rawdict_needle_bbox": raw_bbox,
        "rawdict_char_count": len(needle_char_bboxes),
        "bbox_level": "block (evidence bbox spans full block width; needle is contained within)",
        "no_flip_x_contains": no_flip_x_contains,
        "no_flip_y_contains": no_flip_y_contains,
        "no_flip_contains": no_flip_contains,
        "y_flip_y_contains": y_flip_y_contains,
        "y_flip_contains": y_flip_contains,
        "conclusion": conclusion,
        "bboxNorm_transform": transform,
        "status": "OK" if conclusion != "INCONCLUSIVE" else "BLOCKED",
    }


def verify_explicit_id_join(
    evidence_by_id: dict[str, Any], display_refs: list[dict[str, Any]]
) -> dict[str, Any]:
    """Verify artifact_id → evidence.json is an explicit ID join, not fuzzy text."""
    total_refs = len(display_refs)
    refs_with_artifact_id = 0
    refs_resolved = 0
    refs_missing = []

    for ref in display_refs:
        aid = ref.get("artifact_id")
        if not aid:
            refs_missing.append({"display_ref_id": ref.get("id"), "reason": "no artifact_id"})
            continue
        refs_with_artifact_id += 1
        if aid in evidence_by_id:
            refs_resolved += 1
        else:
            refs_missing.append({"artifact_id": aid, "reason": "not in evidence.json"})

    all_have_artifact_id = refs_with_artifact_id == total_refs
    all_resolved = refs_resolved == total_refs
    none_unresolved = len(refs_missing) == 0
    status_ok = all_have_artifact_id and all_resolved and none_unresolved

    return {
        "locator_source": "knowledge_node_evidence_json",
        "join_field": "artifact_id",
        "display_evidence_refs_total": total_refs,
        "refs_with_artifact_id": refs_with_artifact_id,
        "refs_resolved_via_explicit_id": refs_resolved,
        "refs_unresolved": len(refs_missing),
        "fuzzy_text_matching_used": False,
        "all_have_artifact_id": all_have_artifact_id,
        "all_resolved": all_resolved,
        "missing_examples": refs_missing[:10],
        "status": "OK" if status_ok else "BLOCKED",
    }


def sample_10_evidence(
    doc: fitz.Document, evidence_by_id: dict[str, Any]
) -> dict[str, Any]:
    """Sample 10 evidence items, verify ID, page, raw_text, bbox回查."""
    import random

    all_ids = sorted(evidence_by_id.keys())
    # Deterministic sample: spread across pages
    random.seed(42)
    sample_ids = random.sample(all_ids, min(10, len(all_ids)))

    samples = []
    for eid in sample_ids:
        art = evidence_by_id[eid]
        page_start = art.get("page_start")
        raw_text = art.get("raw_text", "")
        loc = art.get("locator", {})
        bbox = loc.get("bbox")
        page = loc.get("page")

        result = {
            "evidence_id": eid,
            "page_start": page_start,
            "locator_page": page,
            "raw_text_preview": raw_text[:80],
            "bbox": bbox,
            "checks": {},
        }

        # Check 1: page_start == locator.page
        result["checks"]["page_start_equals_locator_page"] = (page_start == page)

        # Check 2: page_start in PDF range
        result["checks"]["page_start_in_asthma_range"] = (
            PDF_PAGE_START_1BASED <= page_start <= PDF_PAGE_END_1BASED
        )

        # Check 3: bbox exists and has 4 values
        result["checks"]["bbox_valid"] = bool(bbox) and len(bbox) == 4

        # Check 4: bbox within page bounds
        if bbox and page_start:
            pdf_idx = page_start - 1
            pg = doc.load_page(pdf_idx)
            result["checks"]["bbox_within_page"] = (
                0 <= bbox[0] <= pg.rect.width
                and 0 <= bbox[1] <= pg.rect.height
                and 0 <= bbox[2] <= pg.rect.width
                and 0 <= bbox[3] <= pg.rect.height
            )
            result["checks"]["bbox_x0_lt_x1"] = bbox[0] < bbox[2]
            result["checks"]["bbox_y0_lt_y1"] = bbox[1] < bbox[3]

            # Check 5: raw_text snippet found INSIDE the bbox (not just on page).
            # Extract text from the bbox region via rawdict char intersection,
            # then compare evidence snippet against that region text.
            ev_x0, ev_y0, ev_x1, ev_y1 = bbox
            raw = pg.get_text("rawdict", sort=True)
            region_chars: list[str] = []
            for block in raw.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        for ch in span.get("chars", []):
                            cb = ch.get("bbox")
                            if not cb or len(cb) < 4:
                                continue
                            # Char center inside bbox?
                            cx = (cb[0] + cb[2]) / 2
                            cy = (cb[1] + cb[3]) / 2
                            if (ev_x0 <= cx <= ev_x1 and ev_y0 <= cy <= ev_y1):
                                region_chars.append(ch.get("c", ""))
            region_text = " ".join("".join(region_chars).split())
            normalized_raw = " ".join(raw_text.split())
            snippet = normalized_raw[:30]
            result["checks"]["raw_text_snippet_in_bbox_region"] = (
                bool(snippet) and snippet in region_text
            )
            result["checks"]["region_text_nonempty"] = bool(region_text)
            result["region_text_preview"] = region_text[:80]
            result["raw_text_snippet"] = snippet

        # Check 6: bboxNorm in [0,1]
        if bbox and page_start:
            pdf_idx = page_start - 1
            pg = doc.load_page(pdf_idx)
            w, h = float(pg.rect.width), float(pg.rect.height)
            norm = [bbox[0] / w, bbox[1] / h, bbox[2] / w, bbox[3] / h]
            result["bboxNorm_top_left"] = norm
            result["checks"]["bboxNorm_in_0_1"] = all(0.0 <= v <= 1.0 for v in norm)

        all_pass = all(result["checks"].values())
        result["all_checks_pass"] = all_pass
        samples.append(result)

    passed = sum(1 for s in samples if s["all_checks_pass"])
    all_pass = passed == len(samples)
    return {
        "sample_size": len(samples),
        "all_checks_passed": passed,
        "samples": samples,
        "status": "OK" if all_pass else "BLOCKED",
    }


def generate_calibration_images(
    doc: fitz.Document, evidence_by_id: dict[str, Any]
) -> dict[str, Any]:
    """Generate no-flip and y-flip calibration PNGs for BDT."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return {"error": "PIL not available", "status": "SKIPPED"}

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    art = evidence_by_id[BDT_EVIDENCE_ID]
    bbox = art["locator"]["bbox"]
    page_start = art["page_start"]
    pdf_idx = page_start - 1
    page = doc.load_page(pdf_idx)
    h_pt = float(page.rect.height)

    dpi = 150
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    scale = dpi / 72.0

    outputs = []
    for mode, flip in [("no_flip", False), ("y_flip", True)]:
        im = img.copy()
        draw = ImageDraw.Draw(im)
        x0, y0, x1, y1 = bbox
        if flip:
            y0, y1 = h_pt - y1, h_pt - y0
        rect = [x0 * scale, y0 * scale, x1 * scale, y1 * scale]
        draw.rectangle(rect, outline=(255, 200, 0), width=4)
        out_path = OUT_DIR / f"bdt_p{page_start}_{mode}.png"
        im.save(out_path)
        outputs.append(str(out_path.relative_to(ROOT)))

    return {
        "bdt_evidence_id": BDT_EVIDENCE_ID,
        "page": page_start,
        "bbox": bbox,
        "outputs": outputs,
        "human_verification_required": True,
        "instruction": (
            "Open both PNGs. The yellow box must cover the paragraph containing "
            "'支气管舒张试验'. no_flip = top-left origin; y_flip = bottom-left origin."
        ),
    }


def main() -> None:
    if not PDF_PATH.exists():
        raise SystemExit(f"Missing PDF {PDF_PATH}")
    if not EVIDENCE_PATH.exists():
        raise SystemExit(f"Missing evidence {EVIDENCE_PATH}")
    if not DISPLAY_CONTRACT_PATH.exists():
        raise SystemExit(f"Missing display contract {DISPLAY_CONTRACT_PATH}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    evidence_by_id = load_evidence()
    display_refs = load_display_evidence_refs()
    doc = fitz.open(PDF_PATH)

    try:
        page_identity = verify_page_identity(doc)
        page_semantics = verify_evidence_page_semantics(evidence_by_id)
        bbox_system = verify_bbox_coordinate_system(doc, evidence_by_id)
        id_join = verify_explicit_id_join(evidence_by_id, display_refs)
        sample = sample_10_evidence(doc, evidence_by_id)
        calibration = generate_calibration_images(doc, evidence_by_id)
    finally:
        doc.close()

    # Determine overall status
    blockers = []
    if not page_identity["all_printed_labels_found_in_text"]:
        blockers.append("printed page labels not found in page text")
    if page_semantics["conclusion"].startswith("AMBIGUOUS"):
        blockers.append("evidence page_start semantics ambiguous")
    if bbox_system["status"] == "BLOCKED":
        blockers.append(f"bbox coordinate system: {bbox_system.get('error', 'inconclusive')}")
    if id_join["status"] == "BLOCKED":
        blockers.append(
            f"explicit ID join failed: resolved={id_join['refs_resolved_via_explicit_id']}/"
            f"{id_join['display_evidence_refs_total']}, "
            f"unresolved={id_join['refs_unresolved']}"
        )
    if sample["status"] != "OK":
        blockers.append(
            f"sample check failed: {sample['all_checks_passed']}/{sample['sample_size']} passed"
        )

    report = {
        "audit": "phase6a_bbox_pageidentity_audit",
        "scope": "asthma PDF 62-70",
        "page_identity": page_identity,
        "evidence_page_semantics": page_semantics,
        "bbox_coordinate_system": bbox_system,
        "explicit_id_join": id_join,
        "sample_10_evidence": sample,
        "calibration_images": calibration,
        "blockers": blockers,
        "overall_status": "OK" if not blockers else "BLOCKED",
    }

    out_path = OUT_DIR / "phase6a_audit_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "report": str(out_path.relative_to(ROOT)),
        "overall_status": report["overall_status"],
        "blockers": blockers,
        "bbox_conclusion": bbox_system.get("conclusion"),
        "id_join_resolved": id_join.get("refs_resolved_via_explicit_id"),
        "sample_passed": sample.get("all_checks_passed"),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
