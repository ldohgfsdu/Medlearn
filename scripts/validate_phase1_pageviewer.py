#!/usr/bin/env python3
"""Validate Phase 1 PageViewer wiring without requiring a device."""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_JSON_DIR = ROOT / "generated/app_bundle/phase1_visual_evidence/internal-medicine-10"
REGISTRY = ROOT / "constants/phase1PageImageAssets.ts"
ASSETS = ROOT / "assets/textbooks/internal-medicine-10/pages"
DISPLAY_CONTRACT_DIR = ROOT / "generated/display_contracts/internal-medicine-10"
REPORT = ROOT / "generated/reports/phase1_pageviewer_visual_evidence_summary.md"
EXPORT_DIR = ROOT / ".tmp-phase1-export"


def count_exported_android_webp_assets() -> str:
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        raise RuntimeError("npx was not found on PATH")

    subprocess.run(
        [
            npx,
            "expo",
            "export",
            "--platform",
            "android",
            "--output-dir",
            str(EXPORT_DIR),
        ],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        text=True,
        timeout=600,
        check=False,
    )

    meta = EXPORT_DIR / "metadata.json"
    if not meta.exists():
        raise RuntimeError("expo export did not produce metadata.json")

    metadata = json.loads(meta.read_text(encoding="utf-8"))
    android_assets = metadata["fileMetadata"]["android"]["assets"]
    return str(len([asset for asset in android_assets if asset.get("ext") == "webp"]))


def git_tracked_files(paths: list[Path]) -> set[str]:
    """Return the subset of `paths` that are tracked by git.

    A clean checkout only contains tracked files, so an untracked webp would
    be missing after clone. This gate catches assets that exist on the local
    filesystem but were never committed.
    """
    if not paths:
        return set()
    rel_paths = [str(p.relative_to(ROOT).as_posix()) for p in paths]
    result = subprocess.run(
        ["git", "ls-files", "--"] + rel_paths,
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        text=True,
        check=False,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def write_report(
    *,
    ok: bool,
    keys: list[str],
    missing_files: list[str],
    untracked_assets: list[str],
    locators: list[dict],
    missing_asset: list[str],
    bad_norm: list[str],
    evidence_references: int,
    missing_locator_references: list[str],
    export_webp: str,
) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report_status = "PASS" if ok else "FAIL"
    report_lines = [
        "# phase1_pageviewer_visual_evidence",
        "",
        f"- require registry keys: **{len(keys)}**",
        f"- missing asset files: **{len(missing_files)}**",
        f"- untracked asset files (would be missing on clean checkout): **{len(untracked_assets)}**",
        f"- locators: **{len(locators)}**",
        f"- display-contract evidence references: **{evidence_references}**",
        f"- evidence references missing a resolvable SourceLocator: **{len(missing_locator_references)}**",
        f"- missing pageAsset: **{len(missing_asset)}**",
        f"- bboxNorm out of range: **{len(bad_norm)}**",
        f"- validation result: **{report_status}**",
        f"- expo export webp bundled: **{export_webp}** (9 expected)",
        "- release APK built in this run: **no** - run locally with JDK/Android SDK:",
        "",
        "  `npm run build:android:preview:local`  or  `npm run build:android:local-arm64`",
        "",
        "## Path chain for APK",
        "",
        "```text",
        "generated/textbooks/.../pages/*.webp   # pipeline only; Metro blockList excludes generated/",
        "  -> scripts/sync_phase1_page_assets_to_app.py",
        "  -> assets/textbooks/internal-medicine-10/pages/{31..39}.webp",
        "  -> static require() in constants/phase1PageImageAssets.ts",
        "  -> Metro asset bundle (9x webp in expo export)",
        "  -> resolvePageImageSource(localAssetKey)",
        "  -> PageViewer <Image source={number} />",
        "```",
        "",
        "Relevant app files:",
        "",
        "- `app/textbook/page-viewer.tsx`",
        "- `app/textbook/[sectionId]/unit/[unitId].tsx` (textbook source Pxx link)",
        "- `constants/phase1PageImageAssets.ts`",
        "- `services/phase1VisualEvidenceService.ts`",
        "",
        "## Highlight style",
        "",
        "Runtime marker fill `rgba(255,230,80,0.45)`; the webp page images stay clean.",
        "",
        "## Manual APK check",
        "",
        "1. Build and install the APK on a device.",
        "2. Open bronchial asthma -> source evidence -> textbook source P33 (printed pageLabel).",
        "3. Confirm the P33 image renders and the highlighter aligns with the source paragraph.",
    ]
    REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-export",
        action="store_true",
        help="Run npx expo export and assert 9 webp assets (slow).",
    )
    args = parser.parse_args()

    registry_text = REGISTRY.read_text(encoding="utf-8")
    keys = re.findall(r"(im10_page_\d+):", registry_text)
    missing_files = [
        key
        for key in keys
        if not (ASSETS / f"{key.replace('im10_page_', '')}.webp").exists()
    ]

    # Clean-checkout gate: every referenced webp must be git-tracked, not just
    # present on the local filesystem. An untracked asset passes the .exists()
    # check above but would be missing after a fresh clone, breaking Metro.
    asset_paths = [ASSETS / f"{key.replace('im10_page_', '')}.webp" for key in keys]
    tracked = git_tracked_files(asset_paths)
    untracked_assets = [
        key for key, p in zip(keys, asset_paths)
        if str(p.relative_to(ROOT).as_posix()) not in tracked
    ]

    bundle_paths = sorted(BUNDLE_JSON_DIR.glob("*.bundle.json"))
    if not bundle_paths:
        raise FileNotFoundError(f"No Phase 1 bundle JSON found in {BUNDLE_JSON_DIR}")

    bundle = json.loads(bundle_paths[0].read_text(encoding="utf-8"))
    locators = bundle["sourceLocators"]
    locators_by_id = bundle["sourceLocatorsById"]
    page_assets_by_id = bundle["pageAssetsById"]

    display_contract_paths = sorted(DISPLAY_CONTRACT_DIR.glob("*支气管哮喘.display_contract.json"))
    if not display_contract_paths:
        raise FileNotFoundError("No asthma display contract found")
    display_contract = json.loads(display_contract_paths[0].read_text(encoding="utf-8"))
    evidence_items = [
        item
        for node in display_contract.get("nodes", [])
        for item in node.get("evidence_items", [])
    ]
    missing_locator_references = []
    for item in evidence_items:
        evidence_id = item.get("artifact_id") or "<missing-artifact-id>"
        locator_ids = item.get("sourceLocatorIds") or []
        if not locator_ids or any(locator_id not in locators_by_id for locator_id in locator_ids):
            missing_locator_references.append(evidence_id)

    missing_asset: list[str] = []
    bad_norm: list[str] = []
    for loc in locators:
        if loc.get("pageAssetId") not in page_assets_by_id:
            missing_asset.append(loc["id"])
        bbox_norm = loc.get("bboxNorm") or []
        if len(bbox_norm) != 4 or any(value < 0 or value > 1 for value in bbox_norm):
            bad_norm.append(loc["id"])

    ok = (
        len(keys) == 9
        and not missing_files
        and not untracked_assets
        and not missing_asset
        and not bad_norm
        and not missing_locator_references
    )

    export_webp = "skipped (use --check-export)"
    if args.check_export:
        try:
            export_webp = count_exported_android_webp_assets()
        except Exception as exc:  # noqa: BLE001
            export_webp = f"error:{exc}"
        ok = ok and export_webp == "9"

    write_report(
        ok=ok,
        keys=keys,
        missing_files=missing_files,
        untracked_assets=untracked_assets,
        locators=locators,
        missing_asset=missing_asset,
        bad_norm=bad_norm,
        evidence_references=len(evidence_items),
        missing_locator_references=missing_locator_references,
        export_webp=export_webp,
    )
    print(json.dumps({"ok": ok, "keys": len(keys), "locators": len(locators)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
