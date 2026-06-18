import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[1]
# Avoid shadowing the Supabase Python SDK with the repo's supabase/ directory.
if sys.path[:1] == [""]:
    sys.path.pop(0)
sys.path.insert(0, str(ROOT / "scripts"))

from textbook_pipeline.knowledge_node_adapter import (
    finalize_knowledge_rows,
    is_valid_node_row,
    production_node_id,
    v4_structured_to_knowledge_node,
)
from textbook_identity import INTERNAL_MEDICINE_10
import ingest_knowledge as ingest


class IngestKnowledgeContractTests(unittest.TestCase):
    def test_production_node_id_is_stable(self):
        first = production_node_id(
            "internal-medicine-10",
            "第一篇 呼吸系统疾病",
            "第一章 总论",
            "呼吸生理",
        )
        second = production_node_id(
            "internal-medicine-10",
            "第一篇 呼吸系统疾病",
            "第一章 总论",
            "呼吸生理",
        )
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("kn-"))

    def test_failed_extraction_filter(self):
        self.assertFalse(is_valid_node_row({"title": "Extraction Failed", "content": "x" * 20}))
        self.assertFalse(is_valid_node_row({"title": "", "content": "x" * 20}))
        self.assertFalse(is_valid_node_row({"title": "Valid", "content": "short"}))

    def test_v4_schema_maps_provenance_fields(self):
        row = v4_structured_to_knowledge_node(
            {
                "knowledge_point": {"title": "社区获得性肺炎", "type": "disease"},
                "content": {
                    "definition": {"content": "医院外获得的肺炎感染"},
                    "clinical_manifestations": {"content": "发热、咳嗽"},
                },
                "relations": [],
                "extraction_report": {},
            },
            INTERNAL_MEDICINE_10,
            chapter="第一篇 呼吸系统疾病",
            sub_chapter="第六章 肺部感染性疾病",
            order_num=0,
            provenance={
                "textbook_id": "internal-medicine-10",
                "subject": "内科学",
                "part_title": "第一篇 呼吸系统疾病",
                "section_title": "第六章 肺部感染性疾病",
                "source_pdf": "textbook/内科学（第10版）.pdf",
                "extraction_pipeline_version": "v4",
                "adapter_version": "1.0.0",
                "created_from": "test",
                "content_hash": "abc",
            },
        )
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["subject"], "内科学")
        self.assertEqual(row["book_id"], "internal-medicine-10")
        self.assertIn("provenance", row["source_span"])

    def test_finalize_prefers_manifest_part_over_pdf_heading(self):
        rows = finalize_knowledge_rows(
            [
                {
                    "title": "阻塞性通气功能障碍",
                    "type": "concept",
                    "chapter": "第二篇 呼吸系统疾病",
                    "sub_chapter": "第一章 总论",
                    "content": "阻塞性通气功能障碍患者的残气量增加，肺总量正常或增加。",
                    "structured_sections": [
                        {
                            "title": "要点",
                            "content": "阻塞性通气功能障碍患者的残气量增加，肺总量正常或增加。",
                        }
                    ],
                }
            ],
            INTERNAL_MEDICINE_10,
            provenance={
                "textbook_id": "internal-medicine-10",
                "subject": "内科学",
                "part_title": "第二篇 呼吸系统疾病",
                "section_title": "第一章 总论",
                "source_pdf": "textbook/内科学（第10版）.pdf",
                "extraction_pipeline_version": "v3",
                "adapter_version": "1.0.0",
                "created_from": "test",
                "content_hash": "x",
            },
        )
        self.assertEqual(rows[0]["chapter"], "第二篇 呼吸系统疾病")
        self.assertEqual(rows[0]["knowledge_path"][1], "第二篇 呼吸系统疾病")

    def test_manifest_resume_prefers_failed_section(self):
        manifest = {
            "parts": [
                {
                    "title": "第二篇 呼吸系统疾病",
                    "sections": [
                        {"title": "第一章 总论", "status": "verified"},
                        {"title": "第二章 急性上呼吸道感染和急性气管支气管炎", "status": "failed"},
                        {"title": "第三章 慢性阻塞性肺疾病", "status": "pending"},
                    ],
                }
            ]
        }
        nxt = ingest.next_runnable_section(manifest)
        self.assertIsNotNone(nxt)
        assert nxt is not None
        self.assertEqual(nxt["section_title"], "第二章 急性上呼吸道感染和急性气管支气管炎")

    def test_idempotent_upload_does_not_increase_remote_count(self):
        rows = finalize_knowledge_rows(
            [
                {
                    "title": "肺脓肿",
                    "type": "disease",
                    "chapter": "第二篇 呼吸系统疾病",
                    "sub_chapter": "第七章 肺脓肿",
                    "content": "肺脓肿是由多种病原微生物引起的肺组织化脓性病变。",
                    "structured_sections": [
                        {
                            "title": "定义",
                            "content": "肺脓肿是由多种病原微生物引起的肺组织化脓性病变。",
                        }
                    ],
                }
            ],
            INTERNAL_MEDICINE_10,
        )
        part = "第二篇 呼吸系统疾病"
        section = "第七章 肺脓肿"

        remote_state = {"count": 0, "ids": []}

        def fake_remote(_part: str, _section: str):
            return remote_state["count"], list(remote_state["ids"])

        def fake_upsert(upload_rows):
            remote_state["ids"] = [row["id"] for row in upload_rows]
            remote_state["count"] = len(remote_state["ids"])
            return len(upload_rows)

        def fake_artifacts(*_args, **_kwargs):
            return {"chunks": 1, "embedded": 0, "causal_chains": 0, "node_ids": len(rows)}

        with patch.object(ingest, "remote_nodes_for_section", side_effect=fake_remote):
            with patch.object(ingest, "upsert_knowledge_nodes", side_effect=fake_upsert):
                with patch.object(ingest, "upload_section_artifacts", side_effect=fake_artifacts):
                    first = ingest.upload_rows_idempotent(rows, part, section)
                    second = ingest.upload_rows_idempotent(rows, part, section)

        self.assertEqual(first["after_count"], len(rows))
        self.assertEqual(second["after_count"], len(rows))
        self.assertEqual(second["delta"], 0)
        self.assertTrue(second["idempotent"])

    def test_manifest_status_only_after_upload_verify(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest_path = Path(tmp) / "manifest.yaml"
            manifest = {
                "parts": [
                    {
                        "title": "第一篇 呼吸系统疾病",
                        "sections": [{"title": "第一章 总论", "status": "pending"}],
                    }
                ]
            }
            manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True), encoding="utf-8")

            with patch.object(ingest, "MANIFEST_PATH", manifest_path):
                ingest.set_section_status(
                    manifest,
                    "第一篇 呼吸系统疾病",
                    "第一章 总论",
                    "uploaded",
                    node_count=3,
                    remote_count=3,
                )
                reloaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                status = reloaded["parts"][0]["sections"][0]["status"]
                self.assertEqual(status, "uploaded")
                self.assertNotEqual(status, "verified")

    def test_record_performance_keeps_bounded_history(self):
        state = {}
        for index in range(25):
            ingest.record_performance(
                state,
                part_title="第四篇 消化系统疾病",
                section_title=f"第{index}章",
                stage="extract",
                timings={"total": float(index)},
            )

        perf = state["performance"]
        self.assertEqual(perf["last_section"]["section"], "第四篇 消化系统疾病/第24章")
        self.assertEqual(len(perf["history"]), 20)
        self.assertEqual(perf["history"][0]["section"], "第四篇 消化系统疾病/第5章")


if __name__ == "__main__":
    unittest.main()
