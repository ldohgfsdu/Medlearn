import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

QUALITY = importlib.util.module_from_spec(
    importlib.util.spec_from_file_location(
        "merge_duplicate_quality",
        SCRIPTS / "merge_duplicate_quality.py",
    )
)
assert QUALITY
sys.modules["merge_duplicate_quality"] = QUALITY
importlib.util.spec_from_file_location(
    "merge_duplicate_quality",
    SCRIPTS / "merge_duplicate_quality.py",
).loader.exec_module(QUALITY)


class MergeDuplicateQualityTests(unittest.TestCase):
    def test_strip_redundant_title_prefix(self) -> None:
        self.assertEqual(
            QUALITY.strip_redundant_title_prefix(
                "心肌炎的实验室检查",
                "心肌炎的实验室检查：白细胞计数增高。",
            ),
            "白细胞计数增高。",
        )

    def test_truncated_sentence_detected(self) -> None:
        self.assertTrue(
            QUALITY.is_truncated_content("约有1/3病人有痰血或")
        )
        self.assertFalse(
            QUALITY.is_truncated_content("约有1/3病人有痰血或咯血。")
        )

    def test_aspect_title_conflict(self) -> None:
        self.assertIn(
            "影像学",
            QUALITY.aspect_title_conflicts("临床表现", "肺脓肿的影像学表现"),
        )
        self.assertIn(
            "鉴别诊断",
            QUALITY.aspect_title_conflicts("诊断", "主动脉夹层的鉴别诊断"),
        )

    def test_entity_attribution_conflict(self) -> None:
        conflicts = QUALITY.entity_attribution_conflicts(
            "梗阻性休克",
            [
                {"id": "a", "source_span": {"parent_entity": "梗阻性休克"}},
                {"id": "b", "source_span": {"parent_entity": "血流动力学不稳定"}},
            ],
        )
        self.assertEqual(len(conflicts), 1)

    def test_duplicate_body_conflict(self) -> None:
        shared = "PTE病人可出现胸膜炎样胸痛，合并胸腔积液"
        conflicts = QUALITY.duplicate_body_conflicts(
            [
                {
                    "title": "晕厥的鉴别诊断",
                    "content": f"晕厥的鉴别诊断包含{shared}",
                },
                {
                    "title": "胸腔积液的鉴别诊断",
                    "content": f"胸腔积液的鉴别诊断包含{shared}",
                },
            ]
        )
        self.assertEqual(len(conflicts), 1)

    def test_section_entity_attribution_conflict(self) -> None:
        conflicts = QUALITY.entity_attribution_conflicts(
            "血流动力学不稳定",
            [{"id": "a", "source_span": {"parent_entity": "血流动力学不稳定"}}],
            [
                {"title": "血流动力学不稳定", "content": "包括梗阻性休克的定义"},
                {"title": "梗阻性休克的定义", "content": "收缩压＜90mmHg"},
            ],
        )
        self.assertTrue(any("梗阻性休克" in issue for issue in conflicts))

    def test_assess_merge_group_collects_blockers(self) -> None:
        blockers = QUALITY.assess_merge_group(
            group_aspect="临床表现",
            group_parent="肺脓肿",
            members=[{"id": "1", "source_span": {"parent_entity": "肺脓肿"}}],
            sections=[
                {
                    "title": "肺脓肿的影像学表现",
                    "content": "胸部X线显示空洞。",
                },
                {
                    "title": "肺脓肿的痰血情况",
                    "content": "约有1/3病人有痰血或",
                },
            ],
        )
        self.assertTrue(any(item.startswith("aspect_title_conflict:") for item in blockers))
        self.assertTrue(any(item.startswith("truncated_sentence:") for item in blockers))


if __name__ == "__main__":
    unittest.main()