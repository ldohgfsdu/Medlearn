#!/usr/bin/env python3
"""Phase 1 Step 1: export section page webp + page_assets.json (no App/DB).

Active object: phase1_export_page_assets
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parents[1]
SECTION_KEY = "第二篇_呼吸系统疾病__第四章_支气管哮喘"
TEXTBOOK_ID = "internal-medicine-10"
TEXTBOOK_VERSION = "10"
PDF_PATH = ROOT / "textbook" / "内科学（第10版）.pdf"
DPI = 150

PAGE_MAP_PATH = (
    ROOT
    / "generated/phase1_visual_evidence/page_maps"
    / f"{SECTION_KEY}.page_map.json"
)
LOCATORS_PATH = (
    ROOT
    / "generated/phase1_visual_evidence/source_locators"
    / TEXTBOOK_ID
    / f"{SECTION_KEY}.source_locators_v0.json"
)

OUT_PAGES = ROOT / "generated/textbooks" / TEXTBOOK_ID / "pages"
OUT_MANIFEST = ROOT / "generated/textbooks" / TEXTBOOK_ID / "page_assets.json"
OUT_REPORT = ROOT / "generated/reports/phase1_export_page_assets_summary.md"


def _iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def export_pages(page_map: dict) -> list[dict]:
    OUT_PAGES.mkdir(parents=True, exist_ok=True)
    # WebP export requires Pillow; do not silently degrade to PNG (Phase 6B
    # contract: webp only). Fail loudly if Pillow is unavailable so the
    # environment is reproducible.
    try:
        from PIL import Image  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Pillow is required for WebP page export. "
            "Install with: python -m pip install pillow"
        ) from exc

    assets: list[dict] = []
    doc = fitz.open(PDF_PATH)
    try:
        for entry in page_map["pages"]:
            label = entry["pageLabel"]  # printed label, e.g. "33"
            idx = int(entry["pdfPageIndex"])  # 0-based PyMuPDF index
            page = doc.load_page(idx)
            mat = fitz.Matrix(DPI / 72, DPI / 72)
            pix = page.get_pixmap(matrix=mat, alpha=False)
            out_file = OUT_PAGES / f"{label}.webp"
            from PIL import Image

            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            img.save(str(out_file), format="WEBP", quality=85)
            page_asset_id = f"page_{TEXTBOOK_ID.replace('-', '_')}_{label}"
            local_key = f"im10_page_{label}"
            assets.append(
                {
                    "id": page_asset_id,
                    "textbookId": TEXTBOOK_ID,
                    "textbookVersion": TEXTBOOK_VERSION,
                    "pageLabel": label,
                    "pdfPageIndex": idx,
                    "pdfPageNumber1Based": entry.get("pdfPageNumber1Based", idx + 1),
                    "pdfPageIndexBasis": entry.get("pdfPageIndexBasis", "0-based"),
                    "imageWidth": pix.width,
                    "imageHeight": pix.height,
                    "imageDpi": DPI,
                    "imageFormat": "webp",
                    "localAssetKey": local_key,
                    "relativePath": str(
                        out_file.relative_to(ROOT).as_posix()
                    ),
                    "bboxNormRule": {
                        "origin": "top-left",
                        "yFlip": False,
                        "note": (
                            "Use bboxNorm from SourceLocator v0 "
                            "(top-left/no-flip, confirmed Phase 6A)"
                        ),
                    },
                }
            )
    finally:
        doc.close()
    return assets


def validate_locators(locators: dict, assets_by_id: dict[str, dict]) -> dict:
    missing = []
    for loc in locators.get("locators", []):
        paid = loc.get("pageAssetId")
        if paid not in assets_by_id:
            missing.append({"locatorId": loc["id"], "pageAssetId": paid})
    return {
        "totalLocators": locators.get("count", 0),
        "missingPageAsset": missing,
        "ok": len(missing) == 0,
    }


def write_report(
    page_map: dict,
    assets: list[dict],
    validation: dict,
    triple_check: list[dict],
) -> None:
    lines = [
        "# phase1_export_page_assets — 完成报告",
        "",
        f"**Generated:** {_iso()}",
        f"**Repo:** `F:/ml`",
        f"**Section:** 支气管哮喘 PDF p.62–70 (printed p.31–39)",
        "",
        "## 三页抽验（哮喘节页身份映射）",
        "",
        "Phase 6A 已确认：`pageLabel` 为印刷页码（31–39）；"
        "`pdfPageIndex` 为 0-based（61–69）；"
        "`pdfPageNumber1Based` 为 PDF 1-based（62–70）；"
        "`page_delta = 31`（**仅本节试点**，勿推广全书）。",
        "",
        "| pageLabel | pdfPageNumber1Based | pdfPageIndex | content anchor | hit |",
        "|-----------|----------------------|--------------|----------------|-----|",
    ]
    for row in triple_check:
        lines.append(
            f"| {row['pageLabel']} | {row['pdfPageNumber1Based']} | {row['pdfPageIndex']} | {row['needle'][:30]} | {row['hit']} |"
        )
    lines.extend(
        [
            "",
            "## 导出结果",
            "",
            f"- WebP 页数: **{len(assets)}**",
            f"- 目录: `generated/textbooks/{TEXTBOOK_ID}/pages/`",
            f"- Manifest: `generated/textbooks/{TEXTBOOK_ID}/page_assets.json`",
            "",
            "## SourceLocator 连通性",
            "",
            f"- Locators: **{validation['totalLocators']}**",
            f"- 缺 PageAsset: **{len(validation['missingPageAsset'])}**",
            f"- 判定: **{'PASS' if validation['ok'] else 'FAIL'}**",
            "",
            "## 坐标系（冻结待主人看图）",
            "",
            "- 规则: 左上原点，`bboxNorm = bboxPdf / pageWidthHeight`，**Y 不翻转**",
            "- 请主人确认: `generated/reports/phase1_visual_evidence_coordinate_check/asthma_p64_no_flip.png`",
            "",
            "## 未做（按范围）",
            "",
            "PageViewer / App / bundle merge / DB / 全书导出",
        ]
    )
    OUT_REPORT.parent.mkdir(parents=True, exist_ok=True)
    OUT_REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def triple_page_content_check() -> list[dict]:
    """Verify content anchors on 3 printed pages (31, 33, 39).

    Phase 6A confirmed: pageLabel is the printed label (31-39);
    pdfPageIndex is 0-based (61-69); pdfPageNumber1Based is 62-70.
    page_delta = 31 (PDF 1-based page - printed label).
    """
    import fitz as fz

    ev_path = (
        ROOT
        / "generated/knowledge_nodes/internal-medicine-10"
        / f"{SECTION_KEY}.evidence.json"
    )
    ev = json.loads(ev_path.read_text(encoding="utf-8"))
    # Map PDF 1-based page -> first evidence raw_text snippet
    by_pdf_page: dict[int, str] = {}
    for a in ev["artifacts"]:
        p = a["page_start"]  # PDF 1-based page number (62-70)
        if p not in by_pdf_page:
            by_pdf_page[p] = a.get("raw_text", "")[:20]
    # Printed pageLabel -> (pdfPageNumber1Based, needle)
    # 31 -> PDF 62 (支气管哮喘), 33 -> PDF 64 (BDT), 39 -> PDF 70 (预后)
    targets = {
        "31": (62, "支气管哮喘"),
        "33": (64, "支气管舒张试验"),
        "39": (70, by_pdf_page.get(70, "预后")[:12]),
    }
    doc = fz.open(PDF_PATH)
    rows = []
    try:
        for printed_label, (pdf_page_1based, needle) in targets.items():
            idx = pdf_page_1based - 1  # 0-based PyMuPDF index
            t = doc.load_page(idx).get_text()
            rows.append(
                {
                    "pageLabel": printed_label,
                    "pdfPageNumber1Based": pdf_page_1based,
                    "pdfPageIndex": idx,
                    "needle": needle,
                    "hit": needle in t,
                }
            )
    finally:
        doc.close()
    return rows


def main() -> None:
    for p in (PAGE_MAP_PATH, LOCATORS_PATH, PDF_PATH):
        if not p.exists():
            raise SystemExit(f"Missing input: {p}")

    page_map = json.loads(PAGE_MAP_PATH.read_text(encoding="utf-8"))
    locators = json.loads(LOCATORS_PATH.read_text(encoding="utf-8"))

    triple = triple_page_content_check()
    if not all(r["hit"] for r in triple):
        raise SystemExit(f"Triple page check failed: {triple}")

    assets = export_pages(page_map)
    assets_by_id = {a["id"]: a for a in assets}

    manifest = {
        "version": "page-assets-v1",
        "textbookId": TEXTBOOK_ID,
        "textbookVersion": TEXTBOOK_VERSION,
        "section": SECTION_KEY,
        "generatedAt": _iso(),
        "pageMappingNote": (
            "Asthma pilot only: pageLabel is the printed label (31-39); "
            "pdfPageIndex is 0-based (61-69); pdfPageNumber1Based is 62-70; "
            "page_delta=31 (PDF 1-based - printed). Do not generalize to full "
            "book without a per-section page map."
        ),
        "pages": assets,
    }
    OUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    OUT_MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    validation = validate_locators(locators, assets_by_id)
    write_report(page_map, assets, validation, triple)

    print(
        json.dumps(
            {
                "pages_exported": len(assets),
                "manifest": str(OUT_MANIFEST),
                "locator_validation": validation["ok"],
                "triple_check": triple,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    if not validation["ok"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()