import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_artifact import EvidenceLocator, make_artifact
from textbook_pipeline.evidence_artifact_audit import audit_artifacts


def _artifact(order: int, artifact_type: str, text: str, page: int, bbox: tuple[float, ...]):
    return make_artifact(
        textbook_id="internal-medicine-10",
        book_id="internal-medicine-10",
        part_title="第二篇 呼吸系统疾病",
        section_title="第六章 肺部感染性疾病",
        source_heading="测试标题",
        normalized_aspect=None,
        source_order=order,
        artifact_type=artifact_type,
        raw_text=text,
        page_start=page,
        page_end=page,
        locator=EvidenceLocator(page=page, kind=artifact_type, bbox=bbox),
    )


class EvidenceArtifactAuditTests(unittest.TestCase):
    def test_detects_caption_like_text_and_table_binding(self):
        artifacts = [
            _artifact(0, "text_block", "表 2-1 肺炎常见病原体", 10, (80, 90, 500, 120)),
            _artifact(1, "table", "| 病原体 | 特点 |\n|---|---|\n| 细菌 | 常见 |", 10, (70, 130, 520, 500)),
            _artifact(2, "text_block", "注：资料来自教材原表。", 10, (80, 510, 500, 540)),
        ]

        report = audit_artifacts(artifacts)

        self.assertEqual(report["summary"]["table"], 1)
        self.assertEqual(report["summary"]["caption_like_text"], 2)
        binding = report["table_bindings"][0]
        self.assertEqual(binding["column_count"], 2)
        self.assertEqual(len(binding["caption_artifact_ids"]), 1)
        self.assertEqual(len(binding["note_artifact_ids"]), 1)

    def test_detects_possible_continued_table(self):
        artifacts = [
            _artifact(0, "table", "| A | B |\n|---|---|\n| 1 | 2 |", 20, (60, 620, 520, 760)),
            _artifact(1, "table", "| A | B |\n|---|---|\n| 3 | 4 |", 21, (60, 80, 520, 300)),
        ]

        report = audit_artifacts(artifacts)

        self.assertEqual(len(report["possible_continued_tables"]), 1)
        self.assertTrue(any(w["type"] == "possible_continued_table" for w in report["warnings"]))

    def test_detects_list_topology(self):
        artifacts = [
            _artifact(
                0,
                "text_block",
                "一、定义\n（一）亚型\n1. 具体表现\n2. 其他表现",
                30,
                (70, 100, 520, 300),
            )
        ]

        report = audit_artifacts(artifacts)

        self.assertEqual(report["summary"]["list_like_text"], 1)
        self.assertEqual(report["list_artifacts"][0]["render_type"], "pre_formatted_list")
        self.assertTrue(report["list_artifacts"][0]["layout_topology_hash"])

    def test_flags_figure_caption_without_figure_artifact(self):
        artifacts = [
            _artifact(0, "text_block", "图 3-1 侧支循环示意图", 40, (80, 400, 500, 430)),
        ]

        report = audit_artifacts(artifacts)

        self.assertTrue(
            any(w["type"] == "missing_figure_context_warning" for w in report["warnings"])
        )


if __name__ == "__main__":
    unittest.main()
