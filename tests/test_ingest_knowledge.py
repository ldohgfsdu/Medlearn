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
from textbook_pipeline.evidence_artifact import make_artifact
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

    def test_ev1_app_bundle_roots_are_canonical(self):
        ingest.configure_ingestion("internal-medicine-10")

        self.assertEqual(ingest.EV1_NORMALIZED_ROOT, ingest.GENERATED_ROOT)
        self.assertEqual(
            ingest.EV1_DISPLAY_CONTRACT_ROOT,
            ROOT / "generated" / "display_contracts",
        )

    def test_ev1_normalized_cache_paths_skip_legacy_v3_caches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ev1_path = root / "ev1.normalized.json"
            v3_path = root / "v3.normalized.json"
            ev1_path.write_text(
                json.dumps({"pipeline_version": ingest.EV1_NORMALIZED_PIPELINE_VERSION}),
                encoding="utf-8",
            )
            v3_path.write_text(
                json.dumps({"pipeline_version": "v3"}),
                encoding="utf-8",
            )

            ev1_paths, skipped_paths = ingest.ev1_normalized_cache_paths(root)

        self.assertEqual(ev1_paths, [ev1_path])
        self.assertEqual(skipped_paths, [v3_path])

    def test_ev1_registry_loads_pipeline_v3_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            registry_path = (
                project_root
                / "generated"
                / "pipeline_v3"
                / "evidence_candidates"
                / "internal-medicine-10"
                / "_registry.json"
            )
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text(
                json.dumps({"version": "ev1-registry-0.1.0", "sections": {"demo": {}}}),
                encoding="utf-8",
            )

            with patch.object(ingest, "PROJECT_ROOT", project_root):
                registry = ingest._load_ev1_registry()

        self.assertEqual(registry["sections"], {"demo": {}})

    def test_ev1_candidate_cache_path_defaults_to_pipeline_v3(self):
        with patch.object(ingest, "PROJECT_ROOT", ROOT):
            candidate_path = ingest._ev1_candidate_cache_path("part", "section")

        self.assertEqual(
            candidate_path.relative_to(ROOT).parts[:3],
            ("generated", "pipeline_v3", "evidence_candidates"),
        )

    def test_ev1_candidate_resolver_maps_legacy_registry_path_to_pipeline_v3_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_root = Path(tmp)
            candidate_rel = Path(
                "generated",
                "pipeline_v3",
                "evidence_candidates",
                "internal-medicine-10",
                "part__section.candidate.json",
            )
            candidate_path = project_root / candidate_rel
            candidate_path.parent.mkdir(parents=True)
            candidate_path.write_text("{}", encoding="utf-8")

            entry = {
                "part_title": "part",
                "section_title": "section",
                "output_path": str(
                    Path(
                        "generated",
                        "evidence_candidates",
                        "internal-medicine-10",
                        "part__section.candidate.json",
                    )
                ),
            }
            with patch.object(ingest, "PROJECT_ROOT", project_root):
                resolved = ingest._resolve_ev1_candidate_path(entry)

        self.assertEqual(resolved, candidate_path)

    def test_ev1_reverify_candidates_parser_supports_local_cache_reverification(self):
        parser = ingest.build_parser()

        args = parser.parse_args([
            "ev1-reverify-candidates",
            "--part",
            "第二篇 呼吸系统疾病",
            "--limit",
            "1",
            "--write-normalized-cache",
        ])

        self.assertEqual(args.command, "ev1-reverify-candidates")
        self.assertEqual(args.part, "第二篇 呼吸系统疾病")
        self.assertEqual(args.limit, 1)
        self.assertTrue(args.write_normalized_cache)

    def test_ev1_candidate_quality_report_parser_supports_strict_gate(self):
        parser = ingest.build_parser()

        args = parser.parse_args([
            "ev1-candidate-quality-report",
            "--min-coverage",
            "0.99",
            "--max-rejected-rate",
            "0",
            "--diagnostic-sample-limit",
            "2",
            "--diagnostic-items-output",
            "generated/queue.json",
            "--strict",
        ])

        self.assertEqual(args.command, "ev1-candidate-quality-report")
        self.assertEqual(args.min_coverage, 0.99)
        self.assertEqual(args.max_rejected_rate, 0)
        self.assertEqual(args.diagnostic_sample_limit, 2)
        self.assertEqual(args.diagnostic_items_output, "generated/queue.json")
        self.assertTrue(args.strict)

    def test_ev1_display_quality_report_parser_supports_strict_gate(self):
        parser = ingest.build_parser()

        args = parser.parse_args([
            "ev1-display-quality-report",
            "--section",
            "Section",
            "--sample-limit",
            "2",
            "--output",
            "generated/display-quality.json",
            "--strict",
        ])

        self.assertEqual(args.command, "ev1-display-quality-report")
        self.assertEqual(args.section, "Section")
        self.assertEqual(args.sample_limit, 2)
        self.assertEqual(args.output, "generated/display-quality.json")
        self.assertTrue(args.strict)

    def test_ev1_remediate_quality_queue_parser_defaults_to_dry_run(self):
        parser = ingest.build_parser()

        args = parser.parse_args([
            "ev1-remediate-quality-queue",
            "--queue",
            "generated/queue.json",
            "--limit-sections",
            "2",
        ])

        self.assertEqual(args.command, "ev1-remediate-quality-queue")
        self.assertEqual(args.queue, "generated/queue.json")
        self.assertEqual(args.recommended_action, "rerun_synthesis_with_strict_gate")
        self.assertEqual(args.limit_sections, 2)
        self.assertFalse(args.execute)

    def test_ev1_quality_remediation_targets_group_by_section_and_artifact(self):
        queue = {
            "items": [
                {
                    "part_title": "Part A",
                    "section_title": "Section 1",
                    "artifact_id": "a1",
                    "title": "First",
                    "recommended_action": "rerun_synthesis_with_strict_gate",
                },
                {
                    "part_title": "Part A",
                    "section_title": "Section 1",
                    "artifact_id": "a1",
                    "title": "Second",
                    "recommended_action": "rerun_synthesis_with_strict_gate",
                },
                {
                    "part_title": "Part B",
                    "section_title": "Section 2",
                    "artifact_id": "b1",
                    "title": "Repair",
                    "recommended_action": "repair_span_then_keep_evidence_only",
                },
                {
                    "part_title": "Part C",
                    "section_title": "Section 3",
                    "artifact_id": "c1",
                    "title": "Third",
                    "recommended_action": "rerun_synthesis_with_strict_gate",
                },
            ]
        }

        targets = ingest._ev1_quality_remediation_targets(queue)

        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]["part_title"], "Part A")
        self.assertEqual(targets[0]["section_title"], "Section 1")
        self.assertEqual(targets[0]["artifact_ids"], ["a1"])
        self.assertEqual(targets[0]["item_count"], 2)
        self.assertEqual(targets[0]["sample_titles"], ["First", "Second"])

    def test_ev1_candidate_quality_summary_surfaces_blockers_and_issue_types(self):
        payload = {
            "part_title": "Part",
            "section_title": "Section",
            "candidate_status": "needs_pipeline_review",
            "coverage": {
                "artifacts_with_items": 9,
                "artifacts_without_items": 1,
                "coverage_rate": 0.9,
            },
            "candidate_items": [
                {
                    "verification_state": "pass",
                    "risk_class": "standard",
                    "verification_notes": [
                        "evidence_substring: loose match (punctuation normalized)",
                        "evidence_content_span: evidence expanded to continuous content span",
                    ],
                },
                {
                    "verification_state": "needs_review",
                    "risk_class": "standard",
                    "verification_notes": [
                        "content_evidence_ratio: low overlap (20%), content may exceed evidence"
                    ],
                },
                {
                    "verification_state": "rejected",
                    "risk_class": "standard",
                    "verification_notes": ["evidence_substring: evidence not found"],
                },
            ],
        }

        report = ingest.summarize_ev1_candidate_quality(
            [(None, payload)],
            min_coverage=0.95,
            max_rejected_rate=0.0,
        )

        self.assertFalse(report["summary"]["passed"])
        self.assertEqual(report["summary"]["verification_counts"]["rejected"], 1)
        self.assertEqual(report["summary"]["issue_type_counts"]["content_evidence_ratio"], 1)
        self.assertEqual(report["summary"]["issue_type_counts"]["evidence_substring"], 1)
        self.assertEqual(report["summary"]["repair_counts"]["evidence_substring"], 1)
        self.assertEqual(report["summary"]["repair_counts"]["evidence_content_span"], 1)
        self.assertEqual(
            report["sections"][0]["blockers"],
            ["coverage_below_threshold", "rejected_rate_above_threshold"],
        )
        diagnostics = report["needs_review_diagnostics"]
        self.assertEqual(diagnostics["quality_defect_counts"]["standard_candidate_extraction_noise"], 1)
        self.assertEqual(diagnostics["quality_defect_counts"]["source_binding_blocker"], 1)
        self.assertEqual(diagnostics["quality_defect_total"], 2)
        self.assertIn("rerun_synthesis_with_strict_gate", diagnostics["recommended_action_counts"])

    def test_ev1_candidate_review_diagnostics_separates_design_hidden_from_defects(self):
        payload = {
            "part_title": "Part",
            "section_title": "Section",
            "candidate_status": "needs_pipeline_review",
            "coverage": {"coverage_rate": 1.0},
            "candidate_items": [
                {
                    "verification_state": "needs_review",
                    "risk_class": "needs_review",
                    "title": "Dose",
                    "content": "drug dose",
                    "evidence": "drug dose",
                    "verification_notes": [],
                },
                {
                    "verification_state": "needs_review",
                    "risk_class": "needs_review",
                    "title": "Noisy Dose",
                    "content": "drug dose with inferred route",
                    "evidence": "drug dose",
                    "verification_notes": ["content_evidence_ratio: 0.42"],
                },
                {
                    "verification_state": "needs_review",
                    "risk_class": "needs_review",
                    "title": "Source",
                    "content": "source text",
                    "evidence": "source text",
                    "verification_notes": ["source_only_fallback_no_synthesized_item"],
                },
                {
                    "verification_state": "needs_review",
                    "risk_class": "standard",
                    "title": "Compressed",
                    "content": "source text plus inferred title",
                    "evidence": "source text",
                    "verification_notes": ["unsupported_terms: 4 CJK chars in content not in evidence"],
                },
            ],
        }

        diagnostics = ingest.summarize_ev1_candidate_review_diagnostics(
            [(None, payload)],
            sample_limit=1,
        )

        self.assertEqual(diagnostics["review_class_counts"]["high_risk_grounded_source_only"], 1)
        self.assertEqual(diagnostics["review_class_counts"]["high_risk_with_extraction_noise"], 1)
        self.assertEqual(diagnostics["review_class_counts"]["source_only_fallback"], 1)
        self.assertEqual(diagnostics["review_class_counts"]["standard_candidate_extraction_noise"], 1)
        self.assertEqual(diagnostics["quality_defect_total"], 2)
        self.assertEqual(
            diagnostics["recommended_action_counts"]["keep_evidence_only"],
            1,
        )
        self.assertEqual(
            diagnostics["recommended_action_counts"]["rerun_synthesis_with_strict_gate"],
            2,
        )
        self.assertEqual(
            diagnostics["samples_by_class"]["standard_candidate_extraction_noise"][0]["title"],
            "Compressed",
        )

        queue = ingest.build_ev1_candidate_quality_defect_queue([(None, payload)])
        self.assertEqual(queue["total_items"], 2)
        self.assertEqual([item["title"] for item in queue["items"]], ["Noisy Dose", "Compressed"])
        self.assertEqual(
            queue["recommended_action_counts"],
            {"rerun_synthesis_with_strict_gate": 2},
        )

    def test_ev1_candidate_review_diagnostics_separates_repairable_span_from_rerun(self):
        standard_item = {
            "verification_state": "needs_review",
            "risk_class": "standard",
            "title": "Repairable",
            "content": "source sentence in nearby text",
            "evidence": "source sentence",
            "verification_notes": ["unsupported_terms: nearby text"],
        }
        high_risk_item = {
            "verification_state": "needs_review",
            "risk_class": "needs_review",
            "title": "Repairable high risk",
            "content": "high risk source sentence",
            "evidence": "source sentence",
            "verification_notes": ["content_evidence_ratio: 0.4"],
        }
        source_context = "prefix source sentence in nearby text suffix high risk source sentence"

        self.assertEqual(
            ingest._ev1_candidate_review_class(standard_item, source_context),
            ("standard_candidate_repairable_span", "repair_span_from_source_context"),
        )
        self.assertEqual(
            ingest._ev1_candidate_review_class(high_risk_item, source_context),
            ("high_risk_repairable_span_binding", "repair_span_then_keep_evidence_only"),
        )

    def test_ev1_candidate_review_diagnostics_does_not_repair_title_only_content(self):
        item = {
            "verification_state": "needs_review",
            "risk_class": "standard",
            "title": "CAR-T细胞免疫疗法在血液病中的应用",
            "content": "CAR-T 细胞免疫疗法在血 液病中的应用",
            "evidence": "unrelated table row",
            "verification_notes": ["content_evidence_ratio: 0.0"],
        }

        self.assertEqual(
            ingest._ev1_candidate_review_class(
                item,
                "CAR-T 细胞免疫疗法在血 液病中的应用",
            ),
            ("standard_candidate_extraction_noise", "rerun_synthesis_with_strict_gate"),
        )

    def test_ev1_display_quality_summary_catches_blockers_without_spacing_false_positive(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n1",
                                "render_type": "evidence",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "CO中毒",
                                    "page_label": "p.1",
                                },
                                "evidence_items": [
                                    {
                                        "artifact_id": "a1",
                                        "text": "CO 中毒可见于相关原文片段。",
                                    }
                                ],
                            },
                            {
                                "id": "n2",
                                "render_type": "organized",
                                "publication_state": "published",
                                "display": {"title": "", "page_label": ""},
                                "evidence_items": [],
                            },
                            {
                                "id": "n3",
                                "render_type": "grouped",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "治疗",
                                    "page_label": "p.2",
                                    "items": [
                                        {
                                            "title": "原文证据",
                                            "body": "具体药物相关原文片段。",
                                            "page_label": "p.2",
                                        }
                                    ],
                                },
                                "evidence_items": [
                                    {
                                        "artifact_id": "a2",
                                        "text": "具体药物相关原文片段。",
                                    }
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        self.assertEqual(report["contracts"], 1)
        self.assertEqual(report["nodes"], 3)
        self.assertEqual(report["warning_total"], 0)
        self.assertEqual(report["issue_counts"]["empty_title"], 1)
        self.assertEqual(report["issue_counts"]["missing_page_label"], 1)
        self.assertEqual(report["issue_counts"]["missing_evidence_items"], 1)
        self.assertEqual(report["issue_counts"]["organized_empty_body_and_items"], 1)
        self.assertFalse(report["passed"])

    def test_ev1_display_quality_summary_rejects_control_characters_in_display_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n-control",
                                "render_type": "evidence_only",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "原文证据",
                                    "page_label": "p.1",
                                    "source_heading": "第四章 \x07动脉粥样硬化",
                                },
                                "evidence_items": [
                                    {
                                        "artifact_id": "a-control",
                                        "text": "冠脉CTA 有较高阴性预测价值。",
                                    }
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        self.assertEqual(report["issue_counts"]["display_control_characters"], 1)
        self.assertFalse(report["passed"])

    def test_ev1_display_quality_summary_rejects_invalid_page_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n-page-label",
                                "render_type": "evidence_only",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "原文证据",
                                    "page_label": "pp.10-11",
                                },
                                "evidence_items": [
                                    {
                                        "artifact_id": "a-page-label",
                                        "text": "连续原文证据。",
                                    }
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        self.assertEqual(report["issue_counts"]["invalid_page_label"], 1)
        self.assertFalse(report["passed"])

    def test_ev1_display_quality_summary_rejects_duplicate_group_items(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n-group",
                                "render_type": "grouped",
                                "publication_state": "organized",
                                "display": {
                                    "title": "分类",
                                    "page_label": "p.1",
                                    "items": [
                                        {"title": "卵睾", "body": "卵睾"},
                                        {"title": "卵睾", "body": "卵睾"},
                                    ],
                                },
                                "evidence_items": [
                                    {
                                        "artifact_id": "a1",
                                        "text": "卵睾",
                                    }
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        self.assertEqual(report["issue_counts"]["duplicate_group_display_item"], 1)
        self.assertFalse(report["passed"])

    def test_ev1_display_quality_summary_rejects_source_evidence_order_jump(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n-source-evidence",
                                "render_type": "grouped",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "原文证据",
                                    "page_label": "p.1",
                                    "items": [
                                        {"title": "原文证据", "body": "第一段。第二段。"},
                                    ],
                                },
                                "group": {"topic": "source_evidence"},
                                "evidence_items": [
                                    {
                                        "artifact_id": "a1",
                                        "text": "第一段。",
                                        "source_order": 10,
                                    },
                                    {
                                        "artifact_id": "a2",
                                        "text": "第二段。",
                                        "source_order": 13,
                                    },
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        self.assertEqual(report["issue_counts"]["source_evidence_group_order_jump"], 1)
        self.assertFalse(report["passed"])

    def test_ev1_display_quality_summary_rejects_overlong_group_item_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n-long-item",
                                "render_type": "grouped",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "原文证据",
                                    "page_label": "p.1",
                                    "items": [
                                        {"title": "原文证据", "body": "原文" * 400},
                                    ],
                                },
                                "group": {"topic": "source_evidence"},
                                "evidence_items": [
                                    {
                                        "artifact_id": "a1",
                                        "text": "原文",
                                        "source_order": 1,
                                    },
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        self.assertEqual(report["issue_counts"]["group_display_item_too_long"], 1)
        self.assertFalse(report["passed"])

    def test_ev1_display_quality_summary_reports_readability_metrics(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.display_contract.json"
            path.write_text(
                json.dumps(
                    {
                        "nodes": [
                            {
                                "id": "n-source-evidence",
                                "render_type": "grouped",
                                "publication_state": "evidence_only",
                                "display": {
                                    "title": "原文证据",
                                    "page_label": "p.1",
                                    "items": [
                                        {"title": "原文证据", "body": "第一段。第二段。"},
                                    ],
                                },
                                "group": {"topic": "source_evidence"},
                                "evidence_items": [
                                    {
                                        "artifact_id": "a1",
                                        "text": "第一段。",
                                        "source_order": 10,
                                    },
                                    {
                                        "artifact_id": "a2",
                                        "text": "第二段。",
                                        "source_order": 11,
                                    },
                                ],
                            },
                            {
                                "id": "n-evidence-a",
                                "render_type": "evidence_only",
                                "publication_state": "evidence_only",
                                "display": {"title": "原文证据", "page_label": "p.2"},
                                "evidence_items": [
                                    {"artifact_id": "a3", "text": "第三段。", "source_order": 20}
                                ],
                            },
                            {
                                "id": "n-evidence-b",
                                "render_type": "evidence_only",
                                "publication_state": "evidence_only",
                                "display": {"title": "原文证据", "page_label": "p.2"},
                                "evidence_items": [
                                    {"artifact_id": "a4", "text": "第四段。", "source_order": 21}
                                ],
                            },
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            report = ingest.summarize_ev1_display_contract_quality([path])

        readability = report["readability"]
        self.assertEqual(readability["source_evidence_group_count"], 1)
        self.assertEqual(readability["source_evidence_group_evidence_items"], 2)
        self.assertEqual(readability["source_evidence_group_display_items"], 1)
        self.assertEqual(readability["max_source_evidence_group_evidence_items"], 2)
        self.assertEqual(readability["remaining_evidence_only_run_count"], 1)
        self.assertEqual(readability["remaining_evidence_only_run_nodes"], 2)
        self.assertEqual(readability["max_remaining_evidence_only_run_length"], 2)
        self.assertGreater(readability["max_group_display_item_body_chars"], 0)
        self.assertTrue(report["passed"])

    def test_ev1_source_only_fallback_covers_unitemized_text_artifacts(self):
        artifact = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第五章 支气管扩张症",
            source_heading="第五章\n支气管扩张症",
            normalized_aspect=None,
            source_order=1,
            artifact_type="text_block",
            raw_text="特征常可作出明确的鉴别诊断。下述要点对鉴别诊断有一定参考意义。",
            page_start=75,
            page_end=75,
        )
        header = make_artifact(
            textbook_id="internal-medicine-10",
            book_id="internal-medicine-10",
            part_title="第二篇 呼吸系统疾病",
            section_title="第五章 支气管扩张症",
            source_heading="第五章\n支气管扩张症",
            normalized_aspect=None,
            source_order=2,
            artifact_type="text_block",
            raw_text="第五章 支气管扩张症",
            page_start=75,
            page_end=75,
        )
        items = []

        added = ingest._append_ev1_source_only_fallback_items(
            items,
            [artifact, header],
            section_title="第五章 支气管扩张症",
        )

        self.assertEqual(added, 1)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].artifact_id, artifact.id)
        self.assertEqual(items[0].title, "原文证据片段")
        self.assertEqual(items[0].risk_class, "needs_review")
        self.assertEqual(items[0].evidence, artifact.raw_text)

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
