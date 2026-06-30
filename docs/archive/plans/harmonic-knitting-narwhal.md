# 教材抽取入库与按教材章节整理计划

## Context

用户现在要求在通用教材解析管线打通后，继续把教材内容真正提取出来并导入学习工具里，同时在工具内“按教材、按章节”顺好。当前项目状态：

- 教材文件已放在 [textbook/](textbook/) 下，包含内科学、生理学、生化、药理学、诊断学、外科学等 PDF。
- 现有 app 知识点数据入口是 [src/db/extractedKnowledge.ts](src/db/extractedKnowledge.ts)，由 [src/db/seed.ts](src/db/seed.ts) 动态导入后写入 Dexie。
- `KnowledgeNode` 类型在 [src/types/knowledge.ts](src/types/knowledge.ts)，当前没有显式 `textbook` / `bookId` 字段，但 Dexie 可存额外字段；为了类型清晰，应补可选字段。
- 现有 UI 主要按 `subject` → `chapter` 分组：
  - [src/pages/FeynmanRecall.tsx](src/pages/FeynmanRecall.tsx)
  - [src/components/knowledge/SystemContextPanel.tsx](src/components/knowledge/SystemContextPanel.tsx)
  - [src/pages/Dashboard.tsx](src/pages/Dashboard.tsx)
- 内科学呼吸系统已有 catalog 和章节树：[src/constants/internalMedicineCatalog.ts](src/constants/internalMedicineCatalog.ts)、[scripts/textbook_pipeline/catalog.internal-medicine.json](scripts/textbook_pipeline/catalog.internal-medicine.json)。其他教材目前只有 reader 能抽页/TOC，没有人工 catalog 时不能稳定生成高质量 nodes。
- 上一轮验证发现当前 shell 环境找不到 `python`/`python3`/`py`，因此执行阶段第一步必须先确认可用 Python 命令；若仍不可用，需要用户在 VS Code/系统环境里安装或暴露 Python。

本轮目标不是继续停在 staging，而是：先对具备 catalog 的《内科学（第10版）》呼吸系统跑通 reader → segment → nodes → validate；validation 达标后生成 [src/db/extractedKnowledge.ts](src/db/extractedKnowledge.ts)；同时让工具里按教材与章节顺序展示。其他教材先完成 reader 产物和目录概览，不强行把无 catalog 的内容导入生产知识点，避免低质量节点进入工具。

## Recommended implementation

### Phase 1：先跑通抽取环境与 staging

1. 确认 Python 可执行命令：
   - 优先尝试 `python`、`python3`、`py -3`。
   - 若 bash 找不到，但 Windows/VS Code 里有解释器，则使用绝对路径或 VS Code 选择的解释器路径。
   - 若仍不可用，停止执行并提示需要安装/配置 Python；不要改用不可靠的手工解析。

2. 对《内科学（第10版）》先跑完整 staging：

```bash
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook --pipeline all --force --verbose
```

3. 检查产物：
   - `generated/textbook/internal-medicine-10/pages.jsonl`
   - `generated/textbook/internal-medicine-10/toc.json`
   - `generated/textbook/internal-medicine-10/segments.jsonl`
   - `generated/textbook/internal-medicine-10/nodes.staging.json`
   - `generated/textbook/internal-medicine-10/validation-report.md`
   - `generated/textbook/internal-medicine-10/validation-report.json`

4. 读取 validation summary：
   - 若 errors > 0，先修 catalog/segment/node 规则后重跑。
   - 若只有可接受 warnings（如 catalog-only 附录项、弱定义候选），再进入 emit 入库阶段。

5. 对其他教材先跑 reader/dry-run 或 reader：

```bash
python scripts/textbook_parser.py auto --input textbook --out generated/textbook --pipeline reader --verbose
```

这一步只生成每本书 pages/toc/metadata/reader-report，先不生成 nodes，不导入工具。

### Phase 2：新增 staging → app data emitter

新增 [scripts/textbook_pipeline/emit_extracted_knowledge.py](scripts/textbook_pipeline/emit_extracted_knowledge.py)，负责把验证通过的 `nodes.staging.json` 转成 app 可直接导入的 TypeScript。

核心行为：

1. 输入参数：
   - `--nodes generated/textbook/internal-medicine-10/nodes.staging.json`
   - `--segments generated/textbook/internal-medicine-10/segments.jsonl`
   - `--metadata generated/textbook/internal-medicine-10/metadata.json`
   - `--validation generated/textbook/internal-medicine-10/validation-report.json`
   - `--out src/db/extractedKnowledge.ts`
   - `--allow-warnings`：允许 warnings 存在但 errors 必须为 0。

2. 安全门禁：
   - 默认读取 validation JSON；如果 errors > 0 直接退出，不写 [src/db/extractedKnowledge.ts](src/db/extractedKnowledge.ts)。
   - 若 validation 文件不存在，也直接退出，避免未验证数据入库。

3. 转换规则：
   - 从 staging node 保留：`id`、`type`、`title`、`subject`、`chapter`、`content`、`keyPoints`、`causalLinks`、`relatedNodes`、`difficulty`、`tags`。
   - 补齐 `createdAt`、`updatedAt` 为固定生成时间戳，避免每次 import 都变化。
   - `source` 设为 `'seed'` 或按现有类型扩展为 `'textbook'`。为减少前端改动，推荐第一版仍用 `'seed'`，同时增加 tags/可选字段记录教材来源。
   - 增加可选字段：`bookId`、`textbook`、`edition`、`sourceSpan`、`nodeSource`、`inferred`，用于后续按教材筛选和溯源。

4. 排序规则：
   - 以 `segments.jsonl` 的顺序作为教材章节顺序。
   - 每个 segment 内按：`segment-main` → `definition-sentence` → `explicit-heading`。
   - explicit-heading 内尽量按 `sourceSpan.lineStart` 排序。
   - 输出 [src/db/extractedKnowledge.ts](src/db/extractedKnowledge.ts) 时就是这个顺序，方便工具加载后保持教材顺序。

5. 输出头部注释：
   - 教材名、bookId、版次、生成时间。
   - 节点总数。
   - validation errors/warnings summary。
   - 明确“自动从 staging 生成，请勿手改节点内容”。

### Phase 3：扩展 KnowledgeNode 类型以支持教材元数据

修改 [src/types/knowledge.ts](src/types/knowledge.ts)：

1. 增加可选字段：

```ts
bookId?: string;
textbook?: string;
edition?: string;
nodeSource?: 'segment-main' | 'explicit-heading' | 'definition-sentence';
inferred?: boolean;
sourceSpan?: {
  segmentId?: string;
  pageStart?: number;
  pageEnd?: number;
  lineStart?: number | null;
  lineEnd?: number | null;
  headingPath?: string[];
  textHash?: string;
};
```

2. `source` 第一版不改 union，继续使用 `'seed' | 'ai-generated'`，避免 DB 和 UI 大面积改动；教材来源由 `bookId/textbook/tags` 表达。

### Phase 4：按教材、按章节整理 UI

目标是工具内不是只看到散乱的 subject/chapter，而是能先按教材，再按章节顺序看。

1. 新增或扩展教材目录常量：
   - 新增 [src/constants/textbookCatalog.ts](src/constants/textbookCatalog.ts)。
   - 定义 `TextbookInfo`：`bookId`、`title`、`edition`、`subjectOrder`/`chapterOrder`。
   - 第一版注册：`internal-medicine-10`，章节顺序来自现有 respiratory catalog。

2. 修改 [src/pages/FeynmanRecall.tsx](src/pages/FeynmanRecall.tsx)：
   - 分组从单纯 `system -> chapter` 调整为 `textbook -> system/subject -> chapter`。
   - 对有 `bookId` 的导入节点，优先按 `bookId/textbook` 分组。
   - 章节排序优先使用 catalog/segments 顺序；无 catalog 的节点放在末尾“未编目”。
   - 保留现有呼吸系统 catalog tree 体验，避免回退。

3. 修改 [src/components/knowledge/SystemContextPanel.tsx](src/components/knowledge/SystemContextPanel.tsx)：
   - 在 selected node 有 `textbook` 时显示教材名。
   - 同一教材内按 chapterOrder 展示章节节点。
   - 没有 `bookId` 的旧 seed 节点继续使用原逻辑。

4. 修改 [src/pages/Dashboard.tsx](src/pages/Dashboard.tsx)：
   - 进度统计仍可保留现有系统维度。
   - 增加或调整展示时使用教材章节顺序，不要让新导入节点被排到“其他”。

### Phase 5：可选：生成教材目录索引，供 UI 精确排序

为了避免前端手写每本教材目录，新增 emitter 输出一个轻量目录索引：

- [src/db/extractedTextbookIndex.ts](src/db/extractedTextbookIndex.ts)

包含：

```ts
export const extractedTextbooks = [
  {
    bookId: 'internal-medicine-10',
    title: '内科学',
    edition: '第10版',
    chapters: [
      { segmentId, label, name, subject, pageStart, pageEnd, depth, parentSegmentId }
    ]
  }
];
```

前端 UI 可用它排序；如果第一版要少改 UI，可以先只生成 `extractedKnowledge.ts`，后续再接 `extractedTextbookIndex.ts`。

## Critical files to modify

- [scripts/textbook_pipeline/emit_extracted_knowledge.py](scripts/textbook_pipeline/emit_extracted_knowledge.py)（新增）
- [src/db/extractedKnowledge.ts](src/db/extractedKnowledge.ts)（由 emitter 生成）
- [src/types/knowledge.ts](src/types/knowledge.ts)
- [src/constants/textbookCatalog.ts](src/constants/textbookCatalog.ts)（新增，或先最小化改动）
- [src/pages/FeynmanRecall.tsx](src/pages/FeynmanRecall.tsx)
- [src/components/knowledge/SystemContextPanel.tsx](src/components/knowledge/SystemContextPanel.tsx)
- [src/pages/Dashboard.tsx](src/pages/Dashboard.tsx)
- [scripts/textbook_pipeline/README.md](scripts/textbook_pipeline/README.md)

可能需要继续修的抽取文件：

- [scripts/textbook_parser.py](scripts/textbook_parser.py)
- [scripts/textbook_pipeline/segment_by_catalog.py](scripts/textbook_pipeline/segment_by_catalog.py)
- [scripts/textbook_pipeline/extract_knowledge_nodes.py](scripts/textbook_pipeline/extract_knowledge_nodes.py)
- [scripts/textbook_pipeline/validate_nodes.py](scripts/textbook_pipeline/validate_nodes.py)
- [scripts/textbook_pipeline/catalog.internal-medicine.json](scripts/textbook_pipeline/catalog.internal-medicine.json)

## Execution and verification

1. Python 可用性：

```bash
python --version || python3 --version || py -3 --version
```

2. 抽取内科学：

```bash
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook --pipeline all --force --verbose
```

3. 查看 validation：

```bash
python scripts/textbook_pipeline/validate_nodes.py --catalog scripts/textbook_pipeline/catalog.internal-medicine.json --segments generated/textbook/internal-medicine-10/segments.jsonl --nodes generated/textbook/internal-medicine-10/nodes.staging.json --report generated/textbook/internal-medicine-10/validation-report.md
```

4. 生成 app 数据：

```bash
python scripts/textbook_pipeline/emit_extracted_knowledge.py --nodes generated/textbook/internal-medicine-10/nodes.staging.json --segments generated/textbook/internal-medicine-10/segments.jsonl --metadata generated/textbook/internal-medicine-10/metadata.json --validation generated/textbook/internal-medicine-10/validation-report.json --out src/db/extractedKnowledge.ts --allow-warnings
```

5. app 验证：

```bash
npm run build
npm run dev
```

手工检查：

- 费曼页面知识地图按“教材/系统/章节”展开。
- 《内科学（第10版）》呼吸系统章节顺序与教材一致。
- 每章节点顺序是主节点 → 定义 → 显式小节。
- Dashboard 统计能看到新导入教材节点。
- Console 出现 `新增 N 个教材知识点`，且无导入异常。

## Success criteria

- Python 环境可执行，内科学完整 extraction pipeline 产出 staging 文件。
- `validation-report.json` errors 为 0。
- [src/db/extractedKnowledge.ts](src/db/extractedKnowledge.ts) 由 emitter 自动生成，不再手写 483 个节点。
- app 能导入新节点，且不破坏旧 seed 数据。
- 工具内知识地图按教材与章节顺序展示。
- 其他教材先有 reader/toc/metadata 产物；没有 catalog 前不把低质量节点导入生产知识点。
