import unittest

from scripts.textbook_pipeline.evidence_artifact import make_artifact
from scripts.textbook_pipeline.text_layers import build_text_layers


class TextLayerContractTests(unittest.TestCase):
    def test_raw_canonical_and_display_layers_are_distinct(self):
        raw = "气道 炎症\n反复发作 ， 常在夜间\n\nbronchial asthma 10 mg"
        layers = build_text_layers(raw)
        self.assertEqual(layers.raw_text, raw)
        self.assertEqual(
            layers.canonical_text,
            "气道炎症反复发作 ， 常在夜间\n\nbronchial asthma 10 mg",
        )
        self.assertEqual(
            layers.display_text,
            "气道炎症反复发作，常在夜间\n\nbronchial asthma 10 mg",
        )

    def test_artifact_exposes_layers_without_serializing_new_schema(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第四章 支气管哮喘",
            source_heading="定义与概述",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text="支气管 哮喘",
            page_start=62,
            page_end=62,
        )
        self.assertEqual(artifact.raw_text, "支气管 哮喘")
        self.assertEqual(artifact.canonical_text, "支气管哮喘")
        self.assertEqual(artifact.display_text, "支气管哮喘")
        self.assertNotIn("canonical_text", artifact.to_dict())
        self.assertNotIn("display_text", artifact.to_dict())

    def test_display_layer_is_idempotent(self):
        once = build_text_layers("定义 ：\n哮喘")
        twice = build_text_layers(once.display_text)
        self.assertEqual(twice.display_text, once.display_text)


if __name__ == "__main__":
    unittest.main()
