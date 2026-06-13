# Medlearn 教材提取 Pipeline

**版本**: 2.0
**日期**: 2026-06-07
**状态**: 当前实现

---

## 目录

1. [概述](#1-概述)
2. [Pipeline 架构](#2-pipeline-架构)
3. [使用指南](#3-使用指南)
4. [输出格式](#4-输出格式)
5. [Catalog 配置](#5-catalog-配置)
6. [验证规则](#6-验证规则)
7. [Supabase 上传](#7-supabase-上传)
8. [常见问题](#8-常见问题)

---

## 1. 概述

### 1.1 目标

将医学教材 PDF 自动提取为结构化的知识节点（knowledge nodes），用于 Medlearn 应用的种子数据。

### 1.2 技术栈

| 组件 | 技术 |
|------|------|
| PDF 解析 | PyMuPDF (`pymupdf`) |
| 目录匹配 | 规则引擎 + SequenceMatcher 模糊匹配 |
| 节点提取 | 正则评分 + 定义模式匹配 |
| 校验 | 规则引擎（目录覆盖率、节点数、空段检测） |
| 上传 | Supabase Python SDK |
| 可视化 | ANSI 终端实时进度 |

### 1.3 依赖安装

```bash
cd scripts
pip install -r requirements.txt
# 依赖: pymupdf, supabase, python-dotenv, requests
```

---

## 2. Pipeline 架构

### 2.1 流程概览

```
PDF/TXT 文件
    │
    ▼
┌─────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐  ┌──────────┐
│ Reader   │─▶│ Segment  │─▶│ Nodes  │─▶│ Validate │─▶│ Upload   │
│ (Stage 1)│  │ (Stage 2)│  │(Stage 3)│  │ (Stage 4)│  │ (Stage 5)│
└─────────┘  └──────────┘  └────────┘  └──────────┘  └──────────┘
    │             │             │            │              │
    ▼             ▼             ▼            ▼              ▼
 pages.jsonl  segments.jsonl  nodes.*   validation-    Supabase
 toc.json                   .json     report.*       knowledge_nodes
 metadata.json                                     pipeline_runs
```

### 2.2 各阶段说明

#### Stage 1: Reader
- 读取 PDF/TXT，提取每页文本和目录结构
- 输出: `pages.jsonl`, `toc.json`, `metadata.json`, `reader-report.json`
- 支持缓存：基于文件 mtime + size + pipeline version 验证

#### Stage 2: Segment
- 根据 catalog（教材目录 JSON）将页面分为 segment
- 匹配策略：strict → fuzzy → hierarchical（支持层级匹配）
- 输出: `segments.jsonl`

#### Stage 3: Nodes
- 从 segment 文本中提取知识节点
- 三种来源：segment-main（目录匹配）、explicit-heading（标题评分）、definition（定义模式）
- 自动去重 + 定义质量排序
- 输出: `nodes.staging.json`

#### Stage 4: Validate
- 校验节点与 catalog 的一致性
- 检查：目录覆盖率、节点数上限、空 segment、重复标题、弱定义
- 输出: `validation-report.json`, `validation-report.md`

#### Stage 5: Upload（可选）
- 将节点上传到 Supabase `knowledge_nodes` 表（upsert）
- 创建 `pipeline_runs` 运行记录和 `pipeline_snapshots` 快照

### 2.3 文件结构

```
scripts/
├── textbook_parser.py                    # CLI 入口 + 可视化
├── catalog.internal-medicine.json        # 内科学 catalog
├── requirements.txt
└── textbook_pipeline/
    ├── __init__.py
    ├── metadata.py                       # 缓存验证
    ├── lock.py                           # 文件锁（原子 O_EXCL）
    ├── atomic_io.py                      # 原子文件写入
    ├── book_registry.py                  # 文件名 → book_id 映射
    ├── segment_by_catalog.py             # Catalog 分段
    ├── extract_knowledge_nodes.py        # 节点提取
    ├── validate_nodes.py                 # 校验
    ├── upload_to_supabase.py             # Supabase 上传
    ├── migration_pipeline_infra.sql      # DB migration
    └── readers/
        ├── __init__.py
        ├── base.py                       # ReaderResult/PageRecord 数据类
        ├── pdf_reader.py                 # PyMuPDF PDF Reader
        ├── txt_reader.py                 # 纯文本 Reader
        └── factory.py                    # 按扩展名分发
```

---

## 3. 使用指南

### 3.1 基本用法

```bash
# 处理单本教材（全阶段）
python scripts/textbook_parser.py parse \
  --file textbook/internal-medicine-10.pdf \
  --verbose

# 指定阶段
python scripts/textbook_parser.py parse \
  --file textbook/internal-medicine-10.pdf \
  --pipeline reader

# 强制重跑（忽略缓存）
python scripts/textbook_parser.py parse \
  --file textbook/internal-medicine-10.pdf \
  --force --verbose
```

### 3.2 批量处理

```bash
# 预览（dry-run）
python scripts/textbook_parser.py auto \
  --input textbook \
  --out generated/textbook \
  --dry-run

# 正式运行
python scripts/textbook_parser.py auto \
  --input textbook \
  --out generated/textbook
```

### 3.3 上传到 Supabase

```bash
# 设置环境变量
export SUPABASE_URL="https://your-project.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"
export SILICONFLOW_KEY="your-siliconflow-key" # optional; omit to upload without vectors

# 运行全阶段 + 上传
python scripts/textbook_parser.py parse \
  --file textbook/internal-medicine-10.pdf \
  --upload --verbose
```

### 3.4 命令行参数

| 参数 | 说明 |
|------|------|
| `parse` | 处理单个文件 |
| `auto` | 批量处理目录下所有 PDF/TXT |
| `--file <path>` | 指定 PDF/TXT 文件 |
| `--input <dir>` | 批量输入目录 |
| `--out <dir>` | 输出目录（默认 `generated/textbook`） |
| `--pipeline <stage>` | 指定阶段：reader / segment / nodes / validate / all |
| `--force` | 忽略缓存，强制重跑 |
| `--verbose` | 详细输出 |
| `--dry-run` | 预览模式，不实际执行 |
| `--upload` | 运行后上传到 Supabase |
| `--wait-lock` | 等待锁释放而不是立即报错 |

### 3.5 终端输出示例

```
  📖 internal-medicine-10
  Stages: reader → segment → nodes → validate

  ✅ Reader    (2.3s) 387 pages, 12 TOC entries
  ✅ Segment   (0.1s) 23/23 matched
  ✅ Nodes     (0.0s) 48 nodes, 5 weak defs
  ✅ Validate  (0.0s) 0 errors, 2 warnings

  ✅ internal-medicine-10 done

  Stage        Status     Time     Detail
  ──────────── ────────── ──────── ─────────────────────────────
  reader       ✅         2.3s     387 pages, 12 TOC entries
  segment      ✅         0.1s     23/23 matched
  nodes        ✅         0.0s     48 nodes, 5 weak defs
  validate     ✅         0.0s     0 errors, 2 warnings

  Total: 2.4s | Output: generated/textbook/internal-medicine-10/
```

---

## 4. 输出格式

### 4.1 pages.jsonl（每行一个页面）

```json
{"page_number": 15, "text": "肺炎是指终末气道...", "char_count": 2450}
```

### 4.2 toc.json

```json
[
  {"level": 1, "title": "第二篇 呼吸系统疾病", "page": 15},
  {"level": 2, "title": "第六章 肺部感染性疾病", "page": 42}
]
```

### 4.3 segments.jsonl

```json
{
  "segmentId": "第六章肺部感染性疾病",
  "chapter": "第一篇 呼吸系统疾病",
  "sectionTitle": "第六章 肺部感染性疾病",
  "found": true,
  "matchType": "strict",
  "confidence": 1.0,
  "pageStart": 42,
  "pageEnd": 68,
  "textHash": "a1b2c3d4e5f6g7h8"
}
```

### 4.4 nodes.staging.json

```json
{
  "nodes": [
    {
      "id": "a1b2c3d4e5f6",
      "type": "disease",
      "title": "肺炎",
      "chapter": "第一篇 呼吸系统疾病",
      "nodeSource": "segment-main",
      "contentHash": "a1b2c3d4e5f6g7h8",
      "sourceSpan": {"segmentId": "...", "pageStart": 42, "pageEnd": 68}
    }
  ],
  "weakDefinitionCandidates": [
    {"segmentId": "...", "definition": "肺炎是指...", "confidence": "high"}
  ]
}
```

### 4.5 validation-report.json

```json
{
  "summary": {
    "totalNodes": 48,
    "totalSegments": 23,
    "foundSegments": 23,
    "errors": 0,
    "warnings": 2,
    "weakDefinitions": 5
  },
  "segments": [...],
  "errors": [],
  "warnings": [...]
}
```

---

## 5. Catalog 配置

Catalog 是 JSON 文件，定义教材的章节结构，用于 segment 阶段的页面匹配。

### 5.1 格式

```json
{
  "bookId": "internal-medicine-10",
  "title": "内科学（第10版）",
  "chapters": [
    {
      "chapterTitle": "第一篇 呼吸系统疾病",
      "sections": [
        {"title": "第六章 肺部感染性疾病", "aliases": ["肺炎", "肺部感染"]}
      ]
    }
  ]
}
```

### 5.2 匹配策略

| 优先级 | 策略 | 说明 |
|--------|------|------|
| 1 | strict | 标题完全一致（去除空格后）或匹配 alias |
| 2 | fuzzy (exact) | 归一化后文本完全一致（去掉括号、章节号） |
| 3 | fuzzy (similar) | SequenceMatcher 相似度 ≥ 0.85 |
| 4 | hierarchical | 核心标题包含父级 TOC 条目（层级匹配） |

### 5.3 命名规则

Catalog 文件名格式：`catalog.{book-id}.json`

搜索路径（按优先级）：
1. `scripts/textbook_pipeline/catalog.{book-id}.json`
2. `scripts/catalog.{book-id}.json`

---

## 6. 验证规则

| 规则 | 级别 | 说明 |
|------|------|------|
| `catalog-missing` | error | Catalog 中的条目在 TOC 中未找到 |
| `node-count-exceeded` | error | 单个 segment 节点数超过上限（默认 50） |
| `empty-segment` | warning | TOC 匹配成功但提取文本为空 |
| `duplicate-title-high` | warning | 同一标题出现 > 3 次 |
| `weak-definition` | warning | 弱定义候选（低置信度） |
| `low-confidence` | warning | fuzzy/hierarchical 匹配置信度 < 0.8 |

---

## 7. Supabase 上传

### 7.1 环境变量

```bash
# 方式 1: 使用 Supabase service key（推荐，有写权限）
export SUPABASE_URL="https://xxx.supabase.co"
export SUPABASE_SERVICE_ROLE_KEY="your-service-role-key"

# 方式 2: 使用 anon key
export EXPO_PUBLIC_SUPABASE_URL="https://xxx.supabase.co"
export EXPO_PUBLIC_SUPABASE_ANON_KEY="your-anon-key"
```

### 7.2 数据库表

运行 `scripts/textbook_pipeline/migration_pipeline_infra.sql` 创建：

- `pipeline_runs` — 运行记录
- `pipeline_snapshots` — 输出快照

节点数据写入已有的 `knowledge_nodes` 表。

### 7.3 上传内容

| 表 | 内容 | 冲突策略 |
|---|---|---|
| `knowledge_nodes` | nodes.staging.json 中的节点、正文和节点关系 | upsert (by id) |
| `document_chunks` | segments.jsonl 切分后的正文、页码、关联节点和可选向量 | 按教材全量刷新 |
| `pipeline_runs` | 运行状态、耗时、阶段结果 | insert |
| `pipeline_snapshots` | 节点 + segments + validation 完整快照 | insert |

---

## 8. 常见问题

### Q: 缓存没有生效？

检查 `metadata.json` 中是否包含 `sourceMtime` 和 `pipelineVersion` 字段。这两个字段是缓存验证的关键。

### Q: Catalog 匹配率低？

1. 检查 PDF 的 TOC 是否正确提取（查看 `toc.json`）
2. 使用 `aliases` 字段添加常见缩写
3. 调整 catalog 中的 title 使其更接近 PDF 中的 TOC 文本

### Q: 如何添加新教材？

1. 将 PDF 放入 `textbook/` 目录
2. 创建 `scripts/catalog.{book-id}.json`
3. 在 `scripts/textbook_pipeline/book_registry.py` 中添加文件名映射
4. 运行 `python scripts/textbook_parser.py parse --file textbook/your-book.pdf --verbose`

### Q: 节点提取质量不佳？

1. 查看 `nodes.staging.json` 中的 `weakDefinitionCandidates`
2. 检查 `validation-report.json` 中的 warning
3. 考虑使用 LLM 辅助提取（当前版本使用规则引擎）
