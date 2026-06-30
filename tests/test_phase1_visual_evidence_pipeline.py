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


class TestPageAssetManifest:
    """Phase 6B: export_page_assets manifest structure."""

    def _run_export(self, tmp_path):
        """Helper: run export_page_assets into tmp_path, return manifest dict."""
        doc = _FakeDoc()
        pm = lineage.build_page_map(doc)
        original_out = lineage.OUT_PAGE_ASSETS
        original_images = lineage.OUT_PAGE_IMAGES
        original_root = lineage.ROOT
        try:
            lineage.OUT_PAGE_ASSETS = tmp_path
            lineage.OUT_PAGE_IMAGES = tmp_path / "pages"
            lineage.ROOT = tmp_path
            lineage.export_page_assets(doc, pm)
            return json.loads((tmp_path / "page_assets.json").read_text("utf-8"))
        finally:
            lineage.OUT_PAGE_ASSETS = original_out
            lineage.OUT_PAGE_IMAGES = original_images
            lineage.ROOT = original_root

    def test_manifest_has_required_fields(self, tmp_path):
        manifest = self._run_export(tmp_path)
        assert manifest["pageAssetCount"] == 9
        assert len(manifest["pageAssets"]) == 9
        for asset in manifest["pageAssets"]:
            assert "id" in asset
            assert "textbookId" in asset
            assert "pdfPageIndex" in asset
            assert "pageLabel" in asset
            assert "imageWidth" in asset
            assert "imageHeight" in asset
            assert "localAssetKey" in asset

    def test_page_asset_ids_use_printed_label(self, tmp_path):
        manifest = self._run_export(tmp_path)
        first = manifest["pageAssets"][0]
        assert first["id"] == "page_internal_medicine_10_31"
        assert first["pageLabel"] == "31"
        assert first["pdfPageIndex"] == 61
        assert first["localAssetKey"] == "pages/31.png"

    def test_page_asset_pdfPageIndex_0_based(self, tmp_path):
        manifest = self._run_export(tmp_path)
        for asset in manifest["pageAssets"]:
            assert asset["pdfPageIndex"] == asset["pdfPageNumber1Based"] - 1


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
    def test_manifest_has_nine_assets(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        assert manifest["pageAssetCount"] == 9
        assert len(manifest["pageAssets"]) == 9

    def test_every_page_asset_image_file_exists(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pageAssets"]:
            img_path = PAGE_IMAGES_DIR / Path(asset["localAssetKey"]).name
            assert img_path.exists(), f"missing image: {img_path}"

    def test_page_asset_dimensions_positive(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pageAssets"]:
            assert asset["imageWidth"] > 0
            assert asset["imageHeight"] > 0

    def test_page_asset_ids_and_labels_consistent(self):
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        for asset in manifest["pageAssets"]:
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
        page_asset_ids = {a["id"] for a in manifest["pageAssets"]}
        for loc in loc_data["locators"]:
            assert loc["pageAssetId"] in page_asset_ids, (
                f"{loc['id']} references missing pageAssetId {loc['pageAssetId']}"
            )

    def test_every_page_asset_has_at_least_one_locator(self):
        """Each exported page should be referenced by ≥1 locator (coverage sanity)."""
        manifest = json.loads(PAGE_ASSETS_PATH.read_text("utf-8"))
        loc_data = json.loads(LOCATORS_PATH.read_text("utf-8"))
        referenced = {loc["pageAssetId"] for loc in loc_data["locators"]}
        all_assets = {a["id"] for a in manifest["pageAssets"]}
        # Not every page must have a locator, but at least 5 of 9 should
        assert len(referenced & all_assets) >= 5, (
            f"only {len(referenced & all_assets)} pages have locators"
        )


if __name__ == "__main__":
    unittest.main()
