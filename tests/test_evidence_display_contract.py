import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.evidence_display_contract import (  # noqa: E402
    DISPLAY_CONTRACT_VERSION,
    build_display_contract_payload,
)


def _row(
    row_id: str,
    *,
    title: str,
    body: str,
    evidence: str,
    heading: str,
    artifact_id: str,
    page: int,
    order: int,
) -> dict:
    return {
        "id": row_id,
        "title": title,
        "content": body,
        "sub_chapter": "Chapter 7 Congenital cardiovascular disease",
        "order_num": order,
        "source_span": {
            "artifact_id": artifact_id,
            "item_index": order,
            "source_heading": heading,
            "evidence": evidence,
            "page_start": page,
            "page_end": page,
            "verification_state": "pass",
            "candidate_only": True,
        },
    }


class EvidenceDisplayContractTests(unittest.TestCase):
    def _normalized_payload(self) -> dict:
        return {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part 3 Circulatory diseases",
            "section_title": "Chapter 7 Congenital cardiovascular disease",
            "source_path": "candidate.json",
            "node_count": 3,
            "nodes": [
                _row(
                    "kn-a",
                    title="Definition",
                    body="Congenital cardiovascular disease refers to abnormal development",
                    evidence="Congenital cardiovascular disease refers to abnormal development",
                    heading="Definition",
                    artifact_id="art-a",
                    page=319,
                    order=0,
                ),
                _row(
                    "kn-b",
                    title="Definition",
                    body="of the heart and great vessels during fetal life.",
                    evidence="of the heart and great vessels during fetal life.",
                    heading="Definition",
                    artifact_id="art-b",
                    page=319,
                    order=1,
                ),
                _row(
                    "kn-c",
                    title="Atrial septal defect",
                    body="Atrial septal defect is a common adult congenital heart disease.",
                    evidence="Atrial septal defect is a common adult congenital heart disease.",
                    heading="Atrial septal defect",
                    artifact_id="art-c",
                    page=320,
                    order=2,
                ),
            ],
        }

    def test_builds_frontend_display_contract(self):
        payload = build_display_contract_payload(self._normalized_payload())

        self.assertEqual(payload["version"], DISPLAY_CONTRACT_VERSION)
        self.assertEqual(payload["textbook_id"], "internal-medicine-10")
        self.assertEqual(payload["summary"]["organized"], 2)
        first = payload["nodes"][0]
        self.assertEqual(first["render_type"], "merged")
        self.assertEqual(first["publication_state"], "organized")
        self.assertEqual(first["display"]["page_label"], "p.319")
        self.assertIn("merged", first["quality_badges"])
        self.assertEqual(first["merge"]["child_node_ids"], ["kn-a", "kn-b"])
        self.assertEqual(
            first["display"]["body"],
            "Congenital cardiovascular disease refers to abnormal development "
            "of the heart and great vessels during fetal life.",
        )
        self.assertEqual(len(first["evidence_items"]), 2)

    def test_does_not_merge_different_source_heading(self):
        payload = build_display_contract_payload(self._normalized_payload())

        self.assertEqual(payload["nodes"][1]["render_type"], "normal")
        self.assertEqual(payload["nodes"][1]["display"]["source_heading"], "Atrial septal defect")

    def test_cross_page_range_uses_single_page_prefix(self):
        normalized_payload = self._normalized_payload()
        normalized_payload["nodes"][1]["source_span"]["page_start"] = 320
        normalized_payload["nodes"][1]["source_span"]["page_end"] = 320

        payload = build_display_contract_payload(normalized_payload)

        self.assertEqual(payload["nodes"][0]["render_type"], "merged")
        self.assertEqual(payload["nodes"][0]["display"]["page_label"], "p.319-320")

    def test_needs_review_candidate_becomes_evidence_only(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-risk",
                    "item_index": 0,
                    "title": "Intervention",
                    "aspect": "Treatment",
                    "source_heading": "Treatment",
                    "evidence": "If anatomical conditions are suitable, catheter closure is preferred.",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-rejected",
                    "item_index": 0,
                    "title": "Rejected item",
                    "evidence": "This should not appear.",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "rejected",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(len(evidence_only), 1)
        self.assertEqual(evidence_only[0]["render_type"], "evidence_only")
        self.assertEqual(evidence_only[0]["display"]["title"], "Treatment")
        self.assertEqual(evidence_only[0]["display"]["body"], "")
        self.assertIn("conservative_fallback", evidence_only[0]["quality_badges"])
        self.assertEqual(evidence_only[0]["evidence_items"][0]["artifact_id"], "art-risk")

    def test_evidence_only_title_uses_source_heading_not_llm_title(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-noisy",
                    "item_index": 0,
                    "title": "LLM-compressed unsupported title",
                    "aspect": "Source Aspect",
                    "source_heading": "Original Textbook Heading",
                    "evidence": "Original evidence span.",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(evidence_only[0]["display"]["title"], "Original Textbook Heading")
        self.assertEqual(evidence_only[0]["evidence_items"][0]["text"], "Original evidence span.")

    def test_evidence_only_title_does_not_use_generic_aspect_heading(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-treatment",
                    "item_index": 0,
                    "title": "Unsupported LLM title",
                    "aspect": "治疗",
                    "source_heading": "治疗",
                    "evidence": "具体药物和剂量相关原文片段，不包含泛化小标题。",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(evidence_only[0]["display"]["title"], "原文证据")
        self.assertEqual(evidence_only[0]["display"]["source_heading"], "治疗")

    def test_evidence_only_title_uses_generic_label_for_section_heading(self):
        candidate_payload = {
            "part_title": "第一篇 绪论",
            "section_title": "绪论",
            "candidate_items": [
                {
                    "artifact_id": "art-generic-heading",
                    "item_index": 0,
                    "title": "Unsupported LLM title",
                    "aspect": "绪论",
                    "source_heading": "绪论",
                    "evidence": "Original source paragraph without the section heading.",
                    "page_start": 1,
                    "page_end": 1,
                    "verification_state": "needs_review",
                },
            ],
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(evidence_only[0]["display"]["title"], "原文证据")
        self.assertEqual(evidence_only[0]["display"]["source_heading"], "绪论")

    def test_evidence_only_title_treats_formal_section_heading_as_generic(self):
        candidate_payload = {
            "part_title": "第三篇 循环系统疾病",
            "section_title": "第三章 心律失常",
            "candidate_items": [
                {
                    "artifact_id": "art-formal-section",
                    "item_index": 0,
                    "title": "Unsupported LLM title",
                    "aspect": "第八节  |  心律失常的介入治疗和手术治疗",
                    "source_heading": "第八节  |  心律失常的介入治疗和手术治疗",
                    "evidence": "连续原文证据片段。",
                    "page_start": 244,
                    "page_end": 244,
                    "verification_state": "needs_review",
                },
            ],
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(evidence_only[0]["display"]["title"], "原文证据")
        self.assertEqual(
            evidence_only[0]["display"]["source_heading"],
            "第八节  |  心律失常的介入治疗和手术治疗",
        )

    def test_evidence_only_title_treats_digital_resource_heading_as_generic(self):
        candidate_payload = {
            "part_title": "第七篇 内分泌和代谢性疾病",
            "section_title": "第七章 肾上腺疾病",
            "candidate_items": [
                {
                    "artifact_id": "art-digital-resource",
                    "item_index": 0,
                    "title": "原文证据片段",
                    "aspect": "本章数字资源 第七章 肾上腺疾病",
                    "source_heading": "本章数字资源 第七章 肾上腺疾病",
                    "evidence": "家族性者以肾上腺素为主。",
                    "page_start": 752,
                    "page_end": 752,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(evidence_only[0]["display"]["title"], "原文证据")
        self.assertEqual(evidence_only[0]["display"]["source_heading"], "本章数字资源 第七章 肾上腺疾病")

    def test_display_fields_drop_pdf_control_characters(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-control",
                    "item_index": 0,
                    "title": "Unsupported LLM title",
                    "aspect": "第四章 \x07动脉粥样硬化",
                    "source_heading": "第四章 \x07动脉粥样硬化",
                    "evidence": "冠脉CTA 有较高阴性预测价值。",
                    "page_start": 266,
                    "page_end": 266,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertNotIn("\x07", evidence_only[0]["display"]["source_heading"])

    def test_evidence_only_title_keeps_title_when_present_in_evidence(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-supported-title",
                    "item_index": 0,
                    "title": "Antibacterial treatment",
                    "aspect": "Treatment",
                    "source_heading": "Original Textbook Heading",
                    "evidence": "Antibacterial treatment is the source heading inside this evidence.",
                    "page_start": 321,
                    "page_end": 321,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        evidence_only = [node for node in payload["nodes"] if node["publication_state"] == "evidence_only"]
        self.assertEqual(evidence_only[0]["display"]["title"], "Antibacterial treatment")

    def test_evidence_only_nodes_are_sorted_back_into_source_order(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-risk-early",
                    "item_index": 0,
                    "title": "Treatment note",
                    "aspect": "Treatment",
                    "source_heading": "Definition",
                    "evidence": "Original treatment evidence on the earlier page.",
                    "page_start": 318,
                    "page_end": 318,
                    "verification_state": "needs_review",
                }
            ]
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        self.assertEqual(payload["nodes"][0]["id"], "view-evidence-art-risk-early-0")
        self.assertEqual(payload["nodes"][0]["publication_state"], "evidence_only")

    def test_related_classification_items_become_numbered_group(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part 2 Respiratory diseases",
            "section_title": "Chapter 6 Pulmonary infections",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-class",
                    title="\u80ba\u708e\u7684\u5206\u7c7b",
                    body="\u80ba\u708e\u53ef\u6309\u89e3\u5256\u3001\u75c5\u56e0\u6216\u60a3\u75c5\u73af\u5883\u52a0\u4ee5\u5206\u7c7b\u3002",
                    evidence="\u3010\u5206\u7c7b\u3011 \u80ba\u708e\u53ef\u6309\u89e3\u5256\u3001\u75c5\u56e0\u6216\u60a3\u75c5\u73af\u5883\u52a0\u4ee5\u5206\u7c7b\u3002",
                    heading="Chapter 6 Pulmonary infections",
                    artifact_id="art-class",
                    page=77,
                    order=0,
                ),
                _row(
                    "kn-lobar",
                    title="\u5927\u53f6\u6027\uff08\u80ba\u6ce1\u6027\uff09\u80ba\u708e",
                    body="\u75c5\u539f\u4f53\u5148\u5728\u80ba\u6ce1\u5f15\u8d77\u708e\u75c7\u3002",
                    evidence="\u75c5\u539f\u4f53\u5148\u5728\u80ba\u6ce1\u5f15\u8d77\u708e\u75c7\u3002",
                    heading="Chapter 6 Pulmonary infections",
                    artifact_id="art-lobar",
                    page=77,
                    order=1,
                ),
                _row(
                    "kn-broncho",
                    title="\u5c0f\u53f6\u6027\uff08\u652f\u6c14\u7ba1\u6027\uff09\u80ba\u708e",
                    body="\u75c5\u539f\u4f53\u7ecf\u652f\u6c14\u7ba1\u5165\u4fb5\u3002",
                    evidence="\u75c5\u539f\u4f53\u7ecf\u652f\u6c14\u7ba1\u5165\u4fb5\u3002",
                    heading="Chapter 6 Pulmonary infections",
                    artifact_id="art-broncho",
                    page=77,
                    order=2,
                ),
            ],
        }

        payload = build_display_contract_payload(normalized_payload)

        self.assertEqual(len(payload["nodes"]), 1)
        group = payload["nodes"][0]
        self.assertEqual(group["render_type"], "grouped")
        self.assertEqual(group["group"]["topic"], "classification")
        self.assertEqual(len(group["display"]["items"]), 3)
        self.assertIn("group:classification", group["quality_badges"])

    def test_auxiliary_exam_items_stay_under_exam_group(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part 2 Respiratory diseases",
            "section_title": "Chapter 4 Bronchial asthma",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-sign",
                    title="体征",
                    body="发作时可闻及哮鸣音。",
                    evidence="2. 体征 发作时可闻及哮鸣音。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-sign",
                    page=63,
                    order=65,
                ),
                _row(
                    "kn-sputum-eos",
                    title="痰嗜酸性粒细胞计数",
                    body="诱导痰中嗜酸性粒细胞计数增高。",
                    evidence="（一） 痰嗜酸性粒细胞计数 诱导痰中嗜酸性粒细胞计数增高。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-sputum",
                    page=63,
                    order=66,
                ),
                _row(
                    "kn-blood-eos",
                    title="外周血嗜酸性粒细胞计数",
                    body="部分哮喘病人外周血嗜酸性粒细胞计数增高。",
                    evidence="（二） 外周血嗜酸性粒细胞计数 部分哮喘病人外周血嗜酸性粒细胞计数增高。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-blood",
                    page=63,
                    order=68,
                ),
                _row(
                    "kn-ventilation",
                    title="通气功能检测",
                    body="哮喘发作时呈阻塞性通气功能障碍表现。",
                    evidence="1. 通气功能检测 哮喘发作时呈阻塞性通气功能障碍表现。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-ventilation",
                    page=64,
                    order=71,
                ),
                _row(
                    "kn-bronchodilator",
                    title="支气管舒张试验",
                    body="用于测定气道的可逆性改变。",
                    evidence="3. 支气管舒张试验 用于测定气道的可逆性改变。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-bronchodilator",
                    page=64,
                    order=79,
                ),
                _row(
                    "kn-feno",
                    title="呼出气一氧化氮（FeNO）检测",
                    body="FeNO测定可作为评估哮喘控制水平的指标。",
                    evidence="（七） 呼出气一氧化氮（FeNO）检测 FeNO测定可作为评估哮喘控制水平的指标。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-feno",
                    page=64,
                    order=94,
                ),
                _row(
                    "kn-diagnosis",
                    title="支气管哮喘的诊断标准",
                    body="符合症状和体征并具备客观检查之一。",
                    evidence="符合症状和体征并具备客观检查之一，可以诊断为哮喘。",
                    heading="Chapter 4 Bronchial asthma",
                    artifact_id="art-diagnosis",
                    page=64,
                    order=102,
                ),
            ],
        }
        candidate_payload = {
            "part_title": "Part 2 Respiratory diseases",
            "section_title": "Chapter 4 Bronchial asthma",
            "candidate_items": [
                {
                    "artifact_id": "art-treatment-response",
                    "item_index": 0,
                    "title": "治疗反应观察指标",
                    "aspect": "Chapter 4 Bronchial asthma",
                    "source_heading": "Chapter 4 Bronchial asthma",
                    "evidence": "可以作为药物的选择和治疗后反应的观察指标。",
                    "page_start": 63,
                    "page_end": 63,
                    "source_order": 70,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-ventilation-source-only",
                    "item_index": 0,
                    "title": "肺功能检查",
                    "aspect": "Chapter 4 Bronchial asthma",
                    "source_heading": "Chapter 4 Bronchial asthma",
                    "evidence": "肺功能检查 是判断持续气流受限的主要方法。FEV1/FVC＜70%",
                    "page_start": 64,
                    "page_end": 64,
                    "source_order": 70,
                    "verification_state": "needs_review",
                },
            ],
        }

        payload = build_display_contract_payload(
            normalized_payload,
            candidate_payload=candidate_payload,
        )

        exam_group = next(node for node in payload["nodes"] if node.get("group", {}).get("topic") == "auxiliary_exam")
        self.assertEqual(exam_group["render_type"], "grouped")
        self.assertEqual(exam_group["display"]["title"], "实验室和其他检查")
        self.assertIn("group:auxiliary_exam", exam_group["quality_badges"])
        self.assertEqual(
            [item["title"] for item in exam_group["display"]["items"]],
            [
                "痰嗜酸性粒细胞计数",
                "外周血嗜酸性粒细胞计数",
                "肺功能检查",
                "呼出气一氧化氮（FeNO）检测",
            ],
        )
        blood_item = exam_group["display"]["items"][1]
        self.assertNotIn("药物的选择", blood_item["body"])
        self.assertEqual(blood_item["evidence_artifact_ids"], ["art-blood"])
        self.assertEqual(blood_item["children"][0]["publication_state"], "evidence_only")
        self.assertIn("药物的选择", blood_item["children"][0]["body"])
        self.assertEqual(blood_item["children"][0]["evidence_artifact_ids"], ["art-treatment-response"])
        lung_function = exam_group["display"]["items"][2]
        self.assertEqual(
            [item["title"] for item in lung_function["children"]],
            ["通气功能检测", "支气管舒张试验（BDT）"],
        )
        self.assertEqual(lung_function["children"][0]["evidence_artifact_ids"], ["art-ventilation"])
        self.assertEqual(lung_function["children"][0]["children"][0]["publication_state"], "evidence_only")
        self.assertEqual(
            lung_function["children"][0]["children"][0]["evidence_artifact_ids"],
            ["art-ventilation-source-only"],
        )
        self.assertEqual(lung_function["children"][1]["evidence_artifact_ids"], ["art-bronchodilator"])
        self.assertEqual(payload["nodes"][-1]["display"]["title"], "支气管哮喘的诊断标准")
        self.assertFalse(
            any(node.get("group", {}).get("topic") == "treatment" for node in payload["nodes"])
        )

    def test_tb_classification_items_form_recursive_tree(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "第二篇 呼吸系统疾病",
            "section_title": "第八章 肺结核",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-tb-class-intro",
                    title="结核病的分类标准",
                    body="根据我国实施的《结核病分类》（WS 196—2017）标准，肺结核可按不同",
                    evidence="根据我国实施的《结核病分类》（WS 196—2017）标准，肺结核可按不同",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-class-intro",
                    page=106,
                    order=156,
                ),
                _row(
                    "kn-tb-latent",
                    title="结核分枝杆菌潜伏感染者",
                    body="机体内感染了结核分枝杆菌，但没有发生临床结核病，没有临",
                    evidence="（一）结核分枝杆菌潜伏感染者 机体内感染了结核分枝杆菌，但没有发生临床结核病，没有临",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-latent",
                    page=107,
                    order=157,
                ),
                _row(
                    "kn-tb-active",
                    title="活动性结核病的定义",
                    body="具有结核病相关的临床症状和体征，结核分枝杆菌病原学、病理学、影像学",
                    evidence="（二）活动性结核病 具有结核病相关的临床症状和体征，结核分枝杆菌病原学、病理学、影像学",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-active",
                    page=107,
                    order=159,
                ),
                _row(
                    "kn-tb-site-axis",
                    title="肺结核的病变部位",
                    body="肺结核病的结核病变可发生在肺、气管、支气管和胸膜等部位。按照病变部位，分为",
                    evidence="肺结核病的结核病变可发生在肺、气管、支气管和胸膜等部位。按照病变部位，分为",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-site-axis",
                    page=107,
                    order=161,
                ),
                _row(
                    "kn-tb-primary",
                    title="原发性肺结核",
                    body="包括原发综合征和胸内淋巴结结核",
                    evidence="1）原发性肺结核：包括原发综合征和胸内淋巴结结核",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-primary",
                    page=107,
                    order=162,
                ),
                _row(
                    "kn-tb-hematogenous",
                    title="血行播散性肺结核",
                    body="含急性、亚急性和慢性血行播散性肺结核",
                    evidence="2）血行播散性肺结核：含急性、亚急性和慢性血行播散性肺结核",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-hematogenous",
                    page=108,
                    order=170,
                ),
                _row(
                    "kn-tb-etiology-axis",
                    title="按病原学检查结果分类",
                    body="分为病原学阳性、病原学阴性和病原学未查肺结核",
                    evidence="2. 按病原学检查结果分类 分为病原学阳性、病原学阴性和病原学未查肺结核",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-etiology-axis",
                    page=109,
                    order=214,
                ),
                _row(
                    "kn-tb-resistance-axis",
                    title="肺结核的耐药分类",
                    body="按耐药状况分类，分为敏感肺结核和耐药肺结核",
                    evidence="3. 按耐药状况分类 分为敏感肺结核和耐药肺结核",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-resistance-axis",
                    page=109,
                    order=218,
                ),
                _row(
                    "kn-tb-history-axis",
                    title="按既往治疗史分类",
                    body="分为初治肺结核和复治肺结核",
                    evidence="4. 按既往治疗史分类 分为初治肺结核和复治肺结核",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-history-axis",
                    page=109,
                    order=219,
                ),
                _row(
                    "kn-tb-diagnosis-principle",
                    title="肺结核的诊断原则",
                    body="肺结核的诊断是以病原学检查结果为主",
                    evidence="（一）诊断原则 肺结核的诊断是以病原学检查结果为主",
                    heading="第八章 肺结核",
                    artifact_id="art-tb-diagnosis-principle",
                    page=110,
                    order=250,
                ),
            ],
        }

        payload = build_display_contract_payload(normalized_payload)

        classification_groups = [
            node for node in payload["nodes"] if node.get("group", {}).get("topic") == "classification"
        ]
        self.assertEqual(len(classification_groups), 1)
        group = classification_groups[0]
        self.assertEqual(group["display"]["title"], "结核病的分类标准")
        self.assertIn("WS 196", group["display"]["body"])
        item_titles = [item["title"] for item in group["display"]["items"]]
        self.assertEqual(
            item_titles,
            [
                "结核分枝杆菌潜伏感染者",
                "活动性结核病",
            ],
        )
        active_tb = group["display"]["items"][1]
        self.assertEqual(
            [item["title"] for item in active_tb["children"]],
            [
                "按病变部位分类",
                "按病原学检查结果分类",
                "按耐药状况分类",
                "按既往治疗史分类",
            ],
        )
        site_axis = active_tb["children"][0]
        self.assertEqual(
            [item["title"] for item in site_axis["children"]],
            ["原发性肺结核", "血行播散性肺结核"],
        )
        self.assertEqual(payload["nodes"][-1]["display"]["title"], "肺结核的诊断原则")

    def test_classification_group_stops_before_unlisted_following_prose(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part",
            "section_title": "Section",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-class",
                    title="\u6709\u673a\u6eb6\u5242\u7684\u5206\u7c7b",
                    body="\u6309\u5316\u5b66\u7ec4\u6210\uff0c\u6709\u673a\u6eb6\u5242\u53ef\u5206\u4e5d\u7c7b\u3002",
                    evidence="\u6309\u5316\u5b66\u7ec4\u6210\uff0c\u6709\u673a\u6eb6\u5242\u53ef\u5206\u4e5d\u7c7b\u3002",
                    heading="Section",
                    artifact_id="art-class",
                    page=946,
                    order=10,
                ),
                _row(
                    "kn-row",
                    title="\u8102\u80aa\u5f00\u94fe\u70c3\u7c7b",
                    body="\u6b63\u4e59\u70f7\u3001\u6c7d\u6cb9\u3001\u7164\u6cb9\u3002",
                    evidence="1. \u8102\u80aa\u5f00\u94fe\u70c3\u7c7b \u6b63\u4e59\u70f7\u3001\u6c7d\u6cb9\u3001\u7164\u6cb9\u3002",
                    heading="Section",
                    artifact_id="art-row",
                    page=946,
                    order=11,
                ),
                _row(
                    "kn-mechanism",
                    title="\u4e2d\u6bd2\u673a\u5236",
                    body="\u4e0d\u540c\u6709\u673a\u6eb6\u5242\u4e2d\u6bd2\u673a\u5236\u6709\u6240\u5dee\u5f02\u3002",
                    evidence="\u4e0d\u540c\u6709\u673a\u6eb6\u5242\u4e2d\u6bd2\u673a\u5236\u6709\u6240\u5dee\u5f02\u3002",
                    heading="Section",
                    artifact_id="art-mechanism",
                    page=946,
                    order=12,
                ),
            ],
        }

        payload = build_display_contract_payload(normalized_payload)

        self.assertEqual(len(payload["nodes"]), 2)
        group = payload["nodes"][0]
        self.assertEqual(group["render_type"], "grouped")
        self.assertEqual(group["group"]["topic"], "classification")
        self.assertEqual([item["title"] for item in group["display"]["items"]], ["有机溶剂的分类", "脂肪开链烃类"])
        self.assertEqual(payload["nodes"][1]["display"]["title"], "中毒机制")

    def test_grouped_display_items_dedupe_repeated_body_without_dropping_evidence(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part",
            "section_title": "Section",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-class",
                    title="分类",
                    body="分类依据。",
                    evidence="分类依据。",
                    heading="Classification",
                    artifact_id="art-class",
                    page=1,
                    order=0,
                ),
                _row(
                    "kn-a",
                    title="卵睾",
                    body="卵睾",
                    evidence="1. 卵睾",
                    heading="Classification",
                    artifact_id="art-a",
                    page=1,
                    order=1,
                ),
                _row(
                    "kn-b",
                    title="卵睾",
                    body="卵睾",
                    evidence="2. 卵睾",
                    heading="Classification",
                    artifact_id="art-b",
                    page=1,
                    order=2,
                ),
            ],
        }

        payload = build_display_contract_payload(normalized_payload)

        group = payload["nodes"][0]
        self.assertEqual(group["render_type"], "grouped")
        self.assertEqual([item["body"] for item in group["display"]["items"]], ["分类依据。", "卵睾"])
        self.assertEqual(
            [item["artifact_id"] for item in group["evidence_items"]],
            ["art-class", "art-a", "art-b"],
        )

    def test_contiguous_evidence_only_treatment_fragments_render_as_one_original_text_item(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-treatment-a",
                    "item_index": 0,
                    "title": "抗菌药物治疗",
                    "aspect": "治疗",
                    "source_heading": "治疗",
                    "evidence": "抗菌药物治疗 首选青霉素G，",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 10,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-treatment-b",
                    "item_index": 1,
                    "title": "原文证据",
                    "aspect": "治疗",
                    "source_heading": "治疗",
                    "evidence": "轻症病人可用240万U/d，分3次肌内注射。",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 11,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-treatment-c",
                    "item_index": 2,
                    "title": "原文证据",
                    "aspect": "治疗",
                    "source_heading": "治疗",
                    "evidence": "重症者可增至更高剂量。",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 12,
                    "verification_state": "needs_review",
                },
            ],
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        treatment_group = next(node for node in payload["nodes"] if node.get("group", {}).get("topic") == "treatment")
        self.assertEqual(treatment_group["publication_state"], "evidence_only")
        self.assertEqual(treatment_group["display"]["title"], "抗菌药物治疗")
        self.assertEqual(len(treatment_group["display"]["items"]), 1)
        self.assertEqual(
            treatment_group["display"]["items"][0]["body"],
            "抗菌药物治疗 首选青霉素G，轻症病人可用240万U/d，分3次肌内注射。重症者可增至更高剂量。",
        )
        self.assertEqual(
            [item["artifact_id"] for item in treatment_group["evidence_items"]],
            ["art-treatment-a", "art-treatment-b", "art-treatment-c"],
        )

    def test_long_evidence_only_treatment_group_splits_into_readable_original_text_items(self):
        long_fragment = "治疗原文片段" * 45
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": f"art-long-{index}",
                    "item_index": index,
                    "title": "治疗",
                    "aspect": "治疗",
                    "source_heading": "治疗",
                    "evidence": f"{long_fragment}{index}",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": index,
                    "verification_state": "needs_review",
                }
                for index in range(4)
            ],
        }

        payload = build_display_contract_payload(
            self._normalized_payload(),
            candidate_payload=candidate_payload,
        )

        treatment_group = next(node for node in payload["nodes"] if node.get("group", {}).get("topic") == "treatment")
        self.assertEqual(treatment_group["publication_state"], "evidence_only")
        self.assertGreater(len(treatment_group["display"]["items"]), 1)
        self.assertTrue(
            all(len(item["body"]) <= 720 for item in treatment_group["display"]["items"])
        )
        self.assertEqual(len(treatment_group["evidence_items"]), 4)

    def test_contiguous_generic_evidence_only_fragments_render_as_one_original_text_item(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-source-a",
                    "item_index": 0,
                    "title": "原文片段",
                    "aspect": "临床表现",
                    "source_heading": "临床表现",
                    "evidence": "第一段原文，",
                    "page_start": 10,
                    "page_end": 10,
                    "source_order": 20,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-source-b",
                    "item_index": 1,
                    "title": "原文片段",
                    "aspect": "临床表现",
                    "source_heading": "临床表现",
                    "evidence": "接着第二段。",
                    "page_start": 10,
                    "page_end": 10,
                    "source_order": 21,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            {
                "textbook_id": "internal-medicine-10",
                "part_title": "Part",
                "section_title": "Section",
                "source_path": "candidate.json",
                "nodes": [],
            },
            candidate_payload=candidate_payload,
        )

        self.assertEqual(len(payload["nodes"]), 1)
        group = payload["nodes"][0]
        self.assertEqual(group["render_type"], "grouped")
        self.assertEqual(group["publication_state"], "evidence_only")
        self.assertEqual(group["group"]["topic"], "source_evidence")
        self.assertEqual(group["display"]["items"][0]["body"], "第一段原文，接着第二段。")
        self.assertEqual(
            [item["artifact_id"] for item in group["evidence_items"]],
            ["art-source-a", "art-source-b"],
        )

    def test_generic_evidence_only_fragments_do_not_group_across_source_order_gap(self):
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-source-a",
                    "item_index": 0,
                    "title": "原文片段",
                    "aspect": "临床表现",
                    "source_heading": "临床表现",
                    "evidence": "第一段原文。",
                    "page_start": 10,
                    "page_end": 10,
                    "source_order": 20,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-source-b",
                    "item_index": 1,
                    "title": "原文片段",
                    "aspect": "临床表现",
                    "source_heading": "临床表现",
                    "evidence": "隔开后的另一段。",
                    "page_start": 10,
                    "page_end": 10,
                    "source_order": 23,
                    "verification_state": "needs_review",
                },
            ]
        }

        payload = build_display_contract_payload(
            {
                "textbook_id": "internal-medicine-10",
                "part_title": "Part",
                "section_title": "Section",
                "source_path": "candidate.json",
                "nodes": [],
            },
            candidate_payload=candidate_payload,
        )

        self.assertEqual([node["render_type"] for node in payload["nodes"]], ["evidence_only", "evidence_only"])

    def test_repeated_treatment_groups_do_not_merge_across_intervening_content(self):
        normalized_payload = {
            "textbook_id": "internal-medicine-10",
            "part_title": "Part",
            "section_title": "Chapter",
            "source_path": "candidate.json",
            "nodes": [
                _row(
                    "kn-intervening",
                    title="Disease B definition",
                    body="Disease B starts here.",
                    evidence="Disease B starts here.",
                    heading="Disease B",
                    artifact_id="art-intervening",
                    page=83,
                    order=12,
                ),
            ],
        }
        candidate_payload = {
            "candidate_items": [
                {
                    "artifact_id": "art-treatment-a1",
                    "item_index": 0,
                    "title": "\u6cbb\u7597",
                    "aspect": "\u6cbb\u7597",
                    "source_heading": "Disease A",
                    "evidence": "\u6cbb\u7597 Disease A starts.",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 10,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-treatment-a2",
                    "item_index": 1,
                    "title": "\u539f\u6587\u8bc1\u636e",
                    "aspect": "\u6cbb\u7597",
                    "source_heading": "Disease A",
                    "evidence": "Disease A treatment continues.",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 11,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-treatment-b1",
                    "item_index": 2,
                    "title": "\u6cbb\u7597",
                    "aspect": "\u6cbb\u7597",
                    "source_heading": "Disease B",
                    "evidence": "\u6cbb\u7597 Disease B starts.",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 13,
                    "verification_state": "needs_review",
                },
                {
                    "artifact_id": "art-treatment-b2",
                    "item_index": 3,
                    "title": "\u539f\u6587\u8bc1\u636e",
                    "aspect": "\u6cbb\u7597",
                    "source_heading": "Disease B",
                    "evidence": "Disease B treatment continues.",
                    "page_start": 83,
                    "page_end": 83,
                    "source_order": 14,
                    "verification_state": "needs_review",
                },
            ],
        }

        payload = build_display_contract_payload(
            normalized_payload,
            candidate_payload=candidate_payload,
        )

        treatment_groups = [
            node
            for node in payload["nodes"]
            if node.get("group", {}).get("topic") == "treatment"
        ]
        self.assertEqual(len(treatment_groups), 2)
        self.assertEqual(
            [item["artifact_id"] for item in treatment_groups[0]["evidence_items"]],
            ["art-treatment-a1", "art-treatment-a2"],
        )
        self.assertEqual(
            [item["artifact_id"] for item in treatment_groups[1]["evidence_items"]],
            ["art-treatment-b1", "art-treatment-b2"],
        )


if __name__ == "__main__":
    unittest.main()
