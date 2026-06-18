import importlib.util
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "backfill_disease_entities.py"
SPEC = importlib.util.spec_from_file_location("backfill_disease_entities", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


class DiseaseIdentityBackfillTests(unittest.TestCase):
    def test_explicit_aliases_share_one_canonical_key(self):
        canonical, aliases = MODULE.split_explicit_aliases("慢性阻塞性肺疾病（COPD）")
        self.assertEqual(canonical, "慢性阻塞性肺疾病")
        self.assertEqual(aliases, ["COPD"])

    def test_parent_and_subtype_are_not_merged(self):
        self.assertNotEqual(
            MODULE.normalize_disease_name("肺炎"),
            MODULE.normalize_disease_name("细菌性肺炎"),
        )

    def test_golden_aliases_resolve_to_one_canonical_disease(self):
        for alias in ("COPD", "慢阻肺", "慢阻肺病"):
            canonical, aliases = MODULE.canonicalize_candidate(alias)
            self.assertEqual(canonical, "慢性阻塞性肺疾病")
            self.assertIn("COPD", aliases)

    def test_pneumonia_overview_is_not_a_disease(self):
        content_class, _, _ = MODULE.classify_candidate("肺炎", "disease")
        self.assertEqual(content_class, "non_disease_knowledge")

    def test_cross_chapter_golden_disease_is_invalid(self):
        sections, diseases, updates, _ = MODULE.build_rows([
            {
                "id": "wrong-tb",
                "title": "空洞性肺结核的症状",
                "type": "disease",
                "chapter": "第二篇 呼吸系统疾病",
                "sub_chapter": "第七章 肺脓肿",
                "book_id": "internal-medicine-10",
                "source_span": {
                    "parent_entity": "肺结核",
                    "aspect": "症状",
                    "evidence": "肺结核可有咳嗽。",
                    "page_start": 99,
                },
            }
        ])
        self.assertTrue(sections)
        self.assertEqual(diseases, [])
        self.assertEqual(updates[0]["content_class"], "invalid")

    def test_golden_disease_requires_page_evidence_before_available(self):
        _, diseases, _, _ = MODULE.build_rows([
            {
                "id": f"asthma-{index}",
                "title": f"支气管哮喘的{aspect}",
                "type": "disease",
                "chapter": "第二篇 呼吸系统疾病",
                "sub_chapter": "第四章 支气管哮喘",
                "book_id": "internal-medicine-10",
                "source_span": {
                    "parent_entity": "支气管哮喘",
                    "aspect": aspect,
                    "evidence": "教材证据",
                    "page_start": 62 + index,
                },
            }
            for index, aspect in enumerate(("定义", "临床表现", "治疗"))
        ])
        self.assertEqual(diseases[0]["content_status"], "available")

    def test_wrong_chapter_legacy_node_does_not_block_grounded_golden_disease(self):
        nodes = [
            {
                "id": f"tb-{index}",
                "title": f"肺结核的{aspect}",
                "type": "disease",
                "chapter": "第二篇 呼吸系统疾病",
                "sub_chapter": "第八章 肺结核",
                "book_id": "internal-medicine-10",
                "source_span": {
                    "parent_entity": "肺结核",
                    "aspect": aspect,
                    "evidence": "教材证据",
                    "page_start": 102 + index,
                },
            }
            for index, aspect in enumerate(("定义", "临床表现", "治疗"))
        ]
        nodes.append({
            "id": "wrong-tb",
            "title": "肺结核的定义",
            "type": "disease",
            "chapter": "第二篇 呼吸系统疾病",
            "sub_chapter": "第七章 肺脓肿",
            "book_id": "internal-medicine-10",
            "source_span": {
                "parent_entity": "肺结核",
                "aspect": "定义",
                "evidence": "错章 legacy 数据",
            },
        })

        _, diseases, updates, _ = MODULE.build_rows(nodes)

        self.assertEqual(diseases[0]["content_status"], "available")
        wrong_update = next(update for update in updates if update["id"] == "wrong-tb")
        self.assertEqual(wrong_update["content_class"], "invalid")

    def test_known_redundant_prefix_is_normalized_without_contains_matching(self):
        self.assertEqual(
            MODULE.normalize_disease_name("肺炎衣原体肺炎"),
            MODULE.normalize_disease_name("衣原体肺炎"),
        )

    def test_stable_ids_depend_on_series_and_normalized_identity(self):
        first = MODULE.stable_id("disease", "internal-medicine", "慢性阻塞性肺疾病")
        second = MODULE.stable_id("disease", "internal-medicine", "慢性阻塞性肺疾病")
        other_series = MODULE.stable_id("disease", "respiratory-medicine", "慢性阻塞性肺疾病")
        self.assertEqual(first, second)
        self.assertNotEqual(first, other_series)

    def test_legacy_disease_type_does_not_promote_drugs_or_procedures(self):
        for name in ("地高辛", "β受体拮抗剂", "主动脉瓣置换术", "心脏再同步治疗"):
            content_class, _, _ = MODULE.classify_candidate(
                name,
                "disease",
                evidence_count=4,
                aspect_count=3,
            )
            self.assertEqual(content_class, "non_disease_knowledge", name)

    def test_multiple_aspects_do_not_promote_unknown_entities(self):
        content_class, _, _ = MODULE.classify_candidate(
            "ICS",
            "disease",
            evidence_count=5,
            aspect_count=4,
        )
        self.assertEqual(content_class, "non_disease_knowledge")

    def test_clinical_conditions_and_abbreviations_remain_confirmed(self):
        for name in (
            "主动脉夹层",
            "心房颤动",
            "PTE",
            "急性PTE",
            "支气管哮喘",
            "肺脓肿",
            "阻塞性睡眠呼吸暂停",
            "下肢动脉硬化闭塞症",
            "心血管神经症",
            "冠状动脉瘘",
            "心肌桥",
            "急性呼吸窘迫综合征",
        ):
            content_class, _, _ = MODULE.classify_candidate(
                name,
                "concept",
                evidence_count=1,
                aspect_count=1,
            )
            self.assertEqual(content_class, "confirmed_disease", name)

    def test_parallel_disease_title_is_not_one_disease_entity(self):
        content_class, _, _ = MODULE.classify_candidate(
            "不稳定型心绞痛或非ST段抬高型心肌梗死",
            "disease",
        )
        self.assertEqual(content_class, "non_disease_knowledge")


if __name__ == "__main__":
    unittest.main()
