#!/usr/bin/env python3
"""Merge Phase 1 page assets + source locators into app knowledge bundle artifacts.

Active object: phase1_merge_locators_bundle
No PageViewer / App UI / DB changes.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SECTION_KEY = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
TEXTBOOK_ID = "internal-medicine-10"

DC_PATH = (
    ROOT
    / "generated/display_contracts/internal-medicine-10"
    / f"{SECTION_KEY}.display_contract.json"
)
PAGE_ASSETS_PATH = ROOT / "generated/textbooks" / TEXTBOOK_ID / "page_assets.json"
LOCATORS_PATH = (
    ROOT
    / "generated/phase1_visual_evidence/source_locators"
    / TEXTBOOK_ID
    / f"{SECTION_KEY}.source_locators_v0.json"
)

BUNDLE_JSON_DIR = ROOT / "generated/app_bundle/phase1_visual_evidence" / TEXTBOOK_ID
BUNDLE_JSON = BUNDLE_JSON_DIR / f"{SECTION_KEY}.bundle.json"
TS_OUT = ROOT / "constants/phase1VisualEvidenceBundle.ts"
REPORT = ROOT / "generated/reports/phase1_merge_locators_bundle_summary.md"
EXPORT_EV1_TS = ROOT / "scripts/export_ev1_display_contracts_ts.py"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _compact_locator(loc: dict[str, Any]) -> dict[str, Any]:
    bbox_norm = loc.get("bboxNormTopLeftAssumption") or loc.get("bboxNorm")
    return {
        "id": loc["id"],
        "evidenceItemId": loc["evidenceItemId"],
        "locatorSource": loc.get("locatorSource"),
        "sourceEvidenceId": loc.get("sourceEvidenceId"),
        "sourceArtifactId": loc.get("sourceArtifactId"),
        "textbookId": loc["textbookId"],
        "textbookVersion": loc.get("textbookVersion", "10"),
        "pageLabel": loc["pageLabel"],
        "pdfPageIndex": loc["pdfPageIndex"],
        "pdfPageIndexBasis": loc.get("pdfPageIndexBasis", "0-based"),
        "pageAssetId": loc["pageAssetId"],
        "bboxPdf": loc.get("bboxPdf"),
        "bboxNorm": bbox_norm,
        "rawText": loc.get("rawText", ""),
        "confidence": loc.get("confidence", 1.0),
    }


def _compact_page_asset(page: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": page["id"],
        "textbookId": page["textbookId"],
        "textbookVersion": page.get("textbookVersion", "10"),
        "pageLabel": page["pageLabel"],
        "pdfPageIndex": page["pdfPageIndex"],
        "pdfPageIndexBasis": page.get("pdfPageIndexBasis", "0-based"),
        "imageWidth": page["imageWidth"],
        "imageHeight": page["imageHeight"],
        "localAssetKey": page["localAssetKey"],
        "relativePath": page.get("relativePath"),
        "bboxNormRule": page.get("bboxNormRule"),
    }


def patch_display_contract(
    locator_by_evidence: dict[str, dict[str, Any]],
) -> tuple[int, list[str]]:
    payload = json.loads(DC_PATH.read_text(encoding="utf-8"))
    missing: list[str] = []
    patched = 0
    for node in payload.get("nodes", []):
        for ei in node.get("evidence_items", []):
            eid = ei.get("artifact_id")
            if not eid:
                continue
            loc = locator_by_evidence.get(eid)
            if not loc:
                missing.append(eid)
                continue
            ei["sourceLocatorIds"] = [loc["id"]]
            ei["pageLabel"] = loc["pageLabel"]
            # page_start is the PDF 1-based page number (62-70), NOT the printed
            # pageLabel (31-39). Derive from pdfPageIndex (0-based) + 1.
            # Never backfill page_start from the printed pageLabel.
            if ei.get("page_start") is None:
                ei["page_start"] = int(loc["pdfPageIndex"]) + 1
            patched += 1
    DC_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return patched, missing


def validate(
    locators: list[dict[str, Any]],
    page_assets_by_id: dict[str, dict],
    evidence_stats: dict[str, int],
) -> dict[str, Any]:
    bad_norm = []
    missing_asset = []
    invalid_lineage = []
    for loc in locators:
        paid = loc.get("pageAssetId")
        if paid not in page_assets_by_id:
            missing_asset.append(loc["id"])
        bn = loc.get("bboxNorm")
        if bn:
            for v in bn:
                if v < 0 or v > 1:
                    bad_norm.append(loc["id"])
                    break
        for field in ("pageLabel", "pdfPageIndex", "rawText"):
            if loc.get(field) in (None, ""):
                bad_norm.append(f"{loc['id']}:missing_{field}")
        has_source_evidence = bool(loc.get("sourceEvidenceId"))
        has_source_artifact = bool(loc.get("sourceArtifactId"))
        locator_source = loc.get("locatorSource")
        if has_source_evidence == has_source_artifact:
            invalid_lineage.append(f"{loc['id']}:expected_exactly_one_source_id")
        elif (
            locator_source == "knowledge_node_evidence_json"
            and not has_source_evidence
        ):
            invalid_lineage.append(f"{loc['id']}:locator_source_mismatch")
        elif (
            locator_source == "pipeline_v3_source_artifacts"
            and not has_source_artifact
        ):
            invalid_lineage.append(f"{loc['id']}:locator_source_mismatch")
    unique_locator_ids = {loc["id"] for loc in locators}
    unique_evidence_ids = {loc["evidenceItemId"] for loc in locators}
    return {
        "evidenceReferencesExpected": evidence_stats["referenceCount"],
        "uniqueEvidenceItemsExpected": evidence_stats["uniqueEvidenceCount"],
        "missingArtifactIdReferences": evidence_stats["missingArtifactIdCount"],
        "locatorCount": len(locators),
        "uniqueLocatorIdCount": len(unique_locator_ids),
        "uniqueLocatorEvidenceIdCount": len(unique_evidence_ids),
        "missingPageAsset": missing_asset,
        "bboxNormOutOfRange": bad_norm,
        "invalidLineage": invalid_lineage,
        "ok": (
            len(locators) == evidence_stats["uniqueEvidenceCount"]
            and len(unique_locator_ids) == len(locators)
            and len(unique_evidence_ids) == evidence_stats["uniqueEvidenceCount"]
            and evidence_stats["missingArtifactIdCount"] == 0
            and len(missing_asset) == 0
            and len(bad_norm) == 0
            and len(invalid_lineage) == 0
        ),
    }


def write_ts_bundle(bundle: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(bundle, ensure_ascii=False, separators=(",", ":"))
    chunks = [body[i : i + 200_000] for i in range(0, len(body), 200_000)]
    chunk_body = json.dumps(chunks, ensure_ascii=False, indent=2)
    path.write_text(
        "// Auto-generated by scripts/merge_phase1_locators_bundle.py. Do not edit by hand.\n"
        "// Page images are NOT embedded — use localAssetKey + relativePath from pageAssets.\n\n"
        f"const PHASE1_VISUAL_EVIDENCE_JSON_CHUNKS = {chunk_body} as const\n\n"
        "export const PHASE1_VISUAL_EVIDENCE_BUNDLE = JSON.parse(\n"
        "  PHASE1_VISUAL_EVIDENCE_JSON_CHUNKS.join(''),\n"
        ") as Phase1VisualEvidenceBundle\n\n"
        "export type Phase1PageAsset = {\n"
        "  id: string\n"
        "  textbookId: string\n"
        "  textbookVersion: string\n"
        "  pageLabel: string\n"
        "  pdfPageIndex: number\n"
        "  pdfPageIndexBasis: string\n"
        "  imageWidth: number\n"
        "  imageHeight: number\n"
        "  localAssetKey: string\n"
        "  relativePath?: string\n"
        "  bboxNormRule?: { origin: string; yFlip: boolean; note?: string }\n"
        "}\n\n"
        "export type Phase1SourceLocator = {\n"
        "  id: string\n"
        "  evidenceItemId: string\n"
        "  locatorSource?: string\n"
        "  sourceEvidenceId?: string\n"
        "  sourceArtifactId?: string\n"
        "  pageLabel: string\n"
        "  pdfPageIndex: number\n"
        "  pageAssetId: string\n"
        "  bboxPdf?: number[]\n"
        "  bboxNorm?: number[]\n"
        "  rawText: string\n"
        "  confidence: number\n"
        "}\n\n"
        "export type Phase1VisualEvidenceBundle = {\n"
        "  version: string\n"
        "  sectionId: string\n"
        "  textbookId: string\n"
        "  generatedAt: string\n"
        "  pageAssets: Phase1PageAsset[]\n"
        "  sourceLocators: Phase1SourceLocator[]\n"
        "  sourceLocatorsById: Record<string, Phase1SourceLocator>\n"
        "  pageAssetsById: Record<string, Phase1PageAsset>\n"
        "}\n",
        encoding="utf-8",
    )


def evidence_reference_stats() -> dict[str, int]:
    dc = json.loads(DC_PATH.read_text(encoding="utf-8"))
    reference_count = 0
    evidence_ids: set[str] = set()
    missing_artifact_id_count = 0
    for node in dc.get("nodes", []):
        for item in node.get("evidence_items") or []:
            reference_count += 1
            evidence_id = item.get("artifact_id")
            if evidence_id:
                evidence_ids.add(evidence_id)
            else:
                missing_artifact_id_count += 1
    return {
        "referenceCount": reference_count,
        "uniqueEvidenceCount": len(evidence_ids),
        "missingArtifactIdCount": missing_artifact_id_count,
    }


def write_report(
    validation: dict[str, Any],
    patched: int,
    missing: list[str],
    *,
    refreshed_ev1_ts: bool,
) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# phase1_merge_locators_bundle — 完成报告",
        "",
        f"**Generated:** {_iso()}",
        "",
        "## 产物",
        "",
        f"- Bundle JSON: `{BUNDLE_JSON.relative_to(ROOT).as_posix()}`",
        f"- TS import: `constants/phase1VisualEvidenceBundle.ts`",
        f"- Patched display contract: `generated/display_contracts/.../支气管哮喘.display_contract.json`",
        f"- EV1 TS re-export: **{'yes' if refreshed_ev1_ts else 'skipped'}**",
        "",
        "## 校验",
        "",
        f"- display-contract evidence references: **{validation['evidenceReferencesExpected']}**",
        f"- unique evidence ids requiring locators: **{validation['uniqueEvidenceItemsExpected']}**",
        f"- evidence_items patched with sourceLocatorIds: **{patched}**",
        f"- locators: **{validation['locatorCount']}**",
        f"- invalid lineage records: **{len(validation['invalidLineage'])}**",
        f"- PASS: **{validation['ok']}**",
        "",
        "## 未做",
        "",
        "PageViewer, App UI, DB, Supabase, webp-in-JSON",
    ]
    if missing:
        lines.append(f"\nMissing locators for: {missing[:10]}...")
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    import subprocess
    import sys

    for p in (DC_PATH, PAGE_ASSETS_PATH, LOCATORS_PATH):
        if not p.exists():
            raise SystemExit(f"Missing: {p}")

    manifest = json.loads(PAGE_ASSETS_PATH.read_text(encoding="utf-8"))
    loc_data = json.loads(LOCATORS_PATH.read_text(encoding="utf-8"))
    locators = [_compact_locator(x) for x in loc_data["locators"]]
    page_assets = [_compact_page_asset(x) for x in manifest["pages"]]
    page_assets_by_id = {p["id"]: p for p in page_assets}
    locator_by_evidence = {loc["evidenceItemId"]: loc for loc in locators}
    locators_by_id = {loc["id"]: loc for loc in locators}

    evidence_stats = evidence_reference_stats()
    validation = validate(locators, page_assets_by_id, evidence_stats)

    patched, missing = patch_display_contract(locator_by_evidence)

    bundle = {
        "version": "phase1-visual-evidence-bundle-v1",
        "sectionId": SECTION_KEY,
        "textbookId": TEXTBOOK_ID,
        "generatedAt": _iso(),
        "pageAssets": page_assets,
        "sourceLocators": locators,
        "sourceLocatorsById": locators_by_id,
        "pageAssetsById": page_assets_by_id,
    }
    BUNDLE_JSON_DIR.mkdir(parents=True, exist_ok=True)
    BUNDLE_JSON.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    write_ts_bundle(bundle, TS_OUT)

    refreshed = False
    if "--skip-ev1-ts-export" not in sys.argv[1:]:
        rc = subprocess.call(
            [sys.executable, str(EXPORT_EV1_TS)],
            cwd=ROOT,
        )
        refreshed = rc == 0
        if rc != 0:
            print("[warn] ev1DisplayContracts.ts export failed; bundle JSON/TS still written")

    validation["displayContractPatched"] = patched
    validation["displayContractMissing"] = missing
    validation["ok"] = (
        validation["ok"]
        and not missing
        and patched == evidence_stats["referenceCount"]
    )
    write_report(validation, patched, missing, refreshed_ev1_ts=refreshed)

    print(json.dumps({**validation, "bundleJson": str(BUNDLE_JSON)}, ensure_ascii=False, indent=2))
    return 0 if validation["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
