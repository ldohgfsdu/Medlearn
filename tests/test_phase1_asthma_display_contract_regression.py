"""Phase 1 asthma display-contract regression tests (real data).

Unlike ``tests/test_evidence_display_contract.py`` which uses synthetic
fixtures to exercise the contract builder, this module loads the actual
Phase 1 asthma pilot artifacts and asserts the visual-evidence data contract
holds end-to-end:

    evidence item (display contract)
      -> sourceLocatorIds
      -> SourceLocator (source_locators_v0.json)
      -> pageAssetId
      -> PageAsset (page_assets.json)

It enforces the automated acceptance criteria from the
``medlearn-phase1-visual-evidence`` skill for the asthma golden section.
"""

import json
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DISPLAY_CONTRACT_PATH = (
    PROJECT_ROOT
    / "generated"
    / "display_contracts"
    / "internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.display_contract.json"
)
SOURCE_LOCATORS_PATH = (
    PROJECT_ROOT
    / "generated"
    / "phase1_visual_evidence"
    / "source_locators"
    / "internal-medicine-10"
    / "第二篇_呼吸系统疾病__第四章_支气管哮喘.source_locators_v0.json"
)
PAGE_ASSETS_PATH = (
    PROJECT_ROOT / "generated" / "textbooks" / "internal-medicine-10" / "page_assets.json"
)

# BDT (支气管舒张试验) anchor — fixed expected coordinates for the asthma pilot.
BDT_EVIDENCE_ITEM_ID = "ev1-57068078e29b9153d70d"
BDT_EXPECTED_BBOX_PDF = [
    79.36870574951172,
    200.33705139160156,
    495.33868408203125,
    212.13705444335938,
]


def _collect_evidence_items(node, accumulator):
    """Recursively collect every dict held in an ``evidence_items`` list.

    Evidence items live in ``evidence_items`` arrays on each contract node.
    Display items under ``display.items`` (with ``evidence_artifact_ids``)
    are intentionally not collected — they are not evidence items.
    """
    if isinstance(node, dict):
        items = node.get("evidence_items")
        if isinstance(items, list):
            accumulator.extend(items)
        for value in node.values():
            _collect_evidence_items(value, accumulator)
    elif isinstance(node, list):
        for item in node:
            _collect_evidence_items(item, accumulator)


class Phase1AsthmaDisplayContractRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with DISPLAY_CONTRACT_PATH.open(encoding="utf-8") as handle:
            cls.display_contract = json.load(handle)
        with SOURCE_LOCATORS_PATH.open(encoding="utf-8") as handle:
            cls.source_locators_doc = json.load(handle)
        with PAGE_ASSETS_PATH.open(encoding="utf-8") as handle:
            cls.page_assets_doc = json.load(handle)

        cls.evidence_items = []
        _collect_evidence_items(cls.display_contract, cls.evidence_items)

        cls.locators = {
            locator["id"]: locator
            for locator in cls.source_locators_doc.get("locators", [])
        }
        cls.page_assets = {
            page["id"]: page for page in cls.page_assets_doc.get("pages", [])
        }

    def test_contract_targets_asthma_section(self):
        # Guard: confirm the loaded contract is the asthma pilot so a path
        # rename cannot silently turn this regression test into a no-op.
        self.assertEqual(self.display_contract["textbook_id"], "internal-medicine-10")
        self.assertEqual(self.display_contract["section_title"], "第四章 支气管哮喘")
        self.assertEqual(self.display_contract["part_title"], "第二篇 呼吸系统疾病")

    def test_evidence_items_were_collected(self):
        # Guard: a broken collector would leave this empty and make every
        # downstream assertion pass vacuously.
        self.assertGreaterEqual(
            len(self.evidence_items),
            100,
            "expected the asthma contract to expose many evidence items",
        )

    def test_every_evidence_item_has_non_empty_source_locator_ids(self):
        missing = []
        empty = []
        not_list = []
        for item in self.evidence_items:
            ids = item.get("sourceLocatorIds")
            if not isinstance(ids, list):
                not_list.append(item.get("artifact_id"))
            elif len(ids) == 0:
                empty.append(item.get("artifact_id"))
            else:
                continue
            missing.append(item.get("artifact_id"))
        self.assertEqual(not_list, [], "evidence items where sourceLocatorIds is not a list")
        self.assertEqual(empty, [], "evidence items with empty sourceLocatorIds")
        self.assertEqual(missing, [], "evidence items without non-empty sourceLocatorIds")

    def test_every_source_locator_id_resolves_in_locators_file(self):
        missing = []
        for item in self.evidence_items:
            for locator_id in item.get("sourceLocatorIds", []):
                if locator_id not in self.locators:
                    missing.append((item.get("artifact_id"), locator_id))
        self.assertEqual(
            missing,
            [],
            "sourceLocatorIds referenced by evidence items but absent from locators file",
        )

    def test_every_locator_references_an_existing_page_asset(self):
        missing = []
        for locator in self.locators.values():
            page_asset_id = locator.get("pageAssetId")
            if not page_asset_id or page_asset_id not in self.page_assets:
                missing.append((locator.get("id"), page_asset_id))
        self.assertEqual(
            missing,
            [],
            "SourceLocators whose pageAssetId does not resolve to a PageAsset",
        )

    def test_bbox_norm_values_are_within_unit_range(self):
        out_of_range = []
        for locator in self.locators.values():
            bbox_norm = locator.get("bboxNorm")
            if not isinstance(bbox_norm, list):
                continue
            if any(not (0.0 <= value <= 1.0) for value in bbox_norm):
                out_of_range.append((locator.get("id"), bbox_norm))
        self.assertEqual(
            out_of_range,
            [],
            "bboxNorm values outside [0, 1]",
        )

    def test_page_assets_carry_page_label_and_pdf_page_index(self):
        missing = []
        for page in self.page_assets.values():
            if "pageLabel" not in page or "pdfPageIndex" not in page:
                missing.append(page.get("id"))
        self.assertEqual(
            missing,
            [],
            "PageAssets missing pageLabel or pdfPageIndex",
        )

    def test_locators_carry_page_label_and_pdf_page_index(self):
        missing = []
        for locator in self.locators.values():
            if "pageLabel" not in locator or "pdfPageIndex" not in locator:
                missing.append(locator.get("id"))
        self.assertEqual(
            missing,
            [],
            "SourceLocators missing pageLabel or pdfPageIndex",
        )

    def test_bdt_locator_exists_with_expected_bbox_pdf(self):
        bdt_locators = [
            locator
            for locator in self.locators.values()
            if locator.get("evidenceItemId") == BDT_EVIDENCE_ITEM_ID
        ]
        self.assertEqual(
            len(bdt_locators),
            1,
            "expected exactly one SourceLocator for the BDT evidence item",
        )
        locator = bdt_locators[0]
        self.assertEqual(
            locator.get("bboxPdf"),
            BDT_EXPECTED_BBOX_PDF,
            "BDT locator bboxPdf drifted from the anchored asthma pilot value",
        )


if __name__ == "__main__":
    unittest.main()
