import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_ev1_display_contracts_ts import CHUNK_SIZE, build_fixture, write_ts_fixture  # noqa: E402


class ExportDisplayContractsTests(unittest.TestCase):
    def test_preserves_group_metadata_and_display_items(self):
        payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part 2 Respiratory diseases",
            "section_title": "Chapter 6 Pulmonary infections",
            "node_count": 1,
            "summary": {"organized": 1, "grouped": 1},
            "nodes": [
                {
                    "id": "view-grouped-classification",
                    "render_type": "grouped",
                    "publication_state": "organized",
                    "quality_badges": ["group:classification"],
                    "display": {
                        "title": "Pneumonia classification",
                        "body": "",
                        "page_label": "p.77",
                        "source_heading": "Pulmonary infections",
                        "items": [
                            {
                                "title": "Bacterial pneumonia",
                                "body": "A grouped child item.",
                                "page_label": "p.78",
                                "publication_state": "organized",
                            }
                        ],
                    },
                    "source_node_ids": ["kn-child"],
                    "evidence_items": [
                        {
                            "artifact_id": "ev-child",
                            "text": "Source evidence.",
                            "page_start": 77,
                            "page_end": 78,
                            "source_order": 1,
                        }
                    ],
                    "group": {
                        "strategy": "related_classification_items",
                        "topic": "classification",
                        "child_view_ids": ["view-child"],
                        "child_node_ids": ["kn-child"],
                        "child_artifact_ids": ["ev-child"],
                    },
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "sample.display_contract.json").write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            sections = build_fixture(root)

        node = sections[0]["nodes"][0]
        self.assertEqual(node["group"]["topic"], "classification")
        self.assertEqual(node["display"]["items"][0]["title"], "Bacterial pneumonia")

    def test_writes_payload_as_separate_bounded_modules(self):
        sections = [
            {
                "id": "section",
                "nodes": [{"id": "node", "display": {"body": "x" * (CHUNK_SIZE + 10)}}],
            }
        ]

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "fixture.ts"
            write_ts_fixture(sections, output)

            entry = output.read_text(encoding="utf-8")
            chunks = sorted((Path(tmp) / "fixtureChunks").glob("chunk*.ts"))
            chunk_sizes = [path.stat().st_size for path in chunks]

        self.assertEqual(len(chunks), 2)
        self.assertIn("import chunk000 from './fixtureChunks/chunk000'", entry)
        self.assertIn("import chunk001 from './fixtureChunks/chunk001'", entry)
        self.assertLess(len(entry), 2_000)
        self.assertTrue(all(size < CHUNK_SIZE * 4 for size in chunk_sizes))


if __name__ == "__main__":
    unittest.main()
