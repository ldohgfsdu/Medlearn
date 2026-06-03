# MedLearn PDF 教材提取方案

**版本**: 1.0  
**日期**: 2026-06-03  
**状态**: 已验证

---

## 目录

1. [方案概述](#1-方案概述)
2. [架构设计](#2-架构设计)
3. [提取流程](#3-提取流程)
4. [工具与脚本](#4-工具与脚本)
5. [配置说明](#5-配置说明)
6. [使用指南](#6-使用指南)
7. [输出格式](#7-输出格式)
8. [质量验证](#8-质量验证)
9. [常见问题](#9-常见问题)

---

## 1. 方案概述

### 1.1 目标

将医学教材 PDF 自动提取为结构化的知识节点，用于 MedLearn 小程序的种子数据。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| PDF 文本提取 | 支持扫描版和文字版 PDF |
| 目录解析 | 自动识别章节目录结构 |
| 知识分割 | 按章节/知识点粒度分割内容 |
| 结构化提取 | 使用 LLM 提取关键信息（标题、内容、要点、标签） |
| 质量验证 | 自动验证提取结果的完整性和准确性 |

### 1.3 支持的教材

| 教材 | 状态 | 知识节点数 |
|------|------|-----------|
| 内科学（第10版） | ✅ 已完成 | 800+ |
| 生理学（第10版） | ✅ 已完成 | 400+ |
| 诊断学（第10版） | ✅ 已完成 | 300+ |
| 药理学（第10版） | 🔄 进行中 | — |
| 外科学（第10版） | 📋 计划中 | — |

---

## 2. 架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    PDF 提取流水线                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Step 1   │───▶│  Step 2   │───▶│  Step 3   │             │
│  │ PDF→MD   │    │ 解析目录  │    │ 分割知识  │             │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │               │               │                     │
│       ▼               ▼               ▼                     │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Step 4   │◀──│  Step 5   │◀──│  Step 6   │             │
│  │ 结构化    │    │ 验证     │    │ 导出     │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────────────┐                  │
│  │         输出: knowledge_nodes.json    │                  │
│  └──────────────────────────────────────┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 两套提取方案

MedLearn 提供两套 PDF 提取方案，适用于不同场景：

| 方案 | 位置 | 特点 | 适用场景 |
|------|------|------|----------|
| **方案 A: medlearn-extractor** | `medlearn-extractor/` | 独立运行，完整流水线 | 单本教材深度提取 |
| **方案 B: textbook_pipeline** | `scripts/textbook_pipeline/` | 模块化，支持批量 | 多本教材批量处理 |

---

## 3. 提取流程

### 3.1 Step 1: PDF 转 Markdown

**目的**：将 PDF 文件转换为纯文本 Markdown 格式

**工具**：
- `pdfplumber`（文字版 PDF）
- `pytesseract` + `pdf2image`（扫描版 PDF）

**输出**：
- `text.md`：完整文本内容
- `page_index.json`：页码索引

### 3.2 Step 2: 解析目录

**目的**：从文本中提取章节目录结构

**方法**：
1. 正则表达式匹配常见目录格式（第X章、X.X 节）
2. LLM 辅助识别复杂目录结构

**输出**：
- `toc.json`：目录树结构

### 3.3 Step 3: 分割知识块

**目的**：按目录结构将文本分割为独立的知识块

**策略**：
- 一级分割：按章
- 二级分割：按节
- 三级分割：按知识点（疾病/症状/治疗）

**输出**：
- `blocks.json`：知识块数组

### 3.4 Step 4: 结构化提取

**目的**：使用 LLM 从知识块中提取结构化信息

**提取字段**：
```typescript
interface KnowledgeNode {
  id: string;                    // 唯一标识
  type: 'disease' | 'symptom' | 'treatment' | 'concept';
  title: string;                 // 标题
  content: string;               // 详细内容
  keyPoints: string[];           // 关键要点
  tags: string[];                // 标签
  difficulty: 1 | 2 | 3;         // 难度
  source: string;                // 来源教材
  sourceReference: string;       // 具体章节引用
}
```

**LLM 配置**：
- Provider：OpenAI 兼容接口 / Anthropic
- Model：gpt-4o / claude-sonnet
- Temperature：0.3（低温度保证一致性）

### 3.5 Step 5: 质量验证

**验证规则**：

| 检查项 | 标准 | 修复方式 |
|--------|------|----------|
| 标题完整性 | 非空且长度 > 5 | 重新提取 |
| 内容完整性 | 长度 > 100 字符 | 补充内容 |
| 关键要点 | 数量 ≥ 2 | LLM 补充 |
| 标签数量 | 数量 ≥ 3 | LLM 补充 |
| 重复检测 | ID 唯一 | 去重 |

### 3.6 Step 6: 导出

**输出格式**：
- `knowledge_nodes.json`：标准 JSON 格式
- `knowledge_nodes_for_miniapp.ts`：小程序专用格式
- `REPORT.md`：提取报告

---

## 4. 工具与脚本

### 4.1 方案 A: medlearn-extractor

**目录结构**：
```
medlearn-extractor/
├── config.py              # 配置文件
├── run_all.py             # 一键运行脚本
├── step1_pdf_to_markdown.py
├── step2_parse_toc.py
├── step3_split_knowledge.py
├── step4_rule_based.py    # 规则提取
├── step4_structurize.py   # LLM 提取
├── step5_validate.py
├── step6_export.py
├── requirements.txt
└── output/                # 输出目录
```

**依赖安装**：
```bash
cd medlearn-extractor
pip install -r requirements.txt
```

### 4.2 方案 B: textbook_pipeline

**目录结构**：
```
scripts/textbook_pipeline/
├── README.md
├── extract_pdf_text.py    # PDF 文本提取
├── segment_by_catalog.py  # 目录分割
├── extract_knowledge_nodes.py  # 知识节点提取
├── validate_nodes.py      # 验证
├── catalog.internal-medicine.json  # 内科学目录
├── catalog.physiology.json         # 生理学目录
└── ...
```

---

## 5. 配置说明

### 5.1 环境变量

```bash
# LLM 配置
export MEDLEARN_LLM_PROVIDER="openai"  # 或 "anthropic"
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-4o"
export OPENAI_BASE_URL="https://api.openai.com/v1"

# Anthropic 配置（可选）
export ANTHROPIC_API_KEY="your-api-key"
export ANTHROPIC_MODEL="claude-sonnet-4-20250514"

# 并发配置
export MEDLEARN_MAX_CONCURRENCY="5"
export MEDLEARN_BATCH_SIZE="50"

# 验证配置
export MEDLEARN_MIN_KEYWORDS="3"
export MEDLEARN_MIN_KEY_POINTS="2"
```

### 5.2 配置文件

**config.py 关键配置**：
```python
# PDF 路径
PDF_PATH = "内科学.pdf"

# LLM 提供商
LLM_PROVIDER = "openai"  # 或 "anthropic"

# 并发数
MAX_CONCURRENCY = 5

# 批处理大小
BATCH_SIZE = 50
```

---

## 6. 使用指南

### 6.1 方案 A: 一键运行

```bash
cd medlearn-extractor

# 完整流程
python run_all.py --pdf "内科学.pdf"

# 从指定步骤开始
python run_all.py --pdf "内科学.pdf" --from step4
```

### 6.2 方案 B: 模块化运行

```bash
# Step 1: 提取文本
python scripts/textbook_pipeline/extract_pdf_text.py \
  --pdf "textbook/内科学（第10版）.pdf" \
  --out generated/textbook

# Step 2: 分割知识
python scripts/textbook_pipeline/segment_by_catalog.py \
  --catalog scripts/textbook_pipeline/catalog.internal-medicine.json \
  --pages generated/textbook/internal-medicine-10/pages.jsonl \
  --toc generated/textbook/internal-medicine-10/toc.json \
  --out generated/textbook/internal-medicine-10/segments.jsonl

# Step 3: 提取知识节点
python scripts/textbook_pipeline/extract_knowledge_nodes.py \
  --segments generated/textbook/internal-medicine-10/segments.jsonl \
  --out generated/textbook/internal-medicine-10/nodes.staging.json

# Step 4: 验证
python scripts/textbook_pipeline/validate_nodes.py \
  --catalog scripts/textbook_pipeline/catalog.internal-medicine.json \
  --segments generated/textbook/internal-medicine-10/segments.jsonl \
  --nodes generated/textbook/internal-medicine-10/nodes.staging.json \
  --report generated/textbook/internal-medicine-10/validation-report.md
```

### 6.3 批量处理

```bash
# 自动处理所有教材
python scripts/textbook_parser.py auto \
  --input textbook \
  --out generated/textbook \
  --dry-run  # 先预览

# 正式运行
python scripts/textbook_parser.py auto \
  --input textbook \
  --out generated/textbook \
  --pipeline all
```

---

## 7. 输出格式

### 7.1 knowledge_nodes.json

```json
[
  {
    "id": "pneumonia",
    "type": "disease",
    "title": "肺炎",
    "subject": "内科学 - 呼吸系统疾病",
    "chapter": "第二篇 呼吸系统疾病",
    "content": "肺炎（pneumonia）是指终末气道、肺泡和肺间质的炎症...",
    "keyPoints": [
      "细菌性肺炎是最常见的肺炎类型",
      "临床表现主要为发热、咳嗽、咳痰",
      "胸部 X 级是诊断的重要依据"
    ],
    "tags": ["呼吸系统", "感染性疾病", "常见病"],
    "difficulty": 2,
    "source": "内科学（第10版）",
    "sourceReference": "第二篇 第三章 肺炎"
  }
]
```

### 7.2 输出目录结构

```
output/
├── text.md                    # 原始文本
├── toc.json                   # 目录结构
├── blocks.json                # 知识块
├── structured.json            # 结构化数据
├── knowledge_nodes.json       # 最终输出
├── knowledge_nodes_for_miniapp.ts  # 小程序格式
├── review_sample.json         # 验证样本
└── REPORT.md                  # 提取报告
```

---

## 8. 质量验证

### 8.1 验证指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 提取覆盖率 | ≥ 95% | 教材内容覆盖率 |
| 结构完整性 | ≥ 90% | 字段填充率 |
| 关键要点数 | ≥ 2/节点 | 每个节点的要点数 |
| 标签数量 | ≥ 3/节点 | 每个节点的标签数 |
| 重复率 | ≤ 1% | 重复节点比例 |

### 8.2 验证报告

每次提取后会生成 `validation-report.md`，包含：

1. **统计摘要**：总节点数、类型分布、难度分布
2. **质量检查**：缺失字段、内容过短、重复检测
3. **样本预览**：随机抽取 10 个节点供人工审核

### 8.3 人工审核流程

1. 查看 `validation-report.md`
2. 检查 `review_sample.json` 中的样本
3. 如有问题，调整配置后重新运行 Step 4-6
4. 确认无误后，将 `knowledge_nodes.json` 导入小程序

---

## 9. 常见问题

### 9.1 PDF 提取失败

**问题**：扫描版 PDF 无法提取文本

**解决**：
```bash
# 安装 OCR 依赖
pip install pytesseract pdf2image
# 安装 Tesseract OCR
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
```

### 9.2 LLM 调用超时

**问题**：LLM 请求超时

**解决**：
```bash
# 增加超时时间
export MEDLEARN_REQUEST_TIMEOUT="300"

# 降低并发数
export MEDLEARN_MAX_CONCURRENCY="2"
```

### 9.3 提取质量不佳

**问题**：提取的知识节点内容不完整

**解决**：
1. 检查目录解析是否正确（查看 `toc.json`）
2. 调整分割策略（增大 `BATCH_SIZE`）
3. 优化 LLM Prompt（修改 `step4_structurize.py`）

### 9.4 重复节点

**问题**：存在重复的知识节点

**解决**：
```bash
# 运行去重脚本
python medlearn-extractor/check_duplicates.py
```

---

## 附录

### A. 目录配置文件格式

```json
{
  "textbook": "内科学（第10版）",
  "chapters": [
    {
      "id": "chapter-1",
      "title": "绪论",
      "startPage": 1,
      "sections": []
    },
    {
      "id": "chapter-2",
      "title": "呼吸系统疾病",
      "startPage": 15,
      "sections": [
        {
          "id": "section-2-1",
          "title": "急性上呼吸道感染",
          "startPage": 15
        }
      ]
    }
  ]
}
```

### B. 知识节点类型定义

| 类型 | 说明 | 示例 |
|------|------|------|
| disease | 疾病 | 肺炎、哮喘、糖尿病 |
| symptom | 症状 | 发热、咳嗽、胸痛 |
| treatment | 治疗 | 抗生素治疗、手术治疗 |
| concept | 概念 | 炎症、免疫、代谢 |
| mechanism | 机制 | 病理生理机制 |
| exam | 检查 | 胸部 X 线、血常规 |

### C. 相关资源

- **medlearn-extractor**：`G:\MedLearn\medlearn-extractor\`
- **textbook_pipeline**：`G:\MedLearn\scripts\textbook_pipeline\`
- **生成的数据**：`G:\MedLearn\generated\textbook\`
- **种子数据**：`G:\MedLearn\mini-program\src\data\`

---

*文档结束。如有问题请联系开发团队。*
