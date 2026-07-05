# MedLearn PDF 知识点管线索引

## 生产入口（唯一）

| 组件 | 路径 |
|------|------|
| CLI | [`scripts/ingest_knowledge.py`](../scripts/ingest_knowledge.py) |
| 编排 | [`scripts/orchestrator.py`](../scripts/orchestrator.py) |
| V3 核心 | [`scripts/pipeline_v3_extract.py`](../scripts/pipeline_v3_extract.py) |
| 契约 | [`scripts/textbook_pipeline/ingestion_contract.py`](../scripts/textbook_pipeline/ingestion_contract.py) |
| Manifest | [`manifests/internal_medicine_ingestion.yaml`](../manifests/internal_medicine_ingestion.yaml) |

```powershell
cd F:\ml
python scripts\ingest_knowledge.py --book-id internal-medicine-10 status
python scripts\orchestrator.py run-next
python scripts\ingest_knowledge.py backfill-p0
python scripts\verify_pipeline_closure.py
```

## 写入目标

- `knowledge_nodes` — 知识点主表
- `document_chunks` — RAG 引用（`related_node_id`）
- `causal_chains` — 章节级因果链（`source=pipeline_v3`）

## 遗留 / 实验脚本（勿用于生产）

| 脚本 | 状态 | 替代 |
|------|------|------|
| `scripts/ingest_final.py` | DEPRECATED | `ingest_knowledge.py` |
| `scripts/run_optimized_pipeline.py` | EXPERIMENTAL | `ingest_knowledge.py extract` |
| `scripts/textbook_parser.py` | DEMO ONLY | `pipeline_v3_extract.py` |
| V2 `segment_by_catalog` 等 | SUPERSEDED | V3 manifest 流程 |

## 默认配置

- PDF 解析：`auto`（普通页 PyMuPDF、复杂页 Docling、扫描页 OCR）
- Embedding：`bge-m3` via Ollama（`OLLAMA_EMBED_MODEL`）
- 覆盖解析器：`MEDLEARN_PDF_PARSER=auto|pymupdf|docling` 或 CLI `--pdf-parser`
