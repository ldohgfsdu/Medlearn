import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "pipeline_v3_extract.py"
SPEC = importlib.util.spec_from_file_location("pipeline_v3_extract", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class AtomicNodeTests(unittest.TestCase):
    def test_recovers_named_pneumonia_from_grounded_definition(self) -> None:
        source = (
            "一、肺炎链球菌肺炎\n"
            "肺炎链球菌肺炎（Streptococcal pneumonia）是由肺炎链球菌引起的肺炎。"
        )
        self.assertEqual(
            MODULE.recover_explicit_disease_entity("细菌性肺炎", source),
            "肺炎链球菌肺炎",
        )

    def test_catalog_page_range_uses_deepest_matching_heading(self) -> None:
        page_start, page_end = MODULE.resolve_catalog_page_range(
            [
                {
                    "headings": ["第二篇 呼吸系统疾病", "第六章 肺部感染性疾病"],
                    "page_start": 77,
                    "page_end": 98,
                },
                {
                    "headings": [
                        "第二篇 呼吸系统疾病",
                        "第六章 肺部感染性疾病",
                        "第二节 | 细菌性肺炎",
                    ],
                    "page_start": 81,
                    "page_end": 83,
                },
            ],
            [
                "第二篇 呼吸系统疾病",
                "第六章 肺部感染性疾病",
                "第二节 | 细菌性肺炎",
            ],
        )
        self.assertEqual((page_start, page_end), (81, 83))

    def test_title_declares_entity_with_aspect_suffix(self) -> None:
        self.assertTrue(
            MODULE.title_declares_entity("支气管哮喘的临床表现", "支气管哮喘")
        )

    def test_entity_confirmed_via_evidence_when_content_uses_abbreviation(self) -> None:
        result = MODULE.identify_node_entity(
            "慢性血栓栓塞性肺疾病",
            "肺动脉内反复血栓栓塞，以及栓塞后血栓不溶、机化。",
            "定义",
            "称为慢性血栓栓塞性肺疾病（CTEPD）。",
        )
        self.assertEqual(result.entity, "慢性血栓栓塞性肺疾病")

    def test_is_atomic_accepts_parent_in_title_and_evidence(self) -> None:
        accepted = MODULE.MedlearnPipeline.is_atomic_node(
            "支气管哮喘的临床表现",
            "表现为发作性伴有哮鸣音的呼气性呼吸困难。",
            "支气管哮喘",
            "临床表现",
            "哮喘发作时双肺可闻及广泛的哮鸣音。",
            None,
        )
        self.assertTrue(accepted)

    def test_is_atomic_rejects_context_dependent_opening(self) -> None:
        rejected = MODULE.MedlearnPipeline.is_atomic_node(
            "该病的主要表现",
            "该病的主要表现为反复咳嗽。",
            "支气管哮喘",
            "临床表现",
            "哮喘的主要表现为反复咳嗽。",
            None,
        )
        self.assertFalse(rejected)

    def test_build_rows_keeps_title_declared_entity(self) -> None:
        pipeline = MODULE.MedlearnPipeline(
            source_path=Path("textbook/内科学（第10版）.pdf"),
            output_dir=Path("generated/pipeline_v3"),
            model="medlearn-qwen3:8b",
            ollama_url="http://127.0.0.1:11434",
            max_chars=2800,
            num_ctx=4096,
            limit=None,
            subject="内科学（第10版）",
            section_limit=1,
            section_start=0,
            pymupdf_only=True,
        )
        cache = {
            "chunks": {
                "0": {
                    "headings": ["第二篇 呼吸系统疾病", "第十一章 肺血栓栓塞症"],
                    "content": "称为慢性血栓栓塞性肺疾病（CTEPD）。肺动脉内反复血栓栓塞，以及栓塞后血栓不溶、机化。",
                    "nodes": [
                        {
                            "title": "慢性血栓栓塞性肺疾病",
                            "type": "disease",
                            "parent_entity": "慢性血栓栓塞性肺疾病",
                            "aspect": "定义",
                            "content": "肺动脉内反复血栓栓塞，以及栓塞后血栓不溶、机化，导致血管慢性化机械阻塞。",
                            "evidence": "称为慢性血栓栓塞性肺疾病（CTEPD）。",
                            "tags": [],
                        }
                    ],
                    "edges": [],
                }
            }
        }
        rows = pipeline.build_rows(cache)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "慢性血栓栓塞性肺疾病的定义")

    def test_build_rows_merges_same_parent_and_aspect_into_numbered_items(self) -> None:
        pipeline = MODULE.MedlearnPipeline(
            source_path=Path("textbook/内科学（第10版）.pdf"),
            output_dir=Path("generated/pipeline_v3"),
            model="medlearn-qwen3:8b",
            ollama_url="http://127.0.0.1:11434",
            max_chars=2800,
            num_ctx=4096,
            limit=None,
            subject="内科学（第10版）",
            section_limit=1,
            section_start=0,
            pymupdf_only=True,
        )
        source = (
            "高血压治疗包括ACEI类药物，可抑制肾素-血管紧张素系统。"
            "高血压治疗也可使用利尿剂，通过促进钠水排泄降低血压。"
        )
        cache = {
            "chunks": {
                "0": {
                    "headings": ["第三篇 循环系统疾病", "第五章 高血压"],
                    "content": source,
                    "nodes": [
                        {
                            "title": "高血压的ACEI类药物",
                            "type": "treatment",
                            "parent_entity": "高血压",
                            "aspect": "治疗方案",
                            "content": "高血压可使用ACEI类药物抑制肾素-血管紧张素系统。",
                            "evidence": "高血压治疗包括ACEI类药物，可抑制肾素-血管紧张素系统。",
                            "tags": [],
                        },
                        {
                            "title": "高血压的利尿剂",
                            "type": "treatment",
                            "parent_entity": "高血压",
                            "aspect": "个体化治疗方案",
                            "content": "高血压可使用利尿剂促进钠水排泄降低血压。",
                            "evidence": "高血压治疗也可使用利尿剂，通过促进钠水排泄降低血压。",
                            "tags": [],
                        },
                    ],
                    "edges": [],
                }
            }
        }

        rows = pipeline.build_rows(cache)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["title"], "高血压的治疗")
        self.assertEqual(rows[0]["source_span"]["aspect"], "治疗")
        self.assertEqual(rows[0]["source_span"]["raw_aspect"], "治疗方案")
        self.assertEqual(len(rows[0]["structured_sections"]), 2)
        self.assertIn("1. 高血压的ACEI类药物", rows[0]["content"])
        self.assertIn("2. 高血压的利尿剂", rows[0]["content"])


    def test_extract_json_repairs_trailing_commas(self) -> None:
        payload = MODULE.extract_json(
            '{"nodes":[{"title":"高血压的定义","type":"disease","parent_entity":"高血压",'
            '"aspect":"定义","content":"高血压是...","evidence":"高血压定义为...",},],}'
        )
        self.assertEqual(len(payload["nodes"]), 1)

    def test_persist_chunk_result_maintains_insertion_order(self) -> None:
        """Cache chunk keys must stay in insertion order regardless of processing order."""
        pipeline = MODULE.MedlearnPipeline(
            source_path=Path("textbook/内科学（第10版）.pdf"),
            output_dir=Path("generated/pipeline_v3"),
            model="medlearn-qwen3:8b",
            ollama_url="http://127.0.0.1:11434",
            max_chars=2800,
            num_ctx=4096,
            limit=None,
            subject="内科学（第10版）",
            section_limit=1,
            section_start=0,
            pymupdf_only=True,
        )
        cache: dict = {"subject": "test", "chunks": {}}

        # Simulate out-of-order persistence (chunk 2 before chunk 0)
        chunks_data = [
            (MODULE.MarkdownChunk(0, ["h1"], "content 0"), {"nodes": [{"title": "n0"}], "edges": []}),
            (MODULE.MarkdownChunk(2, ["h1"], "content 2"), {"nodes": [{"title": "n2"}], "edges": []}),
            (MODULE.MarkdownChunk(1, ["h1"], "content 1"), {"nodes": [{"title": "n1"}], "edges": []}),
        ]
        for chunk, data in chunks_data:
            pipeline._persist_chunk_result(cache, chunk, data)

        keys = list(cache["chunks"].keys())
        # Insertion order must be preserved: "0", "2", "1"
        self.assertEqual(keys, ["0", "2", "1"])
        self.assertEqual(cache["chunks"]["0"]["nodes"][0]["title"], "n0")
        self.assertEqual(cache["chunks"]["2"]["nodes"][0]["title"], "n2")
        self.assertEqual(cache["chunks"]["1"]["nodes"][0]["title"], "n1")

    def test_extract_concurrent_persists_in_chunk_order(self) -> None:
        """With OLLAMA_CONCURRENCY > 1, cache keys must match chunk order not completion order."""
        import os
        import time
        import threading

        pipeline = MODULE.MedlearnPipeline(
            source_path=Path("textbook/内科学（第10版）.pdf"),
            output_dir=Path("generated/pipeline_v3"),
            model="medlearn-qwen3:8b",
            ollama_url="http://127.0.0.1:11434",
            max_chars=2800,
            num_ctx=4096,
            limit=None,
            subject="内科学（第10版）",
            section_limit=1,
            section_start=0,
            pymupdf_only=True,
        )

        chunks = [
            MODULE.MarkdownChunk(0, ["h1"], "content 0"),
            MODULE.MarkdownChunk(1, ["h1"], "content 1"),
            MODULE.MarkdownChunk(2, ["h1"], "content 2"),
        ]

        # Track call order to verify concurrency actually happened
        call_order = []
        call_order_lock = threading.Lock()

        def fake_call_ollama(chunk, retries=3):
            """Chunk 2 returns first, chunk 0 last — reversed completion order."""
            delay = {2: 0.01, 1: 0.05, 0: 0.1}.get(chunk.index, 0.01)
            time.sleep(delay)
            with call_order_lock:
                call_order.append(chunk.index)
            return {"nodes": [{"title": f"n{chunk.index}"}], "edges": []}

        pipeline.call_ollama = fake_call_ollama

        old_val = os.environ.get("OLLAMA_CONCURRENCY")
        try:
            os.environ["OLLAMA_CONCURRENCY"] = "3"
            cache = pipeline.extract(chunks, resume=False)
        finally:
            if old_val is None:
                os.environ.pop("OLLAMA_CONCURRENCY", None)
            else:
                os.environ["OLLAMA_CONCURRENCY"] = old_val

        # Completion order should be reversed (2, 1, 0)
        self.assertEqual(call_order, [2, 1, 0])
        # But cache keys must be in chunk index order (0, 1, 2)
        keys = list(cache["chunks"].keys())
        self.assertEqual(keys, ["0", "1", "2"])


if __name__ == "__main__":
    unittest.main()
