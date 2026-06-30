# Medlearn PDF 知识点提取指南（V3 生产）

**版本**: 3.0  
**日期**: 2026-06-14  
**生产入口**: [`scripts/ingest_knowledge.py`](../scripts/ingest_knowledge.py)

## 流程

```text
PDF 目录/版面推断 → 自适应页面解析（PyMuPDF/Docling/OCR）→ 结构化分块 → Ollama medlearn-qwen3:8b
  → knowledge_node_adapter (kn-* ID) → normalized cache
  → upload (knowledge_nodes + document_chunks + causal_chains)
```

## 安装

```powershell
cd F:\ml
python -m venv .venv-pipeline
.\.venv-pipeline\Scripts\Activate.ps1
pip install -r scripts\requirements.txt
```

配置 `.env`：`SUPABASE_URL`、`SUPABASE_SERVICE_ROLE_KEY`、`OLLAMA_URL`、`OLLAMA_MODEL`。

## 常用命令

```powershell
# 状态
python scripts\ingest_knowledge.py --book-id internal-medicine-10 status

# 构建 PDF 目录（无书签时自动尝试版面标题，再回退到分页窗口）
python scripts\ingest_knowledge.py catalog

# 提取下一 pending 章
python scripts\orchestrator.py run-next

# 指定章 extract + upload
python scripts\ingest_knowledge.py extract --part "第四篇 消化系统疾病" --section "第一章 总论"
python scripts\ingest_knowledge.py upload --part "第四篇 消化系统疾病" --section "第一章 总论"

# P0 修复：从 cache 重传（无 LLM）
python scripts\ingest_knowledge.py backfill-p0

# 验收
python scripts\verify_pipeline_closure.py
```

## 直接 V3 CLI（调试）

```powershell
python scripts\pipeline_v3_extract.py "textbook/内科学（第10版）.pdf" --catalog-only
python scripts\pipeline_v3_extract.py "textbook/内科学（第10版）.pdf" --section-start 7 --section-limit 1
```

默认使用 **auto**：普通文本页走 PyMuPDF，复杂版面/表格页走 Docling，扫描页走 OCR。
调试时可用 `--pdf-parser pymupdf|docling|auto` 强制覆盖。

## 输出

| 产物 | 路径 |
|------|------|
| PDF 目录 | `generated/pipeline_v3/内科学（第10版）.catalog.json` |
| LLM 缓存 | `generated/pipeline_v3/*.extraction.json` |
| 规范化缓存 | `generated/knowledge_nodes/internal-medicine-10/*.normalized.json` |

## 质量门

- 节点需通过 `extraction_quality` + `node_guardrails`
- LLM 分块覆盖率：≥80% 且 ≥3 块（小节例外）
- 目录映射低置信度会 WARN（见 manifest `quality_metrics.catalog_mapping`）

## 更多

见 [`PIPELINE_INDEX.md`](PIPELINE_INDEX.md)。
