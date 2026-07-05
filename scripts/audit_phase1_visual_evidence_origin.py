#!/usr/bin/env python3
"""Read-only audit: EV1 asthma visual-evidence origin (current contract).

Audits the actual Phase 1 contract:

    display_contract evidence_items.sourceLocatorIds
    -> generated/phase1_visual_evidence/source_locators/...source_locators_v0.json
    -> SourceLocator.pageAssetId
    -> generated/textbooks/internal-medicine-10/page_assets.json
    -> page image files on disk

No longer checks originArtifactIds (those belong to the parser lineage, not
the current bridge). Uses only explicit ID joins; no fuzzy text matching.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SECTION_KEY = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
TEXTBOOK_ID = "internal-medicine-10"

DC_PATH = (
    ROOT
    / "generated/display_contracts"
    / TEXTBOOK_ID
    / f"{SECTION_KEY}.display_contract.json"
)
LOCATORS_PATH = (
    ROOT
    / "generated/phase1_visual_evidence/source_locators"
    / TEXTBOOK_ID
    / f"{SECTION_KEY}.source_locators_v0.json"
)
PAGE_ASSETS_PATH = (
    ROOT / "generated/textbooks" / TEXTBOOK_ID / "page_assets.json"
)
_LEGAL_LOCATOR_SOURCES = frozenset({
    "knowledge_node_evidence_json",
    "pipeline_v3_source_artifacts",
})


def collect_evidence_items(dc: dict) -> list[dict]:
    """Collect every evidence_items entry from the display contract."""
    items: list[dict] = []
    for node in dc.get("nodes", []):
        for ei in node.get("evidence_items", []):
            items.append(ei)
    return items


def main(write_report: bool = True) -> None:
    errors: list[str] = []
    warnings: list[str] = []
    details: dict = {}

    # ------------------------------------------------------------------ #
    # 1. Load display contract
    # ------------------------------------------------------------------ #
    if not DC_PATH.exists():
        raise SystemExit(f"MISSING display contract: {DC_PATH}")
    dc = json.loads(DC_PATH.read_text(encoding="utf-8"))
    evidence_items = collect_evidence_items(dc)
    details["evidence_items_total"] = len(evidence_items)
    details["section_title"] = dc.get("section_title")
    details["textbook_id"] = dc.get("textbook_id")

    # ------------------------------------------------------------------ #
    # 2. Load source locators
    # ------------------------------------------------------------------ #
    if not LOCATORS_PATH.exists():
        raise SystemExit(f"MISSING source locators: {LOCATORS_PATH}")
    loc_doc = json.loads(LOCATORS_PATH.read_text(encoding="utf-8"))
    locators_by_id: dict[str, dict] = {
        loc["id"]: loc for loc in loc_doc.get("locators", [])
    }
    details["source_locators_total"] = loc_doc.get("count", 0)
    details["locator_source"] = loc_doc.get("locatorSource")

    # ------------------------------------------------------------------ #
    # 3. Load page assets
    # ------------------------------------------------------------------ #
    if not PAGE_ASSETS_PATH.exists():
        raise SystemExit(f"MISSING page assets: {PAGE_ASSETS_PATH}")
    pa_doc = json.loads(PAGE_ASSETS_PATH.read_text(encoding="utf-8"))
    page_assets_by_id: dict[str, dict] = {
        p["id"]: p for p in pa_doc.get("pages", [])
    }
    details["page_assets_total"] = len(page_assets_by_id)

    # ------------------------------------------------------------------ #
    # 4. Every evidence item -> sourceLocatorIds -> SourceLocator
    # ------------------------------------------------------------------ #
    items_missing_locator_ids: list[str] = []
    items_with_empty_locator_ids: list[str] = []
    unresolvable_locator_refs: list[tuple[str, str]] = []

    for ei in evidence_items:
        aid = ei.get("artifact_id", "<missing>")
        loc_ids = ei.get("sourceLocatorIds")
        if loc_ids is None:
            items_missing_locator_ids.append(aid)
            continue
        if not isinstance(loc_ids, list) or len(loc_ids) == 0:
            items_with_empty_locator_ids.append(aid)
            continue
        for lid in loc_ids:
            if lid not in locators_by_id:
                unresolvable_locator_refs.append((aid, lid))

    details["items_missing_sourceLocatorIds_field"] = items_missing_locator_ids
    details["items_with_empty_sourceLocatorIds"] = items_with_empty_locator_ids
    details["unresolvable_locator_refs"] = unresolvable_locator_refs

    if items_missing_locator_ids:
        errors.append(
            f"{len(items_missing_locator_ids)} evidence items lack sourceLocatorIds"
        )
    if items_with_empty_locator_ids:
        errors.append(
            f"{len(items_with_empty_locator_ids)} evidence items have empty sourceLocatorIds"
        )
    if unresolvable_locator_refs:
        errors.append(
            f"{len(unresolvable_locator_refs)} sourceLocatorIds do not resolve"
        )

    # ------------------------------------------------------------------ #
    # 5. Every SourceLocator -> pageAssetId -> PageAsset
    # ------------------------------------------------------------------ #
    locators_missing_asset: list[str] = []
    locators_bad_bbox_norm: list[str] = []
    locators_missing_page_label: list[str] = []
    locators_missing_pdf_page_index: list[str] = []
    locators_missing_locator_source: list[str] = []

    locators_bad_locator_source: list[str] = []
    locators_missing_both_source_ids: list[str] = []
    locators_wrong_source_id: list[str] = []

    for loc in locators_by_id.values():
        lid = loc["id"]

        # locatorSource: must be a known legal value, and exactly one of
        # sourceEvidenceId / sourceArtifactId must match.
        ls = loc.get("locatorSource")
        if not ls or ls not in _LEGAL_LOCATOR_SOURCES:
            locators_missing_locator_source.append(lid)
        else:
            seid = loc.get("sourceEvidenceId")
            said = loc.get("sourceArtifactId")
            has_se = bool(seid)
            has_sa = bool(said)
            if not has_se and not has_sa:
                locators_missing_both_source_ids.append(lid)
            elif ls == "knowledge_node_evidence_json" and not has_se:
                locators_wrong_source_id.append(
                    f"{lid}: locatorSource={ls} but sourceEvidenceId missing"
                )
            elif ls == "pipeline_v3_source_artifacts" and not has_sa:
                locators_wrong_source_id.append(
                    f"{lid}: locatorSource={ls} but sourceArtifactId missing"
                )
            elif has_se and has_sa:
                locators_wrong_source_id.append(
                    f"{lid}: both sourceEvidenceId and sourceArtifactId present"
                )

        # pageLabel
        if not loc.get("pageLabel"):
            locators_missing_page_label.append(lid)

        # pdfPageIndex
        if loc.get("pdfPageIndex") is None:
            locators_missing_pdf_page_index.append(lid)

        # pageAssetId
        paid = loc.get("pageAssetId")
        if not paid or paid not in page_assets_by_id:
            locators_missing_asset.append(lid)

        # bboxNorm ∈ [0, 1]
        bbox = loc.get("bboxNorm")
        if bbox and isinstance(bbox, list) and len(bbox) == 4:
            if any(v < 0 or v > 1 for v in bbox):
                locators_bad_bbox_norm.append(lid)
        else:
            locators_bad_bbox_norm.append(lid)

    details["locators_missing_pageAsset"] = locators_missing_asset
    details["locators_bad_bboxNorm"] = locators_bad_bbox_norm
    details["locators_missing_pageLabel"] = locators_missing_page_label
    details["locators_missing_pdfPageIndex"] = locators_missing_pdf_page_index
    details["locators_missing_locatorSource"] = locators_missing_locator_source
    details["locators_missing_both_source_ids"] = locators_missing_both_source_ids
    details["locators_wrong_source_id"] = locators_wrong_source_id

    if locators_missing_asset:
        errors.append(
            f"{len(locators_missing_asset)} locators have unresolvable pageAssetId"
        )
    if locators_bad_bbox_norm:
        errors.append(
            f"{len(locators_bad_bbox_norm)} locators have missing or out-of-range bboxNorm"
        )
    if locators_missing_page_label:
        errors.append(f"{len(locators_missing_page_label)} locators missing pageLabel")
    if locators_missing_pdf_page_index:
        errors.append(
            f"{len(locators_missing_pdf_page_index)} locators missing pdfPageIndex"
        )
    if locators_missing_locator_source:
        errors.append(
            f"{len(locators_missing_locator_source)} locators have missing or illegal locatorSource"
        )
    if locators_missing_both_source_ids:
        errors.append(
            f"{len(locators_missing_both_source_ids)} locators have neither sourceEvidenceId nor sourceArtifactId"
        )
    if locators_wrong_source_id:
        errors.append(
            f"{len(locators_wrong_source_id)} locators have source ID mismatch: {locators_wrong_source_id[:3]}"
        )

    # ------------------------------------------------------------------ #
    # 6. Every PageAsset -> image file on disk
    # ------------------------------------------------------------------ #
    missing_image_files: list[str] = []
    for pa in page_assets_by_id.values():
        rel = pa.get("relativePath", "")
        if rel:
            img_path = ROOT / rel
            if not img_path.exists():
                missing_image_files.append(rel)
        else:
            missing_image_files.append(pa.get("id", "?"))

    details["missing_image_files"] = missing_image_files
    if missing_image_files:
        errors.append(
            f"{len(missing_image_files)} page image files missing on disk"
        )

    # ------------------------------------------------------------------ #
    # 7. PageAsset fields
    # ------------------------------------------------------------------ #
    page_assets_missing_page_label: list[str] = []
    page_assets_missing_pdf_page_index: list[str] = []
    for pa in page_assets_by_id.values():
        if not pa.get("pageLabel"):
            page_assets_missing_page_label.append(pa["id"])
        if pa.get("pdfPageIndex") is None:
            page_assets_missing_pdf_page_index.append(pa["id"])

    details["page_assets_missing_pageLabel"] = page_assets_missing_page_label
    details["page_assets_missing_pdfPageIndex"] = page_assets_missing_pdf_page_index

    if page_assets_missing_page_label:
        errors.append(
            f"{len(page_assets_missing_page_label)} page assets missing pageLabel"
        )
    if page_assets_missing_pdf_page_index:
        errors.append(
            f"{len(page_assets_missing_pdf_page_index)} page assets missing pdfPageIndex"
        )

    # ------------------------------------------------------------------ #
    # 8. originArtifactIds — informational only, NOT a blocker
    # ------------------------------------------------------------------ #
    items_with_origin: int = sum(
        1 for ei in evidence_items
        if ei.get("originArtifactIds") or ei.get("origin_artifact_ids")
    )
    details["items_with_originArtifactIds"] = items_with_origin
    warnings.append(
        f"{items_with_origin}/{len(evidence_items)} evidence items carry "
        "originArtifactIds (informational — not required for current asthma bridge)"
    )

    # ------------------------------------------------------------------ #
    # Report
    # ------------------------------------------------------------------ #
    ok = len(errors) == 0
    details["errors"] = errors
    details["warnings"] = warnings
    details["decision"] = "PASS" if ok else "FAIL"

    if write_report:
        out_dir = ROOT / "generated/reports"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "phase1_visual_evidence_origin_audit_asthma.json"
        out_path.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding="utf-8")
        print(out_path)
    print(json.dumps(
        {
            "evidence_items_total": details["evidence_items_total"],
            "source_locators_total": details["source_locators_total"],
            "page_assets_total": details["page_assets_total"],
            "items_with_sourceLocatorIds": (
                details["evidence_items_total"]
                - len(items_missing_locator_ids)
                - len(items_with_empty_locator_ids)
            ),
            "locators_with_valid_pageAsset": len(locators_by_id) - len(locators_missing_asset),
            "locators_with_valid_bboxNorm": len(locators_by_id) - len(locators_bad_bbox_norm),
            "decision": details["decision"],
            "errors": errors,
        },
        ensure_ascii=False,
        indent=2,
    ))

    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
