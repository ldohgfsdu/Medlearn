"""Tests for scripts/audit_phase1_visual_evidence_origin.py.

Verifies the audit script correctly validates the Phase 1 visual evidence
contract: display_contract -> sourceLocatorIds -> SourceLocator -> PageAsset.

Does NOT depend on real generated artifacts; uses synthetic data to exercise
each validation rule independently.

All tests pass ``write_report=False`` to ``main()`` so the real report file
under ``generated/reports/`` is never touched.
"""
import importlib.util
import json
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "audit_phase1_visual_evidence_origin.py"


def _load_audit():
    spec = importlib.util.spec_from_file_location(
        "audit_phase1_visual_evidence_origin_test", SCRIPT_PATH,
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_dc(*, evidence_items: list[dict]) -> dict:
    return {
        "version": "ev1-display-contract-0.1.0",
        "textbook_id": "internal-medicine-10",
        "section_title": "第四章 支气管哮喘",
        "nodes": [{"id": "view-kn-test", "render_type": "normal", "evidence_items": evidence_items}],
    }


def _make_loc_doc(*, locators: list[dict]) -> dict:
    return {
        "version": "source-locator-v0",
        "section": "第二篇_呼吸系统疾病__第四章_支气管哮喘",
        "locatorSource": "knowledge_node_evidence_json",
        "count": len(locators),
        "locators": locators,
    }


_SENTINEL = object()
_DEFAULT_BBOX = [0.1, 0.2, 0.3, 0.4]


def _make_loc(
    lid="loc_ev1_test",
    paid="page_internal_medicine_10_31",
    bbox_norm=_SENTINEL,
    page_label="31",
    pdf_page_index=61,
    locator_source="knowledge_node_evidence_json",
):
    result = {
        "id": lid,
        "evidenceItemId": f"ev1-{lid}",
        "locatorSource": locator_source,
        "pageAssetId": paid,
        "pageLabel": page_label,
        "pdfPageIndex": pdf_page_index,
        "bboxNorm": bbox_norm if bbox_norm is not _SENTINEL else _DEFAULT_BBOX,
        "rawText": "test evidence text",
    }
    if locator_source == "knowledge_node_evidence_json":
        result["sourceEvidenceId"] = f"ev1-{lid}"
    elif locator_source == "pipeline_v3_source_artifacts":
        result["sourceArtifactId"] = f"artifact-{lid}"
    return result


def _make_pa_doc(*, pages: list[dict]) -> dict:
    return {"version": "page-assets-v1", "textbookId": "internal-medicine-10", "pages": pages}


def _make_pa(paid="page_internal_medicine_10_31", page_label="31", pdf_page_index=61, rel_path=""):
    return {
        "id": paid,
        "pageLabel": page_label,
        "pdfPageIndex": pdf_page_index,
        "imageWidth": 1199,
        "imageHeight": 1654,
        "imageFormat": "webp",
        "relativePath": rel_path or f"generated/textbooks/internal-medicine-10/pages/{page_label}.webp",
    }


class AuditPhase1VisualEvidenceOriginTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.audit = _load_audit()

    def _run_main(self, dc, loc_doc, pa_doc, *, page_files_exist=True, write_report=False):
        reads = [json.dumps(dc), json.dumps(loc_doc), json.dumps(pa_doc)]
        read_idx = [0]

        def read_text_replacement(self_path, /, **kwargs):
            idx = read_idx[0]
            read_idx[0] += 1
            return reads[idx]

        def exists_replacement(self_path, /):
            str_path = str(self_path)
            if not page_files_exist and "pages" in str_path and str_path.endswith(".webp"):
                return False
            return True

        with (
            mock.patch.object(Path, "read_text", read_text_replacement),
            mock.patch.object(Path, "exists", exists_replacement),
            mock.patch.object(Path, "write_text"),
            mock.patch.object(Path, "mkdir"),
        ):
            try:
                self.audit.main(write_report=write_report)
                return True
            except SystemExit:
                return False

    # ================================================================ #
    #  happy path
    # ================================================================ #

    def test_passes_full_valid_contract(self):
        self.assertTrue(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
                {"artifact_id": "ev1-b", "text": "b", "sourceLocatorIds": ["loc_b"]},
            ]),
            _make_loc_doc(locators=[
                _make_loc("loc_a", locator_source="knowledge_node_evidence_json"),
                _make_loc("loc_b", paid="page_internal_medicine_10_32"),
            ]),
            _make_pa_doc(pages=[
                _make_pa("page_internal_medicine_10_31"),
                _make_pa("page_internal_medicine_10_32", "32"),
            ]),
        ))

    # ================================================================ #
    #  originArtifactIds -- informational, NOT a blocker (req 1)
    # ================================================================ #

    def test_missing_origin_artifact_ids_not_a_blocker(self):
        self.assertTrue(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_empty_origin_artifact_ids_not_a_blocker(self):
        self.assertTrue(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"], "originArtifactIds": []},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_present_origin_artifact_ids_fine(self):
        self.assertTrue(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"], "originArtifactIds": ["artifact-001"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    # ================================================================ #
    #  evidence item -> sourceLocatorIds -> SourceLocator
    # ================================================================ #

    def test_fails_when_evidence_missing_source_locator_ids(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[{"artifact_id": "ev1-a", "text": "a"}]),
            _make_loc_doc(locators=[]),
            _make_pa_doc(pages=[]),
        ))

    def test_fails_when_source_locator_id_unresolvable(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_nonexistent"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    # ================================================================ #
    #  SourceLocator -> pageAssetId -> PageAsset
    # ================================================================ #

    def test_fails_when_page_asset_id_unresolvable(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a", paid="page_missing")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    # ================================================================ #
    #  bboxNorm
    # ================================================================ #

    def test_fails_when_bbox_norm_out_of_range(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a", bbox_norm=[-0.1, 0.5, 1.2, 0.8])]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_bbox_norm_is_not_list(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a", bbox_norm=None)]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    # ================================================================ #
    #  locatorSource -- legal value + exactly-one source ID
    # ================================================================ #

    def test_fails_when_locator_source_illegal(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a", locator_source="unknown_parser")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_locator_source_empty(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a", locator_source="")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_locator_source_kn_json_missing_source_evidence_id(self):
        loc = _make_loc("loc_a", locator_source="knowledge_node_evidence_json")
        loc.pop("sourceEvidenceId", None)
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[loc]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_locator_source_pipeline_missing_source_artifact_id(self):
        loc = _make_loc("loc_a", locator_source="pipeline_v3_source_artifacts")
        loc.pop("sourceArtifactId", None)
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[loc]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_both_source_ids_present(self):
        loc = _make_loc("loc_a", locator_source="knowledge_node_evidence_json")
        loc["sourceArtifactId"] = "artifact-001"
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[loc]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_neither_source_id_present(self):
        loc = _make_loc("loc_a", locator_source="knowledge_node_evidence_json")
        loc.pop("sourceEvidenceId", None)
        loc.pop("sourceArtifactId", None)
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[loc]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_passes_pipeline_source_with_source_artifact_id(self):
        loc = _make_loc("loc_a", locator_source="pipeline_v3_source_artifacts")
        self.assertTrue(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[loc]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    # ================================================================ #
    #  SourceLocator scalar fields
    # ================================================================ #

    def test_fails_when_locator_missing_page_label(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a", page_label="")]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    def test_fails_when_locator_missing_pdf_page_index(self):
        loc = _make_loc("loc_a")
        loc["pdfPageIndex"] = None
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[loc]),
            _make_pa_doc(pages=[_make_pa()]),
        ))

    # ================================================================ #
    #  PageAsset fields -- now errors, not warnings
    # ================================================================ #

    def test_fails_when_page_asset_missing_page_label(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[
                {"id": "page_x", "pageLabel": "", "pdfPageIndex": 61, "imageWidth": 100, "imageHeight": 100, "imageFormat": "webp", "relativePath": "gen/pages/x.webp"},
            ]),
        ))

    def test_fails_when_page_asset_missing_pdf_page_index(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[
                {"id": "page_x", "pageLabel": "31", "pdfPageIndex": None, "imageWidth": 100, "imageHeight": 100, "imageFormat": "webp", "relativePath": "gen/pages/x.webp"},
            ]),
        ))

    # ================================================================ #
    #  page image file on disk
    # ================================================================ #

    def test_fails_when_page_image_file_missing_on_disk(self):
        self.assertFalse(self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[_make_pa()]),
            page_files_exist=False,
        ))

    # ================================================================ #
    #  real report integrity
    # ================================================================ #

    def test_does_not_modify_real_report(self):
        """Verify that running main() does not alter the real report on disk."""
        real_path = PROJECT_ROOT / "generated/reports/phase1_visual_evidence_origin_audit_asthma.json"
        before = real_path.read_bytes() if real_path.exists() else None

        self._run_main(
            _make_dc(evidence_items=[
                {"artifact_id": "ev1-a", "text": "a", "sourceLocatorIds": ["loc_a"]},
            ]),
            _make_loc_doc(locators=[_make_loc("loc_a")]),
            _make_pa_doc(pages=[_make_pa()]),
            write_report=True,
        )

        after = real_path.read_bytes() if real_path.exists() else None
        self.assertEqual(before, after)

    # ================================================================ #
    #  unit tests for helpers
    # ================================================================ #

    def test_collect_evidence_items(self):
        dc = _make_dc(evidence_items=[
            {"artifact_id": "ev1-a", "text": "a"},
            {"artifact_id": "ev1-b", "text": "b"},
        ])
        items = self.audit.collect_evidence_items(dc)
        self.assertEqual(len(items), 2)

    def test_collect_evidence_items_skips_nodes_without_evidence(self):
        dc = {"nodes": [{"id": "x", "render_type": "normal"}, {"id": "y", "evidence_items": [{"a": 1}]}]}
        items = self.audit.collect_evidence_items(dc)
        self.assertEqual(len(items), 1)

    # ================================================================ #
    #  no fuzzy text matching (req 2)
    # ================================================================ #

    def test_no_fuzzy_text_matching_in_source(self):
        source = SCRIPT_PATH.read_text("utf-8")
        self.assertNotIn("支气管舒张", source)
        self.assertNotIn("search_for", source)


if __name__ == "__main__":
    unittest.main()
