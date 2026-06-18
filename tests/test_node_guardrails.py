import importlib.util
import json
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from textbook_pipeline.node_guardrails import (  # noqa: E402
    assess_guardrails,
    count_duplicate_parent_aspects,
    evidence_supported_by_source,
    extract_section_entity,
    filter_guarded_rows,
    guard_node_row,
    is_cross_disease_expansion,
    looks_self_referential_evidence,
)


class NodeGuardrailsTests(unittest.TestCase):
    def test_extract_section_entity(self) -> None:
        self.assertEqual(extract_section_entity("第四章 支气管哮喘"), "支气管哮喘")

    def test_cross_disease_expansion_detects_hallucinated_combo(self) -> None:
        self.assertTrue(
            is_cross_disease_expansion(
                "抗IL-5单克隆抗体治疗变应性鼻炎",
                "变应性鼻炎",
                section_entity="支气管哮喘",
            )
        )
        self.assertFalse(
            is_cross_disease_expansion(
                "抗IL-5单克隆抗体治疗哮喘",
                "哮喘",
                section_entity="支气管哮喘",
            )
        )

    def test_evidence_must_exist_in_source(self) -> None:
        source = "②抗IL-5 单克隆抗体：通过阻断IL-5 的作用，抑制体内嗜酸性粒细胞增多而治疗哮喘。"
        self.assertTrue(
            evidence_supported_by_source(
                "②抗IL-5 单克隆抗体：通过阻断IL-5 的作用，抑制体内嗜酸性粒细胞增多而治疗哮喘。",
                source,
            )
        )
        self.assertFalse(
            evidence_supported_by_source(
                "变应性鼻炎合并哮喘的患者，应同时进行鼻部和气道治疗。",
                source,
            )
        )

    def test_self_referential_evidence_is_rejected(self) -> None:
        evidence = "抗IL-5单克隆抗体可用于治疗变应性鼻炎，以减少嗜酸性粒细胞的增多"
        content = f"抗IL-5单克隆抗体治疗变应性鼻炎：{evidence}"
        self.assertTrue(looks_self_referential_evidence(evidence, content))

    def test_filter_guarded_rows_removes_ungrounded_nodes(self) -> None:
        source = "②抗IL-5 单克隆抗体：通过阻断IL-5 的作用，抑制体内嗜酸性粒细胞增多而治疗哮喘。"
        rows = [
            {
                "title": "抗IL-5单克隆抗体治疗哮喘",
                "content": "抗IL-5单克隆抗体治疗哮喘：抑制嗜酸性粒细胞增多而治疗哮喘",
                "source_span": {
                    "parent_entity": "哮喘",
                    "aspect": "治疗方案",
                    "evidence": "②抗IL-5 单克隆抗体：通过阻断IL-5 的作用，抑制体内嗜酸性粒细胞增多而治疗哮喘。",
                },
            },
            {
                "title": "抗IL-5单克隆抗体治疗变应性鼻炎",
                "content": "抗IL-5单克隆抗体治疗变应性鼻炎：减少嗜酸性粒细胞",
                "source_span": {
                    "parent_entity": "变应性鼻炎",
                    "aspect": "治疗方案",
                    "evidence": "抗IL-5单克隆抗体可用于治疗变应性鼻炎，以减少嗜酸性粒细胞的增多。",
                },
            },
        ]
        kept, rejected = filter_guarded_rows(
            rows,
            section_entity="支气管哮喘",
            section_markdown=source,
        )
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["title"], "抗IL-5单克隆抗体治疗哮喘")
        self.assertGreaterEqual(len(rejected), 1)

    def test_assess_guardrails_fails_when_unsafe_nodes_remain(self) -> None:
        report = assess_guardrails(
            [
                {
                    "title": "抗IL-5单克隆抗体治疗变应性鼻炎",
                    "content": "抗IL-5单克隆抗体治疗变应性鼻炎：减少嗜酸性粒细胞",
                    "source_span": {
                        "parent_entity": "变应性鼻炎",
                        "aspect": "治疗方案",
                        "evidence": "抗IL-5单克隆抗体可用于治疗变应性鼻炎，以减少嗜酸性粒细胞的增多。",
                    },
                }
            ],
            section_entity="支气管哮喘",
            section_markdown="②抗IL-5 单克隆抗体：抑制体内嗜酸性粒细胞增多而治疗哮喘。",
        )
        self.assertFalse(report["passed"])
        self.assertIn("unsafe_nodes_present", report["reasons"])

    def test_guard_node_row_requires_source_text(self) -> None:
        ok, reason = guard_node_row(
            {
                "title": "支气管哮喘的定义",
                "content": "支气管哮喘的定义：支气管哮喘是一种以慢性气道炎症为特征的异质性疾病",
                "source_span": {
                    "parent_entity": "支气管哮喘",
                    "aspect": "定义",
                    "evidence": "支气管哮喘是一种以慢性气道炎症为特征的异质性疾病。",
                },
            },
            section_entity="支气管哮喘",
            source_text="",
        )
        self.assertFalse(ok)
        self.assertEqual(reason, "missing_source_text")

    def test_duplicate_parent_aspects_fail_guardrails(self) -> None:
        rows = [
            {
                "title": f"高血压的治疗方案{index}",
                "content": "高血压治疗应根据患者情况选择药物并持续评估疗效。",
                "chapter": "第三篇 循环系统疾病",
                "sub_chapter": "第五章 高血压",
                "source_span": {
                    "parent_entity": "高血压",
                    "aspect": "治疗方案",
                    "evidence": "高血压治疗应根据患者情况选择药物并持续评估疗效。",
                },
            }
            for index in range(2)
        ]
        self.assertEqual(count_duplicate_parent_aspects(rows), 1)
        report = assess_guardrails(
            rows,
            section_entity="高血压",
            section_markdown="高血压治疗应根据患者情况选择药物并持续评估疗效。",
        )
        self.assertFalse(report["passed"])
        self.assertIn("duplicate_parent_aspect_nodes", report["reasons"])


if __name__ == "__main__":
    unittest.main()
