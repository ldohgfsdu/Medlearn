# 教材提取 Pipeline：可视化 + 优化 + 数据库设计

## Context

Pipeline CLI 当前只用 `print()` 输出纯文本，运行过程黑盒、无进度、无耗时统计。
数据库层已有一个 `knowledge_nodes` 表，但缺少 pipeline 运行记录、错误追踪、版本控制等管理能力。
本次改动分三部分：(1) CLI 可视化，(2) Pipeline 优化，(3) 数据库 schema 升级。

---

## Part 1: Pipeline CLI 可视化（Rich Terminal UI）

**目标**：运行 `python scripts/textbook_parser.py parse ...` 时，终端实时显示进度、耗时、状态。

### 方案：用 Python 内置能力实现轻量可视化

不引入 `rich` 等重型依赖（已在 requirements.txt 管理依赖），用 `sys.stderr` + ANSI 转义码实现：
- 阶段进度条（reader → segment → nodes → validate）
- 每阶段耗时计时器
- 彩色状态图标（✅ 完成 / ⏳ 运行中 / ❌ 失败 / ⏭ 跳过）
- 运行结束后输出 Summary 表格

### 修改文件

| 文件 | 改动 |
|---|---|
| [scripts/textbook_parser.py](scripts/textbook_parser.py) | 新增 `PipelineProgress` 类，替换各阶段的 `print()` 调用 |
| `scripts/textbook_pipeline/` (所有 stage runner) | 返回结构化结果（dict），由 parser 层统一渲染 |

### PipelineProgress 类设计

```python
class PipelineProgress:
    """Terminal progress visualization using ANSI escape codes."""

    STAGES = ["reader", "segment", "nodes", "validate"]

    def stage_start(self, name: str) -> None: ...
    def stage_done(self, name: str, status: str, detail: str) -> None: ...
    def summary(self, results: dict) -> None: ...
```

- `stage_start("reader")` → 打印 `⏳ reader ...`
- `stage_done("reader", "✅", "387 pages, 12 TOC entries (2.3s)")` → 覆盖当前行
- `summary()` → 最后输出表格，汇总各阶段耗时/结果
- 如果终端不支持 ANSI（如 Windows CMD），自动降级为普通 print

### Summary 输出示例

```
📖 内科学（第10版） pipeline complete
┌──────────┬──────┬────────────────────────────────┐
│ Stage    │ Time │ Result                         │
├──────────┼──────┼────────────────────────────────┤
│ reader   │ 2.3s │ 387 pages, 12 TOC              │
│ segment  │ 0.1s │ 23/23 matched                  │
│ nodes    │ 0.0s │ 48 nodes, 5 weak defs          │
│ validate │ 0.0s │ 0 errors, 2 warnings           │
└──────────┴──────┴────────────────────────────────┘
Total: 2.5s | Output: generated/textbook/internal-medicine-10/
```

---

## Part 2: Pipeline 优化

### 2.1 Catalog 层级嵌套匹配

**问题**：当前只匹配 TOC 顶层条目，`第二节 慢性心衰` 无法和 `第二章 心衰` 的子节关联。

**改动**：[segment_by_catalog.py](scripts/textbook_pipeline/segment_by_catalog.py) 中 `_match_toc()` 支持层级搜索：
- 先 strict 匹配当前 section title
- 未命中时，检查 TOC 中 level 差 1 的下级条目
- 给 segment 加 `tocChildren` 字段，支持将大 section 拆成多个子 segment

### 2.2 Fuzzy 搜索增强

**改动**：在 `_match_toc()` 的 fuzzy 匹配中加入 `difflib.SequenceMatcher`：
```python
from difflib import SequenceMatcher
if SequenceMatcher(None, fuzzy_title, t_fuzzy).ratio() > 0.85:
    return entry, "fuzzy"
```

### 2.3 节点去重

**改动**：[extract_knowledge_nodes.py](scripts/textbook_pipeline/extract_knowledge_nodes.py) 的 `extract_nodes_from_segments()` 末尾加去重：
- 按 `(chapter, title)` 去重
- 相同标题保留 `contentHash` 非 null 的版本

### 2.4 节点定义质量排序

**改动**：`weakDefinitionCandidates`  排序：
- 定义长度 > 20 字符 → high
- 定义长度 10-20 → medium  
- < 10 → low

### 2.5 PDF 加密/损坏检测

**改动**：[textbook_parser.py](scripts/textbook_parser.py) `run_reader()` 包裹 try/except：
```python
try:
    result = read_file(file_path, book_id=book_id)
except Exception as e:
    print(f"  ❌ Failed to read {file_path}: {e}")
    return {}
```

### 2.6 空 segment 检测（validate 层）

**改动**：[validate_nodes.py](scripts/textbook_pipeline/validate_nodes.py) 新增规则 `empty-segment`：
- 如果 `found=true` 但 segment text 为空，报 warning

---

## Part 3: 数据库 Schema 升级

### 当前状态

App 已有 `knowledge_nodes` 表（Supabase），但 pipeline 运行记录无处存储。

### 推荐 Schema（Supabase SQL Migration）

```sql
-- 1. Pipeline 运行记录
CREATE TABLE pipeline_runs (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  book_id       TEXT NOT NULL,           -- e.g. 'internal-medicine-10'
  source_file   TEXT NOT NULL,           -- PDF 文件名
  status        TEXT NOT NULL DEFAULT 'running',  -- running/success/failed
  pipeline_version TEXT NOT NULL,        -- '2.0.0'
  stages        JSONB NOT NULL DEFAULT '{}',  -- 各阶段详情
  started_at    TIMESTAMPTZ DEFAULT NOW(),
  finished_at   TIMESTAMPTZ,
  error_message TEXT
);

-- stages JSONB 结构示例:
-- {
--   "reader":   {"status": "success", "duration_ms": 2300, "pages": 387, "toc_entries": 12},
--   "segment":  {"status": "success", "duration_ms": 100, "matched": 23, "total": 23},
--   "nodes":    {"status": "success", "duration_ms": 50,  "nodes": 48, "weak_defs": 5},
--   "validate": {"status": "success", "duration_ms": 30,  "errors": 0, "warnings": 2}
-- }

-- 2. Pipeline 输出快照（每次成功运行生成一份）
CREATE TABLE pipeline_snapshots (
  id            UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  run_id        UUID REFERENCES pipeline_runs(id),
  book_id       TEXT NOT NULL,
  total_nodes   INT NOT NULL,
  total_segments INT NOT NULL,
  nodes_data    JSONB NOT NULL,          -- nodes.staging.json 的内容
  segments_data JSONB,                   -- 可选：segments.jsonl 汇总
  validation    JSONB,                   -- validation-report.json 内容
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 3. 索引
CREATE INDEX idx_pipeline_runs_book ON pipeline_runs(book_id);
CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status);
CREATE INDEX idx_pipeline_snapshots_book ON pipeline_snapshots(book_id);
```

### Pipeline 上传集成

新增 `upload` stage（第五阶段）：
- `textbook_parser.py` 新增 `run_stage_upload(out, book_id, verbose)`
- 上传 `nodes.staging.json` → Supabase `knowledge_nodes` 表（upsert by id）
- 创建 `pipeline_runs` 记录
- 创建 `pipeline_snapshots` 快照

### App 端：Pipeline 历史查看（可选）

在 "我的" 页面加一个 "Pipeline 历史" 入口，展示：
- 最近运行列表（书名、状态、时间、耗时）
- 点击查看单次运行详情（各阶段结果、节点数、错误列表）

---

## 修改文件汇总

| 文件 | 改动类型 |
|---|---|
| `scripts/textbook_parser.py` | 新增 PipelineProgress、upload stage、PDF 损坏检测 |
| `scripts/textbook_pipeline/segment_by_catalog.py` | 层级匹配、fuzzy 增强 |
| `scripts/textbook_pipeline/extract_knowledge_nodes.py` | 节点去重、定义质量排序 |
| `scripts/textbook_pipeline/validate_nodes.py` | 空 segment 检测 |
| `scripts/textbook_pipeline/upload_to_supabase.py` | **新建**：上传节点到 Supabase |
| `scripts/requirements.txt` | 无需新增依赖（纯 Python 实现） |
| `docs/PDF_EXTRACTION_GUIDE.md` | 重写为当前 4+1 阶段 pipeline 说明 |
| SQL migration（文档形式） | pipeline_runs + pipeline_snapshots 表 |

## 验证方式

1. `python scripts/textbook_parser.py parse --file textbook/internal-medicine-10.pdf --pipeline all --verbose` → 检查终端输出有彩色进度 + summary
2. 检查 `generated/textbook/internal-medicine-10/` 下所有输出文件正常
3. `python scripts/textbook_parser.py parse --file textbook/internal-medicine-10.pdf`（第二次不带 --force）→ 检查 cache hit（reader 阶段跳过）
4. 对比修复前后的 `validation-report.json`，确认 segmentId 分组正确
5. 在 Supabase 控制台执行 SQL migration，确认表创建成功
