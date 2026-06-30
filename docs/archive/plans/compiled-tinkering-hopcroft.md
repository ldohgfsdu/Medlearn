# 通用教材解析器与精准抽取计划

## Context
用户希望把当前只面向《内科学（第10版）》呼吸系统的提取管线升级为“通吃”的教材解析工具：既支持交互式选择教材，也支持自动扫描某个文件夹批量解析；文件格式至少支持 PDF、TXT，后续可扩展 DOCX/EPUB/Markdown；教材很多，不能为每本书都手写一次脚本。同时当前 staging 结果暴露出两个问题：目录定位可跑通但仍有 missing；小节切分过于泛化，导致 12608 个 staging 节点和大量重复标题。因此下一步要同时做两件事：一是把通用“教材解析入口”搭好，二是把内科学管线改得更精准，确保不会把低质量节点写入生产数据。

## Recommended implementation

### 1. 新增统一 CLI：`scripts/textbook_parser.py`

实现一个通用入口，负责交互式/自动模式调度，而不是让用户记多个子脚本。

推荐命令（统一入口始终是 `scripts/textbook_parser.py`）：

```bash
# 交互模式：列出 textbook/ 下教材，选择一本或多本
python scripts/textbook_parser.py interactive --input textbook --out generated/textbook --verbose

# 自动模式：扫描目录内所有支持格式教材
python scripts/textbook_parser.py auto --input textbook --out generated/textbook --dry-run

# 单文件模式：指定一本教材
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook --force --wait-lock
```

所有模式支持统一参数：

- `--force`：忽略缓存强制重跑。
- `--wait-lock`：遇到同一本书的 lock 时等待；默认跳过并提示。
- `--dry-run`：只列出将要解析的文件、bookId、输出目录、缓存命中情况和将执行的 pipeline，不写文件。
- `--verbose`：输出 reader、TOC 匹配、segment、validation 的详细日志。
- `--pipeline reader|segment|nodes|validate|all`：可选预留参数，用于只重跑某一阶段；第一版至少在 CLI 帮助中保留，若实现成本低则直接支持。

交互模式设计：

- 不依赖系统文件夹选择器（命令行环境跨平台更稳），而是在终端列出目录内教材：
  - `[1] 内科学（第10版）.pdf`
  - `[2] 生理学（第10版）.pdf`
  - ...
- 用户输入：
  - 数字：选一本
  - `1,3,5`：选多本
  - `all`：全部
  - `q`：退出
- 后续如果做 Electron/桌面 UI，再接原生文件选择器；CLI 先保证可用、可批处理。

### 2. 支持格式与 reader 抽象

新增目录：`scripts/textbook_pipeline/readers/`

- `base.py`
  - 定义 `TextbookDocument` / `PageRecord` / `TocEntry` 数据结构。
- `pdf_reader.py`
  - 使用 PyMuPDF/fitz。
  - 输出 pages jsonl + toc json。
- `txt_reader.py`
  - TXT 没有真实页码，使用 `sourceType: 'chunk'`，`pageNumber: -1`，并额外记录 `chunkIndex`、`charStart`、`charEnd`。
  - 编码先用 `charset-normalizer`/`chardet`（若可用）检测，fallback 为 UTF-8 + `errors='replace'`，避免 GBK/混合编码直接 crash。
  - 分块策略：优先按空行段落聚合；次选按换行聚合并保证每块至少约 200 字；兜底按约 1000 字符切分且尽量在句号/分号/换行处断开，避免切断句子。
- 后续预留：
  - `docx_reader.py`：python-docx
  - `epub_reader.py`：ebooklib/bs4
  - `markdown_reader.py`

统一输出：

```json
{
  "bookId": "internal-medicine-10",
  "sourcePath": "textbook/内科学（第10版）.pdf",
  "format": "pdf",
  "pagesPath": "generated/textbook/internal-medicine-10/pages.jsonl",
  "tocPath": "generated/textbook/internal-medicine-10/toc.json"
}
```

### 3. 书籍识别与输出目录规范

新增 `scripts/textbook_pipeline/book_registry.py`：

- 从文件名推断，采用多模式正则 + ASCII slug + 哈希 fallback，避免中文路径/重复名问题：
  - 支持 `内科学（第10版）.pdf`、`内科学(第10版).pdf`、`内科学 第10版.pdf`、`内科学10版.pdf`、`内科学（第10版）（上册）.pdf`、`内科学_第十版_2024.pdf`、`内科学_第十版_下册.pdf` 等常见形式。
  - 支持阿拉伯数字和中文数字版次：`第10版`、`第十版`、`十版` 都应规范化为 `editionNumber: 10`。
  - 支持 volume 识别：上册/下册/第1册/第一册/全目录书签可复制检索等备注进入 metadata；影响 bookId 时只保留规范 volume，如 `-vol1`、`-vol2`。
  - `bookId` 必须是 ASCII slug；slugify 前预处理 `/\\:*?"<>|`、全角括号、空白、上下册等特殊字符；已知教材可用映射，如 `内科学` → `internal-medicine`，未知教材使用拼音不可用时 fallback：`book-<sha256(filename)[:10]>`。
  - 若输出目录已存在且 sourcePath 不同，自动追加 `-v2`/`-v3` 后缀，避免 bookId 碰撞覆盖。
  - 输出 metadata 保留原始中文 `title`、`edition`、`volume`、`sourceFilename`，不要把信息只压进 bookId。
- 每本书输出到独立目录：

```text
generated/textbook/
  internal-medicine-10/
    pages.jsonl
    toc.json
    segments.jsonl
    nodes.staging.json
    validation-report.md
    validation-report.json
    reader-report.json
  physiology-10/
    pages.jsonl
    toc.json
```

这样多本教材不会互相覆盖。

### 4. 升级 `extract_pdf_text.py` 为通用 reader wrapper

保留现有脚本兼容，但内部调用新 reader：

- 现在输出 `internal_medicine_pages.jsonl` / `internal_medicine_toc.json`。
- 新模式输出 `pages.jsonl` / `toc.json` 到书籍目录。
- 老命令仍可用，避免之前流程断掉。

### 5. 精修 `segment_by_catalog.py`

当前 segment 是全文搜标题，下一步改为：

1. 优先使用 PDF TOC：
   - normalize 分 strict/fuzzy 两级：strict 只去空格、全角空格、`|/｜` 等格式噪声；fuzzy 仅用于候选提示和人工确认，不直接覆盖 strict 结果，避免“肺部感染”和“肺部感染性疾病”误合并。
   - catalog label/name/aliases 同样生成 strict key。
   - 按 TOC level、父子关系、页码连续性和出现顺序定位 chapter/section；如果 TOC level 缩进不一致，fallback 到正文正则标题匹配，不能只靠全文包含。
2. TOC 没有的“附/一二三”只在父级 page range 内搜索正文标题。
3. pageEnd 取下一个同级/上级目录项开始页 - 1，而不是全局下一个任何目录项。
4. 输出定位字段：
   - `method`: `toc` / `body-heading` / `not-found`
   - `matchType`: `strict` / `alias` / `body-regex` / `fuzzy-candidate`
   - `confidence`: 0-1，用于 validation 分级；fuzzy 结果默认只作为 candidate，不直接视为 found。
5. 对 missing 给出候选 TOC 标题，方便快速补 alias。

优先修已发现 missing：

- `阻塞性睡眠呼吸障碍` alias 加 `阻塞性睡眠呼吸暂停`。
- `2019冠状病毒病` 要正文内搜索，TOC 没书签。
- `呼吸健康概要` 要确认是否在正文中存在；若 PDF 无标题，则 report 标为 catalog-only/待人工确认。

### 6. 精修 `extract_knowledge_nodes.py`

当前按全文任意关键词切分，导致大量重复。改为“标题行评分机制”，而不是只靠关键词正则。

节点来源分三类，避免重新走向关键词泛滥切分：

- `segment-main`：每个 catalog segment 的主节点。
- `explicit-heading`：显式标题行，例如 `一、临床表现`、`【治疗】`、`病因和发病机制`。
- `definition-sentence`：仅在 segment 开头区域推断出的定义节点。

标题行评分特征：

- 行长度短、独立成行、前后为空行或标题样式，得分增加。
- 匹配 `【...】`、`一、...`、`（一）...`、`第...节` 等标题模式，得分增加。
- 行内只有小节名或小节名后接少量标点，得分增加。
- 出现在长句中、前后紧跟大量正文、句末为普通句号，得分降低。
- 阈值可配置，输出每个小节的 `headingScore` 和 `headingEvidence`，方便调参。

有效标题候选：

- `【定义】`
- `一、定义`
- `（一）定义`
- 单独成行且长度较短的 `定义` / `流行病学` / `病因和发病机制`
- PDF 提取中前后有换行的标题行

额外规则：教材正文经常没有“定义”这个显式标题，而是以“某某疾病是指……”“某某病是一种……”开头。导入学习工具时仍需要生成“定义”知识点，因此：

- 只允许在很小范围内触发定义推断：segment 开头前 1-3 个自然段，或第一个显式小节标题之前；不能在整个 segment 全文扫描。
- 强定义节点必须同时满足：位置在开头区域、命中定义句式、定义句主语 X 与当前 segment 标题/alias/简称/英文缩写相关。
- 若首段/前几段出现 `X 是指...`、`X 是一种...`、`X 是由/由于...引起`、`X 是以...为特征的疾病/综合征`、`X 又称...`、`X 简称...`，且 X 关联当前 segment，则生成 title=`定义` 的 inferred 节点。
- 如果只满足定义句式但没有明显 segment 关联，不生成知识节点，只在 validation 中输出 `weakDefinitionCandidates`。
- 强定义节点记录 `nodeSource: 'definition-sentence'`、`inferred: true`、`headingEvidence: ['definition-sentence']`、`headingScore`。
- 若后续存在显式 `定义` 标题，则优先显式标题，不重复生成推断定义节点。

禁止：

- 正文中出现“治疗”“诊断”等词就切。

节点策略：

- 每个 catalog segment 最多：1 个主节点 + 若干小节节点。
- 同一 segment 中同名小节可合并连续内容，但必须保留多个 sourceSpan；跨 segment 永不合并，避免不同疾病的“病因/治疗”误合并。
- 单个 segment 生成节点数超过阈值时 validation 强警告；阈值应可配置：优先读取 catalog item 的 `maxNodesPerSegment`，否则使用 `max(30, 子项数量 + 5)` 之类的动态阈值，避免肺炎等复杂章节误报。
- 生成 `sourceSpan.lineStart/lineEnd`，不仅是 pageStart/pageEnd。

### 7. 增强 validation

修改 `validate_nodes.py`：

- duplicate title 跨 segment 允许但必须通过 `chapter + title` 区分；同一 segment 内重复 > 3 直接 error 或 high warning。
- 单个 chapter node count 超过动态阈值分两级：超过 warningThreshold 记 warning，超过 errorThreshold 记 error；阈值从 catalog `maxNodesPerSegment` / `warningMaxNodes` / `errorMaxNodes` 或子项数量推断。
- content hash 重复检查；跨 segment 重复只 warning，同 segment 大量重复 high warning。
- missing catalog 分级：
  - chapter/section missing：error
  - 附/子项 missing：warning
- `definition inferred but weak evidence`：只满足定义句式但未包含 segment 标题/alias/简称，不生成节点，只记录 weakDefinitionCandidates warning。
- `section heading score below threshold but accepted`：标题评分刚过线但证据弱，warning，便于调参。
- validation 输出 Markdown + JSON 双格式：`validation-report.md` 便于人工读，`validation-report.json` 便于程序消费。
  - 每个 catalog item：found/method/matchType/confidence/pageStart/pageEnd/nodeCount/warnings。

### 8. 稳定性、缓存和增量解析

- 所有写文件操作先写 `.tmp`，完成后 `os.replace(tmp, out)` 原子替换，避免中断后留下半文件。
- 写入前检查目标磁盘剩余空间；解析期间创建 `.lock` 文件，完成后最后写 metadata 并删除 lock，避免原子写入失败或半文件被误判为缓存命中。
- 并发解析同一本书时如果发现 lock，默认跳过并提示；提供 `--wait-lock` 可等待。lock 文件记录 `pid/time/hostname/bookId/sourcePath`；若进程不存在或超过 stale TTL（默认 2 小时），标记 stale lock 并允许覆盖。
- 每个 reader 在 metadata 中记录：`generatedAt`、`sourceMtime`、`sourceSize`、`sourceSampleHash`、`parserVersion`、`pipelineVersion`、`errors`。
- 每次 reader 产出 `reader-report.json`，记录页数、TOC 数、空页数、错误页、是否加密、是否疑似扫描件、编码检测结果等。
- 解析缓存：若目标 `pages.jsonl`/`toc.json` 已存在，且 metadata 中的 `sourceMtime/sourceSize/sourceSampleHash/pipelineVersion` 与源文件和当前管线一致，则默认跳过；提供 `--force` 强制重解析，避免 git checkout 等 mtime 不变场景使用旧缓存。
- PDF 异常恢复：加密/扫描件/TOC 乱码时不要静默跳过，metadata 和 report 标明 `encrypted`、`noTextLayer`、`emptyToc`、`pageErrors`；若 `len(toc) < 5` 或 TOC 命中率过低，segment 自动回退到 body-heading 正则定位。
- 增量解析准备：保留 TOC diff 所需 metadata，未来第10版→第11版可比较 TOC 和 textHash，只重跑变化章节。

### 9. Catalog 跨教材复用

- catalog schema 支持可选 `extends` 字段，例如外科学或诊断学可复用基础章节模板，只覆盖差异项。
- 本轮先实现 schema 预留和 README 说明，不必完成完整继承解析器；但文件格式要从一开始兼容。

### 10. 产物仍保持 staging，不导入生产

本轮只改脚本和生成文件，不更新 [src/db/extractedKnowledge.ts](g:/MedLearn/src/db/extractedKnowledge.ts)。等 validation 结果合理后，再做 `emit_extracted_knowledge.py`。

## Critical files to modify

- `scripts/textbook_parser.py`（新增统一 CLI）
- `scripts/textbook_pipeline/readers/base.py`（新增）
- `scripts/textbook_pipeline/readers/pdf_reader.py`（新增）
- `scripts/textbook_pipeline/readers/txt_reader.py`（新增）
- `scripts/textbook_pipeline/book_registry.py`（新增）
- `scripts/textbook_pipeline/atomic_io.py`（新增，`.tmp` + `os.replace` 原子写入）
- `scripts/textbook_pipeline/metadata.py`（新增，缓存判断、source mtime/size/sampleHash/parserVersion）
- `scripts/textbook_pipeline/lock.py`（新增，解析锁与 `--wait-lock` 支持）
- `scripts/textbook_pipeline/extract_pdf_text.py`（兼容旧命令，改为调用 reader）
- `scripts/textbook_pipeline/segment_by_catalog.py`
- `scripts/textbook_pipeline/extract_knowledge_nodes.py`
- `scripts/textbook_pipeline/validate_nodes.py`（输出 `validation-report.md` 和 `validation-report.json`）
- `scripts/textbook_pipeline/catalog.internal-medicine.json`（补 alias）
- `scripts/textbook_pipeline/README.md`

## Implementation phases

### Phase 1：通用解析器骨架

目标：多本书都能解析出：

- `pages.jsonl`
- `toc.json`
- `metadata.json`
- `reader-report.json`

范围：`scripts/textbook_parser.py`、book registry、reader、atomic/metadata/lock。

### Phase 2：目录切分精准化

目标：生成 `segments.jsonl`，并在 `validation-report.json/md` 中清楚看到 found/missing/method/matchType/confidence/page range/candidates。

范围：`segment_by_catalog.py`、catalog aliases、TOC strict/alias/body fallback。

### Phase 3：知识节点精准化

目标：生成 `nodes.staging.json`，节点数从 12608 降到合理规模，同时保留：

- 主节点
- 显式小节节点
- 推断定义节点
- `sourceSpan`
- `headingEvidence`
- `headingScore`
- `nodeSource`

## Verification

1. 通用 CLI：

```bash
python scripts/textbook_parser.py auto --input textbook --out generated/textbook --dry-run
python scripts/textbook_parser.py parse --file "textbook/内科学（第10版）.pdf" --out generated/textbook
```

2. 内科学精准管线：

```bash
python scripts/textbook_pipeline/segment_by_catalog.py --catalog scripts/textbook_pipeline/catalog.internal-medicine.json --pages generated/textbook/internal-medicine-10/pages.jsonl --toc generated/textbook/internal-medicine-10/toc.json --out generated/textbook/internal-medicine-10/segments.jsonl
python scripts/textbook_pipeline/extract_knowledge_nodes.py --segments generated/textbook/internal-medicine-10/segments.jsonl --out generated/textbook/internal-medicine-10/nodes.staging.json
python scripts/textbook_pipeline/validate_nodes.py --catalog scripts/textbook_pipeline/catalog.internal-medicine.json --segments generated/textbook/internal-medicine-10/segments.jsonl --nodes generated/textbook/internal-medicine-10/nodes.staging.json --report generated/textbook/internal-medicine-10/validation-report.md
```

3. 成功标准：

- 单本 PDF 可以通过通用 CLI 解析。
- auto 模式能识别 `textbook/` 下所有 PDF/TXT 并分书输出。
- 内科学 respiratory catalog missing 从 3 降低到 0 或只剩确认不存在的附录项。
- staged nodes 从 12608 降到合理数量（目标数百级，不是一万级）。
- validation errors 为 0，重复标题高警告显著下降。
