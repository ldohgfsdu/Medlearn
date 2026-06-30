import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from textbook_pipeline.adaptive_pdf_parser import (  # noqa: E402
    bbox_overlap_ratio,
    find_evidence_locators,
    page_window_toc,
    structure_aware_split,
)
from textbook_pipeline.ingestion_contract import (  # noqa: E402
    PRODUCTION_PDF_PARSER,
    resolve_pdf_parser_mode,
)


class AdaptivePdfParserTests(unittest.TestCase):
    def test_default_parser_is_adaptive(self) -> None:
        self.assertEqual(PRODUCTION_PDF_PARSER, "auto")
        self.assertEqual(resolve_pdf_parser_mode(), "auto")

    def test_table_split_repeats_header_and_keeps_rows_whole(self) -> None:
        table = "\n".join(
            [
                "| Name | Value |",
                "| --- | --- |",
                "| Alpha | " + ("a" * 40) + " |",
                "| Beta | " + ("b" * 40) + " |",
                "| Gamma | " + ("c" * 40) + " |",
            ]
        )
        pieces = structure_aware_split(table, 105)
        self.assertGreater(len(pieces), 1)
        for piece in pieces:
            self.assertTrue(piece.startswith("| Name | Value |\n| --- | --- |"))
        self.assertEqual(sum("| Alpha |" in piece for piece in pieces), 1)
        self.assertEqual(sum("| Beta |" in piece for piece in pieces), 1)

    def test_prose_split_uses_sentence_boundaries(self) -> None:
        text = "First sentence. Second sentence is longer. Third sentence."
        pieces = structure_aware_split(text, 35)
        self.assertEqual(pieces, ["First sentence.", "Second sentence is longer.", "Third sentence."])

    def test_page_markers_stay_with_following_content(self) -> None:
        pieces = structure_aware_split(
            "<!-- PDF page 12 -->\nParagraph one.\n\n<!-- PDF page 13 -->\nParagraph two.",
            30,
        )
        self.assertTrue(pieces[0].startswith("<!-- PDF page 12 -->"))
        self.assertTrue(pieces[1].startswith("<!-- PDF page 13 -->"))

    def test_page_window_toc_covers_document(self) -> None:
        toc = page_window_toc(10, window=4)
        self.assertEqual([entry[2] for entry in toc], [1, 5, 9])
        self.assertEqual(toc[-1][1], "Pages 9-10")

    def test_evidence_matches_locator_with_page_filter(self) -> None:
        locators = [
            {
                "artifact_id": "a1",
                "page": 4,
                "kind": "text_block",
                "bbox": [1, 2, 3, 4],
                "text": "Chronic obstructive pulmonary disease causes airflow limitation.",
                "parser": "pymupdf",
                "confidence": 1.0,
            },
            {
                "artifact_id": "a2",
                "page": 8,
                "kind": "text_block",
                "bbox": [5, 6, 7, 8],
                "text": "Unrelated text.",
                "parser": "pymupdf",
                "confidence": 1.0,
            },
        ]
        matches = find_evidence_locators(
            locators,
            "airflow limitation",
            page_start=4,
            page_end=4,
        )
        self.assertEqual([item["artifact_id"] for item in matches], ["a1"])

    def test_bbox_overlap_is_relative_to_text_block(self) -> None:
        self.assertEqual(bbox_overlap_ratio((0, 0, 10, 10), (0, 0, 5, 10)), 0.5)


if __name__ == "__main__":
    unittest.main()
