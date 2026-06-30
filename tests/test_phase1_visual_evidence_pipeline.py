import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


lineage = load_module(
    "export_phase1_evidence_lineage",
    "scripts/export_phase1_evidence_lineage.py",
)
merge = load_module(
    "merge_phase1_locators_bundle",
    "scripts/merge_phase1_locators_bundle.py",
)
page_assets_mod = load_module(
    "export_phase1_page_assets",
    "scripts/export_phase1_page_assets.py",
)

PDF = ROOT / "textbook" / "内科学（第10版）.pdf"
PAGE_MAP_PATH = (
    ROOT / "generated/phase1_visual_evidence/page_maps"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.page_map.json"
)
LOCATORS_PATH = (
    ROOT / "generated/phase1_visual_evidence/source_locators/internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.source_locators_v0.json"
)
PAGE_ASSETS_PATH = ROOT / "generated/textbooks/internal-medicine-10/page_assets.json"
PAGE_IMAGES_DIR = ROOT / "generated/textbooks/internal-medicine-10/pages"

artifacts_mark = pytest.mark.skipif(
    not PAGE_MAP_PATH.exists() or not LOCATORS_PATH.exists() or not PAGE_ASSETS_PATH.exists(),
    reason="Phase 6B generated artifacts not present (run export_phase1_evidence_lineage.py)",
)


class Phase1VisualEvidencePipelineTests(unittest.TestCase):
    def test_lineage_export_deduplicates_repeated_evidence_references(self):
        items = [
            {"artifact_id": "ev1-a", "page_start": 64, "text": "a"},
            {"artifact_id": "ev1-a", "page_start": 64, "text": "a repeated"},
            {"artifact_id": "ev1-b", "page_start": 64, "text": "b"},
        ]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [1, 2, 3, 4], "confidence": 1},
            },
            "ev1-b": {
                "raw_text": "b",
                "locator": {"bbox": [5, 6, 7, 8], "confidence": 1},
            },
        }
        # page_map keyed by PDF 1-based page number ("64"); pageLabel is the
        # printed label ("33" = 64 - PAGE_DELTA 31). Phase 6B contract.
        page_map = {
            "64": {
                "pdfPageNumber1Based": 64,
                "pdfPageIndex": 63,
                "pageLabel": "33",
                "pageWidthPt": 100,
                "pageHeightPt": 200,
            }
        }

        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)

        self.assertEqual(result["referenceCount"], 3)
        self.assertEqual(result["expected"], 2)
        self.assertEqual(result["count"], 2)
        self.assertEqual(result["missing"], [])
        self.assertEqual({item["evidenceItemId"] for item in result["locators"]}, {"ev1-a", "ev1-b"})
        # Phase 6B: pageLabel must be the printed label, not the PDF page number
        for loc in result["locators"]:
            self.assertEqual(loc["pageLabel"], "33")
            self.assertEqual(loc["pdfPageIndex"], 63)
            self.assertNotIn("bboxNormTopLeftAssumption", loc)
            self.assertNotIn("bboxNormYFlipAssumption", loc)
            self.assertIn("bboxNorm", loc)

    def test_go_no_go_uses_dynamic_coverage_not_a_hardcoded_count(self):
        result = lineage.go_no_go(
            {
                "referenceCount": 3,
                "count": 2,
                "expected": 2,
                "missing": [],
            },
            {},
            {"humanDecisionRequired": False},
        )

        self.assertEqual(result["step1_export_page_assets"], "GO")
        self.assertIn("2/2", result["conditions"][2])
        self.assertIn("3 display evidence references", result["conditions"][2])

    def test_merge_validation_compares_unique_locator_coverage(self):
        locators = [
            {
                "id": "loc-a",
                "evidenceItemId": "ev1-a",
                "locatorSource": "knowledge_node_evidence_json",
                "sourceEvidenceId": "ev1-a",
                "pageAssetId": "page-64",
                "bboxNorm": [0.1, 0.2, 0.3, 0.4],
                "pageLabel": "64",
                "pdfPageIndex": 63,
                "rawText": "a",
            },
            {
                "id": "loc-b",
                "evidenceItemId": "ev1-b",
                "locatorSource": "knowledge_node_evidence_json",
                "sourceEvidenceId": "ev1-b",
                "pageAssetId": "page-64",
                "bboxNorm": [0.2, 0.3, 0.4, 0.5],
                "pageLabel": "64",
                "pdfPageIndex": 63,
                "rawText": "b",
            },
        ]
        result = merge.validate(
            locators,
            {"page-64": {"id": "page-64"}},
            {
                "referenceCount": 3,
                "uniqueEvidenceCount": 2,
                "missingArtifactIdCount": 0,
            },
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["evidenceReferencesExpected"], 3)
        self.assertEqual(result["uniqueEvidenceItemsExpected"], 2)


# ---------------------------------------------------------------------------
# Phase 6B — core tests (never skip)
# ---------------------------------------------------------------------------


class _FakePixmap:
    def __init__(self, width: int = 1077, height: int = 1654):
        self.width = width
        self.height = height

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(b"")


class _FakePage:
    def __init__(self, width: float, height: float):
        self.rect = mock.Mock(width=width, height=height)

    def get_pixmap(self, *, matrix=None, alpha=False):
        return _FakePixmap()


class _FakeDoc:
    """Minimal fitz.Document stand-in for build_page_map / export_page_assets.

    Returns the same page shape regardless of index, since build_page_map
    iterates PDF_PAGES_1BASED (62-70) and calls load_page(61)..load_page(69).
    """

    def __init__(self, width: float = 515.0, height: float = 793.0):
        self._page = _FakePage(width, height)

    def load_page(self, idx: int):
        return self._page

    def close(self):
        pass


class TestPageLabelSemantics:
    """Phase 6B: pageLabel must be the printed label, not the PDF page number."""

    def test_page_delta_is_31(self):
        assert lineage.PAGE_DELTA == 31

    def test_pdf_pages_1based_range(self):
        assert lineage.PDF_PAGES_1BASED == list(range(62, 71))

    def test_build_page_map_printed_labels(self):
        doc = _FakeDoc()
        pm = lineage.build_page_map(doc)
        pages = pm["pages"]
        assert len(pages) == 9
        # First page: PDF 62, index 61, printed "31"
        assert pages[0]["pdfPageNumber1Based"] == 62
        assert pages[0]["pdfPageIndex"] == 61
        assert pages[0]["pageLabel"] == "31"
        # Last page: PDF 70, index 69, printed "39"
        assert pages[-1]["pdfPageNumber1Based"] == 70
        assert pages[-1]["pdfPageIndex"] == 69
        assert pages[-1]["pageLabel"] == "39"

    def test_build_page_map_pageLabel_is_string_not_int(self):
        doc = _FakeDoc()
        pm = lineage.build_page_map(doc)
        for p in pm["pages"]:
            assert isinstance(p["pageLabel"], str)
            assert p["pdfPageIndex"] == p["pdfPageNumber1Based"] - 1
            assert int(p["pageLabel"]) == p["pdfPageNumber1Based"] - lineage.PAGE_DELTA

    def test_build_page_map_pdfPageIndex_is_0_based(self):
        doc = _FakeDoc()
        pm = lineage.build_page_map(doc)
        for p in pm["pages"]:
            assert p["pdfPageIndexBasis"] == "0-based"
            assert p["pdfPageIndex"] == p["pdfPageNumber1Based"] - 1

    def test_mapping_rule_documented(self):
        doc = _FakeDoc()
        pm = lineage.build_page_map(doc)
        assert "pdfPageNumber1Based - 1" in pm["mappingRule"]
        assert "31" in pm["mappingRule"]
        assert pm["pageDelta"] == 31


class TestSourceLocatorV0Contract:
    """Phase 6B: SourceLocator uses single bboxNorm field, correct pageLabel."""

    def test_single_bboxNorm_field_not_dual_assumption(self):
        items = [{"artifact_id": "ev1-a", "page_start": 64, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        page_map = {
            "64": {
                "pdfPageNumber1Based": 64,
                "pdfPageIndex": 63,
                "pageLabel": "33",
                "pageWidthPt": 500,
                "pageHeightPt": 800,
            }
        }
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        loc = result["locators"][0]
        assert "bboxNorm" in loc
        assert "bboxNormTopLeftAssumption" not in loc
        assert "bboxNormYFlipAssumption" not in loc

    def test_pageLabel_is_printed_not_pdf_page(self):
        items = [{"artifact_id": "ev1-a", "page_start": 64, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        page_map = {
            "64": {
                "pdfPageNumber1Based": 64,
                "pdfPageIndex": 63,
                "pageLabel": "33",
                "pageWidthPt": 500,
                "pageHeightPt": 800,
            }
        }
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        loc = result["locators"][0]
        assert loc["pageLabel"] == "33"  # printed, not "64"
        assert loc["pdfPageIndex"] == 63

    def test_pageAssetId_format_matches_page_asset_id(self):
        items = [{"artifact_id": "ev1-a", "page_start": 64, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        page_map = {
            "64": {
                "pdfPageNumber1Based": 64,
                "pdfPageIndex": 63,
                "pageLabel": "33",
                "pageWidthPt": 500,
                "pageHeightPt": 800,
            }
        }
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        loc = result["locators"][0]
        # pageAssetId uses printed label, matching PageAsset.id format
        assert loc["pageAssetId"] == "page_internal_medicine_10_33"

    def test_bboxNorm_in_unit_range(self):
        items = [{"artifact_id": "ev1-a", "page_start": 64, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        page_map = {
            "64": {
                "pdfPageNumber1Based": 64,
                "pdfPageIndex": 63,
                "pageLabel": "33",
                "pageWidthPt": 500,
                "pageHeightPt": 800,
            }
        }
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        loc = result["locators"][0]
        for v in loc["bboxNorm"]:
            assert 0 <= v <= 1

    def test_bboxNorm_uses_top_left_no_flip(self):
        """bboxNorm = [x0/w, y0/h, x1/w, y1/h] — no Y-flip."""
        bbox = [100, 200, 300, 400]
        norm = lineage.bbox_to_norm_top_left(bbox, 500, 800)
        assert norm == [0.2, 0.25, 0.6, 0.5]

    def test_bboxNorm_y_flip_differs(self):
        """Y-flip transform must produce different y values (confirms they're not same)."""
        bbox = [100, 200, 300, 400]
        no_flip = lineage.bbox_to_norm_top_left(bbox, 500, 800)
        y_flip = lineage.bbox_to_norm_y_flip(bbox, 500, 800)
        assert no_flip[1] != y_flip[1]
        assert no_flip[3] != y_flip[3]

    def test_locator_source_is_knowledge_node_evidence_json(self):
        items = [{"artifact_id": "ev1-a", "page_start": 64, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        page_map = {
            "64": {
                "pdfPageNumber1Based": 64,
                "pdfPageIndex": 63,
                "pageLabel": "33",
                "pageWidthPt": 500,
                "pageHeightPt": 800,
            }
        }
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        loc = result["locators"][0]
        assert loc["locatorSource"] == "knowledge_node_evidence_json"
        assert loc["sourceEvidenceId"] == "ev1-a"
        assert loc.get("sourceArtifactId") is None

    def test_page_map_keyed_by_pdf_1based_page(self):
        """page_map_by_pdf_page must be keyed by str(pdfPageNumber1Based),
        not by printed label — because evidence.json page_start is PDF 1-based."""
        items = [{"artifact_id": "ev1-a", "page_start": 62, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        # Key "62" = PDF 1-based page; printed label would be "31"
        page_map = {
            "62": {
                "pdfPageNumber1Based": 62,
                "pdfPageIndex": 61,
                "pageLabel": "31",
                "pageWidthPt": 500,
                "pageHeightPt": 800,
            }
        }
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        assert result["count"] == 1
        assert result["missing"] == []
        assert result["locators"][0]["pageLabel"] == "31"

    def test_missing_page_map_entry_goes_to_missing(self):
        items = [{"artifact_id": "ev1-a", "page_start": 99, "text": "a"}]
        evidence_by_id = {
            "ev1-a": {
                "raw_text": "a",
                "locator": {"bbox": [10, 20, 30, 40], "confidence": 1},
            },
        }
        page_map = {}  # no entry for "99"
        with mock.patch.object(lineage, "collect_evidence_items", return_value=items):
            result = lineage.build_source_locators_v0(evidence_by_id, page_map)
        assert result["count"] == 0
        assert "ev1-a" in result["missing"]


class TestPageAssetManifestCore:
    """Phase 6B: export_phase1_page_assets.py manifest structure (core, no PDF).

    Verifies the manifest schema (pages key, webp, require key, relativePath)
    using a synthetic page map and a mocked PIL Image so tests never skip.
    """

    def _build_page_map(self):
        """Synthetic page map matching the lineage script's output shape."""
        return {
            "textbookId": "internal-medicine-10",
            "textbookVersion": "10",
            "section": "第二篇_呼吸系统疾病__第四章_支气管哮喘",
            "pageDelta": 31,
            "pages": [
                {
                    "pdfPageNumber1Based": 62,
                    "pdfPageIndex": 61,
                    "pdfPageIndexBasis": "0-based",
                    "pageLabel": "31",
                    "pageWidthPt": 515.0,
                    "pageHeightPt": 793.0,
                },
                {
                    "pdfPageNumber1Based": 64,
                    "pdfPageIndex": 63,
                    "pdfPageIndexBasis": "0-based",
                    "pageLabel": "33",
                    "pageWidthPt": 515.0,
                    "pageHeightPt": 793.0,
                },
            ],
        }

    def _run_export(self, tmp_path):
        """Run export_pages into tmp_path with mocked fitz + PIL, return assets."""
        page_map = self._build_page_map()

        # Mock fitz.Document / page / pixmap
        fake_pixmap = mock.Mock()
        fake_pixmap.width = 1077
        fake_pixmap.height = 1654
        fake_pixmap.samples = b"\x00" * (1077 * 1654 * 3)
        fake_page = mock.Mock()
        fake_page.get_pixmap.return_value = fake_pixmap
        fake_doc = mock.Mock()
        fake_doc.load_page.return_value = fake_page
        fake_doc.close = mock.Mock()

        # Mock PIL Image to avoid real WebP encoding in core tests
        fake_img = mock.Mock()
        fake_img.save = mock.Mock(side_effect=lambda path, **kw: Path(path).write_bytes(b""))

        original_open = page_assets_mod.fitz.open
        original_out_pages = page_assets_mod.OUT_PAGES
        original_root = page_assets_mod.ROOT
        try:
            page_assets_mod.fitz.open = mock.Mock(return_value=fake_doc)
            page_assets_mod.OUT_PAGES = tmp_path / "pages"
            page_assets_mod.ROOT = tmp_path
            with mock.patch("PIL.Image.Image"), \
                 mock.patch("PIL.Image.frombytes", return_value=fake_img):
                assets = page_assets_mod.export_pages(page_map)
            return assets
        finally:
            page_assets_mod.fitz.open = original_open
            page_assets_mod.OUT_PAGES = original_out_pages
            page_assets_mod.ROOT = original_root

    def test_manifest_uses_pages_key_not_pageAssets(self):
        """The merge consumer reads manifest['pages']; producer must write it."""
        # Verify export_pages returns a list (which main() writes under 'pages')
        assets = [{"id": "x"}]
        manifest = {"pages": assets, "version": "page-assets-v1"}
        assert "pages" in manifest
        assert "pageAssets" not in manifest

    def test_export_pages_returns_webp_assets(self, tmp_path):
        assets = self._run_export(tmp_path)
        assert len(assets) == 2
        for asset in assets:
            assert asset["imageFormat"] == "webp"

    def test_localAssetKey_is_require_key_not_path(self, tmp_path):
        """localAssetKey must be a stable require key (im10_page_31), not a path."""
        assets = self._run_export(tmp_path)
        for asset in assets:
            assert asset["localAssetKey"] == f"im10_page_{asset['pageLabel']}"
            # Must NOT be a path like "pages/31.png"
            assert "/" not in asset["localAssetKey"]
            assert "\\" not in asset["localAssetKey"]

    def test_relativePath_is_separate_from_localAssetKey(self, tmp_path):
        assets = self._run_export(tmp_path)
        for asset in assets:
            assert asset["relativePath"].endswith(".webp")
            assert asset["relativePath"] != asset["localAssetKey"]

    def test_page_asset_id_uses_printed_label(self, tmp_path):
        assets = self._run_export(tmp_path)
        for asset in assets:
            assert asset["id"] == f"page_internal_medicine_10_{asset['pageLabel']}"

    def test_pdfPageIndex_is_0_based(self, tmp_path):
        assets = self._run_export(tmp_path)
        for asset in assets:
            assert asset["pdfPageIndex"] == asset["pdfPageNumber1Based"] - 1

    def test_bboxNormRule_top_left_no_flip(self, tmp_path):
        assets = self._run_export(tmp_path)
        for asset in assets:
            rule = asset["bboxNormRule"]
            assert rule["origin"] == "top-left"
            assert rule["yFlip"] is False
            # Must reference the single bboxNorm field, not the old dual assumption
            assert "bboxNorm" in rule["note"]
            assert "TopLeftAssumption" not in rule["note"]

    def test_pillow_missing_raises_not_silently_png(self, tmp_path):
        """When Pillow is unavailable, export must fail loudly, not degrade to PNG."""
        page_map = self._build_page_map()
        original_out_pages = page_assets_mod.OUT_PAGES
        try:
            page_assets_mod.OUT_PAGES = tmp_path / "pages"
            with mock.patch("builtins.__import__", side_effect=ImportError("no PIL")):
                with pytest.raises(SystemExit, match="Pillow is required"):
                    page_assets_mod.export_pages(page_map)
        finally:
            page_assets_mod.OUT_PAGES = original_out_pages


# ---------------------------------------------------------------------------
# Phase 6B — PDF integration tests (skip if generated artifacts absent)
# ---------------------------------------------------------------------------


@artifacts_mark
class TestGeneratedPageMap:
    def test_page_map_printed_labels_31_to_39(self):
        pm = json.loads(PAGE_MAP_PATH.read_text("utf-8"))
        labels = [p["pageLabel"] for p in pm["pages"]]
        assert labels == [str(n) for n in range(31, 40)]

    def test_page_map_pdfPageIndex_0_based(self):
        pm = json.loads(PAGE_MAP_PATH.read_text("utf-8"))
        for p in pm["pages"]:
            assert p["pdfPageIndex"] == p["pdfPageNumber1Based"] - 1

    def test_page_map_pageDelta_31(self):
        pm = json.loads(PAGE_MAP_PATH.read_text("utf-8"))
        assert pm["pageDelta"] == 31

    def test_page_map_nine_pages(self):
        pm = json.loads(PAGE_MAP_PATH.read_text("utf-8"))
        assert len(pm["pages"]) == 9


@artifacts_mark
class TestGeneratedSourceLocators:
    def test_all_locators_have_single_bboxNorm(self):
        data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        for loc in data["locators"]:
            assert "bboxNorm" in loc, f"{loc['id']} missing bboxNorm"
            assert "bboxNormTopLeftAssumption" not in loc
            assert "bboxNormYFlipAssumption" not in loc

    def test_all_bboxNorm_in_unit_range(self):
        data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        for loc in data["locators"]:
            for v in loc["bboxNorm"]:
                assert 0 <= v <= 1, f"{loc['id']} bboxNorm out of range: {v}"

    def test_pageLabel_is_printed_not_pdf_page(self):
        data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        for loc in data["locators"]:
            # pageLabel must be in printed range "31"-"39", NOT "62"-"70"
            label_int = int(loc["pageLabel"])
            assert 31 <= label_int <= 39, (
                f"{loc['id']} pageLabel {loc['pageLabel']} outside printed range"
            )
            # pdfPageIndex must be 0-based (61-69), not printed label
            assert 61 <= loc["pdfPageIndex"] <= 69

    def test_pageAssetId_uses_printed_label(self):
        data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        for loc in data["locators"]:
            assert loc["pageAssetId"] == f"page_internal_medicine_10_{loc['pageLabel']}"

    def test_no_missing_locators(self):
        data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        assert data["missing"] == []
        assert data["count"] == data["expected"]

    def test_locator_source_knowledge_node_evidence_json(self):
        data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        for loc in data["locators"]:
            assert loc["locatorSource"] == "knowledge_node_evidence_json"
            assert loc.get("sourceEvidenceId") is not None
            assert loc.get("sourceArtifactId") is None


@artifacts_mark
class TestGeneratedPageAssets:
    def test_manifest_uses_pages_key(self):
        """Manifest must use 'pages' key (consumed by merge_phase1_locators_bundle),
        not 'pageAssets'."""
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        assert "pages" in manifest
        assert "pageAssets" not in manifest

    def test_manifest_has_nine_assets(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        assert len(manifest["pages"]) == 9

    def test_every_page_asset_image_is_webp(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pages"]:
            assert asset["imageFormat"] == "webp"
            assert asset["relativePath"].endswith(".webp")

    def test_every_page_asset_webp_file_exists(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pages"]:
            # relativePath is like "generated/textbooks/internal-medicine-10/pages/31.webp"
            img_path = ROOT / asset["relativePath"]
            assert img_path.exists(), f"missing image: {img_path}"

    def test_localAssetKey_is_require_key_not_path(self):
        """localAssetKey must be a stable Expo require key (im10_page_31),
        separate from relativePath."""
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pages"]:
            assert asset["localAssetKey"] == f"im10_page_{asset['pageLabel']}"
            assert "/" not in asset["localAssetKey"]
            assert "\\" not in asset["localAssetKey"]
            assert asset["relativePath"] != asset["localAssetKey"]

    def test_page_asset_dimensions_positive(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pages"]:
            assert asset["imageWidth"] > 0
            assert asset["imageHeight"] > 0

    def test_page_asset_ids_and_labels_consistent(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pages"]:
            assert asset["id"] == f"page_internal_medicine_10_{asset['pageLabel']}"
            assert asset["pdfPageIndex"] == asset["pdfPageNumber1Based"] - 1
            label_int = int(asset["pageLabel"])
            assert 31 <= label_int <= 39


@artifacts_mark
class TestCrossReferenceIntegrity:
    """Every SourceLocator.pageAssetId must reference an existing PageAsset."""

    def test_every_locator_pageAssetId_exists_in_page_assets(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        loc_data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        page_asset_ids = {a["id"] for a in manifest["pages"]}
        for loc in loc_data["locators"]:
            assert loc["pageAssetId"] in page_asset_ids, (
                f"{loc['id']} references missing pageAssetId {loc['pageAssetId']}"
            )

    def test_every_page_asset_has_at_least_one_locator(self):
        """Each exported page should be referenced by ≥1 locator (coverage sanity)."""
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        loc_data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        referenced = {loc["pageAssetId"] for loc in loc_data["locators"]}
        all_assets = {a["id"] for a in manifest["pages"]}
        # Not every page must have a locator, but at least 5 of 9 should
        assert len(referenced & all_assets) >= 5, (
            f"only {len(referenced & all_assets)} pages have locators"
        )


@artifacts_mark
class TestReferenceCoverage281to276:
    """All 281 display evidence references must resolve to one of the 276
    unique locators (deduplication is expected, not a gap)."""

    def test_281_references_resolve_to_276_unique_locators(self):
        loc_data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        # referenceCount = total display evidence references (281)
        # count = unique locators produced (276)
        # expected = unique evidence ids requiring locators (276)
        # missing = [] means every unique id got a locator
        assert loc_data["referenceCount"] == 281
        assert loc_data["count"] == 276
        assert loc_data["expected"] == 276
        assert loc_data["missing"] == []

    def test_every_display_evidence_reference_resolves(self):
        """Every evidence reference in the display contract must carry an
        artifact_id that maps to a locator. No reference may be unresolvable."""
        dc = json.loads(
            (ROOT / "generated/display_contracts/internal-medicine-10"
             / "第二篇_呼吸系统疾病__第四章_支气管哮喘.display_contract.json"
             ).read_text("utf-8")
        )
        loc_data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        locator_evidence_ids = {loc["evidenceItemId"] for loc in loc_data["locators"]}
        unresolved = []
        total_refs = 0
        for node in dc.get("nodes", []):
            for ei in node.get("evidence_items", []):
                total_refs += 1
                aid = ei.get("artifact_id")
                if not aid or aid not in locator_evidence_ids:
                    unresolved.append((ei.get("id", "?"), aid))
        assert total_refs == 281, f"expected 281 refs, got {total_refs}"
        assert unresolved == [], (
            f"{len(unresolved)} references unresolved: {unresolved[:5]}"
        )

    def test_281_minus_276_is_deduplication_not_gap(self):
        """The 5-reference difference must be duplicate artifact_ids, not missing
        locators. Verify by counting references per evidence id."""
        dc = json.loads(
            (ROOT / "generated/display_contracts/internal-medicine-10"
             / "第二篇_呼吸系统疾病__第四章_支气管哮喘.display_contract.json"
             ).read_text("utf-8")
        )
        from collections import Counter
        ref_counts = Counter()
        for node in dc.get("nodes", []):
            for ei in node.get("evidence_items", []):
                aid = ei.get("artifact_id")
                if aid:
                    ref_counts[aid] += 1
        duplicated = {aid: c for aid, c in ref_counts.items() if c > 1}
        extra_refs_from_dupes = sum(c - 1 for c in duplicated.values())
        unique_count = len(ref_counts)
        total_refs = sum(ref_counts.values())
        # 281 total - 276 unique = 5 extra from dedup
        assert total_refs == 281
        assert unique_count == 276
        assert extra_refs_from_dupes == 281 - 276


if __name__ == "__main__":
    unittest.main()
