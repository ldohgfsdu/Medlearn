# Heading Signal Audit Report

> 状态：只读审计完成，待人工批准最终 splitter 与 ID 契约
> 日期：2026-06-30
> 作用域：`内科学（第10版）` 哮喘（PDF 62–70）、肺结核（PDF 102–116）
> 审计器：`scripts/textbook_pipeline/heading_signal_auditor.py`
> 测试：`tests/test_heading_signal_auditor.py`（52 passed with artifacts；26 passed + 26 skipped in clean checkout）
> 边界：未修改现有 extractor、UI、状态文件或远端数据

## 1. 执行摘要

本轮只读审计验证了 Document Tree v1 契约的阻断项是否已解决：

| 阻断项 | 状态 | 证据 |
|---|---|---|
| U+2003 不能通用表示标题/正文边界 | ✅ 已证明 | body font + `：` 覆盖 U+2003，编号正文正确归为 body；chapter 标题内部 U+2003 不触发拆分 |
| bracket 标题用普通空格而非 U+2003 | ✅ 已解决 | bracket 按 `】` 闭合定界拆分；`【流行病学】` heading_text + body_text 正确分离 |
| 章节标题跨两行 | ✅ 已解决 | `merge_chapter_continuations` 合并同 block 同 font/size 续行；joint SourceAnchor `l{first}-{last}` |
| `dict` 只有 span bbox，需 `rawdict` 字符级 | ✅ 已采用 | 审计器使用 `page.get_text("rawdict", sort=True)` |
| raw payload 须规范化 JSON span 数组 | ✅ 已实现 | `normalize_spans_for_fingerprint` + SHA-256，raw_anchor 取 128 bit（32 hex） |
| ID 必须包含/绑定源 PDF checksum | ✅ 已实现 | `dt:{version}:{scope}:{full_pdf_sha256_256bit}:{raw_anchor}`，不截断 |
| 默认 Windows 控制台兼容 | ✅ 已解决 | 输出改用 ASCII `[OK]`/`[NO]`；默认 PowerShell `--twice` 退出码 0 |

**稳定性**：连续两次运行，raw anchors 完全一致（`identical_order=True, identical_set=True`）。
**黄金路径**：T1–T5 全部 PASS，每条路径的每个 expected node 都按严格源序匹配到不同的 heading_candidate（2/2 或 4/4）。
**测试**：52/52 passed（含 PDF 集成测试）；模拟 clean checkout（移除 gitignored 的 `generated/heading_audit/`）后 26 个 core tests 仍全部 passed，26 个 PDF 集成测试按预期 skipped。

## 2. 审计方法

### 2.1 数据源

- PDF：`textbook/内科学（第10版）.pdf`
- SHA-256：`C0BB559FA2C8448A54612F7EDF751C9342DF584D15CE90D0CF7E4F97BF852D78`（256 bit，完整保留于 anchor_id）
- PyMuPDF：`1.27.2.3`
- 提取模式：`rawdict`（字符级 bbox），`sort=True`

### 2.2 信号采集

每行记录以下原始信号：

- `pdf_page` / `raw_block_index` / `raw_line_index`：物理位置
- `spans[]`：每个 span 的 `text` / `font` / `size` / `bbox` / `color` / `flags` / `chars[]` / `separators[]`
- `separators`：U+2003 (EM SPACE) / U+2002 (EN SPACE) / U+2009 (THIN SPACE) / U+200A (HAIR SPACE) 的字符级 bbox
- `marker`：`chapter` / `bracket` / `chinese_parenthetical` / `arabic_dot` / `arabic_parenthetical` / `arabic_right_parenthesis` / `appendix`
- `font_bucket`：`heading` / `body` / `page_header` / `unknown`
- `em_space_position` / `has_body_punct` / `has_sentence_punct`
- `heading_text` / `body_text`：按 marker 分派后的显式拆分结果（非通用 U+2003 拆分）

### 2.3 确定性 ID（≥128 bit，不截断）

```
raw_anchor = p{pdf_page}:b{block_index}:l{line_index}:{sha256(span_payload)[:32]}
anchor_id  = dt:{textbook_version_id}:{scope_id}:{full_pdf_sha256}:{raw_anchor}
```

- `raw_anchor` 的指纹段为 SHA-256 前 32 hex chars = **128 bit**（满足 ≥128 bit 要求）
- `anchor_id` 第 4 段为**完整** PDF SHA-256（64 hex chars = 256 bit），不截断，源绑定无歧义
- `span_payload` 为规范化 JSON span 数组（`sort_keys=True`，bbox/size 保留 2 位小数），不依赖 `str(float)`，不依赖分类结果

## 3. 已验证事实

| # | 事实 | 证据 |
|---|---|---|
| A1 | raw anchors 跨运行稳定 | `stability.json`: `stable=True`, 两 scope 均满足 `identical_order=True, identical_set=True` |
| A2 | 页眉永不成为节点 | 哮喘 8 个、肺结核 14 个 `page_header` 均满足 `marker=None`，未进入 `heading_candidate` |
| A3 | scope 根节点唯一 | 两 scope 各检测到恰好 1 个 `chapter` marker |
| A4 | 五条黄金路径全部通过 | `golden_paths.json`: T1–T5 `passed=True`，`matched_node_count == expected_node_count`（2/2 或 4/4） |
| A5 | 黄金路径按严格源序匹配 | 每个 expected_node 匹配到不同的 heading_candidate，`search_start` 单调递增；out-of-order 场景由 core test 验证为 fail |
| A6 | `bracket` 恒用 heading font | 哮喘 11/11、肺结核 18/18 均为 `FZLTHK--GBK1-0` |
| A7 | `chinese_parenthetical` 恒用 FZZYSK1 | 哮喘 13/13、肺结核 15/15 均为 `FZZYSK1--GBK1-0` |
| A8 | `arabic_dot` 在肺结核全用 heading font | 72/72 均为 `FZLTHK--GBK1-0` |
| A9 | `arabic_parenthetical` 全用 body font | 哮喘 18/18、肺结核 22/22 均为 `FZSSK--GBK1-0` |
| A10 | `arabic_right_parenthesis` 全用 body font | 哮喘 7/7、肺结核 7/7 均为 `FZSSK--GBK1-0` |
| A11 | U+2003 不能通用表示标题边界 | `（1） 气道炎症形成机制：...` 有 U+2003 + body font + `：` → 正确归为 body（非 heading） |
| A12 | chapter 标题内部 U+2003 不触发拆分 | `第四章\u2003`（21pt FZLTZCHK）→ `split_position=None, body_text=""`；chapter marker 被 SPLITTABLE_MARKERS 排除 |
| A13 | BPT/BDT 标题不被截断 | `2.\u2002支气管激发试验（BPT）\u2003用于测定...` → `heading_text` 含 "BPT"，`body_text` 为剩余句 |
| A14 | ID 绑定完整 PDF checksum | `anchor_id` 第 4 段为完整 64 char `c0bb559fa2...852d78`（256 bit） |
| A15 | raw_anchor 满足 ≥128 bit | 指纹段为 32 hex chars（128 bit），由 core test `test_raw_anchor_128_bits` 断言 |
| A16 | anchor_id scope 内唯一 | 两 scope 内均无重复 `anchor_id` |
| A17 | bracket 标题按 `】` 闭合定界拆分 | `【流行病学】 哮喘是世界上最常见...` → `heading_text="【流行病学】"`, `body_text="哮喘是世界上最常见..."`；由 core test `test_bracket_splits_on_ordinary_space` 断言 |
| A18 | bracket 独立标题不拆分 | `【病因和发病机制】` → `body_text=""`；`】` 后无正文时不拆 |
| A19 | chapter 标题跨两行已合并 | `第四章\u2003`(l0) + `支气管哮喘`(l1) → 合并为 `heading_text="第四章 支气管哮喘"`，joint SourceAnchor `l0-1`；由 integration test `test_chapter_merged_full_title` 断言 |
| A20 | TB chapter 标题跨两行已合并 | `第八章\u2003`(l0) + `肺结核`(l1) → 合并为 `heading_text="第八章 肺结核"`，joint SourceAnchor `l0-1` |
| A21 | 默认 Windows 控制台兼容 | ASCII `[OK]`/`[NO]` 输出；默认 PowerShell（无 PYTHONIOENCODING）`--twice` 退出码 0 |
| A22 | merged chapter raw_anchor 稳定 | 合并后 joint anchor 跨运行一致（`stability.json` `identical_order=True`） |

## 4. 统计

### 4.1 哮喘（PDF 62–70，印刷 31–39）

```
总行数: 425
  heading_candidate: 55
  body:              362
  page_header:         8

markers:
  chapter:                1
  bracket:               11
  chinese_parenthetical: 13
  arabic_dot:            30
  arabic_parenthetical:  18
  arabic_right_parenthesis: 7

marker × font_bucket:
  bracket:                heading=11
  chinese_parenthetical:  heading=13
  arabic_dot:             heading=21  body=9    (9 个为编号正文)
  arabic_parenthetical:   body=18               (全部编号正文)
  arabic_right_parenthesis: body=7              (全部编号正文)

separators:
  has_em_space:           34
  has_other_sep_no_em_space: 40

ambiguous_blocks: 34
  numbered body resolved (body font + punct): 25
  heading_candidate with body font:            9
```

### 4.2 肺结核（PDF 102–116，印刷 71–85）

```
总行数: 744
  heading_candidate: 109
  body:              621
  page_header:        14

markers:
  chapter:                1
  bracket:               18
  chinese_parenthetical: 15
  arabic_dot:            72
  arabic_parenthetical:  22
  arabic_right_parenthesis: 7

marker × font_bucket:
  bracket:                heading=18
  chinese_parenthetical:  heading=15
  arabic_dot:             heading=72           (全部标题)
  arabic_parenthetical:   body=22              (全部编号正文)
  arabic_right_parenthesis: body=7             (全部编号正文)

separators:
  has_em_space:           87
  has_other_sep_no_em_space: 64

ambiguous_blocks: 29
  numbered body resolved (body font + punct): 26
  heading_candidate with body font:            3
```

## 5. 黄金路径验证（严格有序节点匹配）

每条路径定义 `expected_nodes`（有序 `{marker, title_contains}` 列表）。验证器遍历 scope 内 `heading_candidate`（按源序），对每个 expected_node 找到下一个 marker 匹配且 `heading_text` 含期望标题子串的候选；`search_start` 单调递增，确保同一候选不会匹配两个节点。所有节点按序匹配成功且页眉未成为节点，路径才 PASS。

| 路径 | scope | expected | matched | 节点序列（marker @ page） | 通过 |
|---|---|---|---|---|---|
| T1 | asthma | 2 | 2 | chapter@62 → bracket@62 | ✅ |
| T2 | asthma | 4 | 4 | chapter@62 → bracket@62 → chinese_paren@62 → arabic_dot@62 | ✅ |
| T3 | asthma | 4 | 4 | chapter@62 → bracket@63 → chinese_paren@64 → arabic_dot@64 | ✅ |
| T4 | tuberculosis | 4 | 4 | chapter@102 → bracket@106 → chinese_paren@107 → arabic_dot@107 | ✅ |
| T5 | tuberculosis | 4 | 4 | chapter@102 → bracket@110 → chinese_paren@112 → arabic_dot@112 | ✅ |

T4 的 bracket 节点 `heading_text` 含 "结核病的分类标准"（含"的"，已修正契约原题）。
T5 的最后一个 arabic_dot 节点 `heading_text` 含 "初治活动性肺结核"（初治治疗方案标题）。

每条路径的每个 expected_node 都附 `raw_anchor` + `pdf_page` + `heading_text` 证据，可在 PDF 中回查。页眉在两 scope 均未成为节点（`page_headers_are_not_nodes=true`）。

## 6. 关键发现

### 6.1 U+2003 不是通用的标题/正文边界

**证据 1**（编号正文）：哮喘 p.63 存在 `（1）\u2003 气道炎症形成机制：气道慢性炎症反应...`
- 有 U+2003（EM SPACE）
- 但 font = `FZSSK--GBK1-0`（body）
- 且含 `：`（body 标点）

**证据 2**（chapter 标题内部）：`第四章\u2003`（21pt FZLTZCHK）
- 有 U+2003，但它是章节标题的尾部填充，不是标题/正文边界
- chapter marker 被 `SPLITTABLE_MARKERS` 排除，`split_position=None, body_text=""`

**结论**：U+2003 既出现在标题内部（章节标题、页眉连接），也出现在编号正文块中。生产 splitter 必须先识别 marker + font + body 标点，再决定是否按 U+2003 拆分。

**split 分派规则（已实现）**：
- `bracket` marker：按 `】` 闭合定界拆分（不依赖 U+2003）；`】` 后有非空正文 → 拆分
- `chinese_parenthetical` / `arabic_dot` / `appendix`：按 U+2003 拆分（这些 marker 用 U+2003 作正文边界）
- `chapter` marker：不拆分（U+2003 是尾部/内部）
- heading font + chapter marker → 标题候选，不拆分
- body font + `：；。` → 正文，即使有 U+2003 也不拆
- body font + 无 body 标点 + 短文本 → 歧义，标 `heading_candidate` 但不拆分，需人工裁决

### 6.1.1 bracket 标题用普通空格，不是 U+2003

**证据**：哮喘 p.62 `【流行病学】 哮喘是世界上最常见的慢性疾病之一...`
- `】` 后是普通空格（U+0020），不是 U+2003
- `em_space_position = -1`
- 旧逻辑（依赖 U+2003）未拆分，`heading_text` 包含整段正文

**修复**：bracket 按 `】` 闭合位置定界，`line_text[close_pos+1:].strip()` 为 body。已由 core test `test_bracket_splits_on_ordinary_space` 和 integration test `test_asthma_bracket_epidemiology_has_body` 断言。

### 6.1.2 章节标题跨两行

**证据**：哮喘 p.62 block 0
- l0: `第四章\u2003`（21pt FZLTZCHK，chapter marker）
- l1: `支气管哮喘`（同 block，同 font，同 size，无 marker → 旧逻辑误归 body）

**修复**：`merge_chapter_continuations` 在分类后扫描 chapter heading_candidate，合并同 block + 同 font + 同 size + 无 marker 的续行：
- `heading_text = "第四章 支气管哮喘"`（空格连接）
- `raw_line_index = "0-1"`（行范围标记）
- `raw_anchor` 指纹从合并行的联合 spans 计算（joint SourceAnchor）
- 续行从 `lines` 列表移除，`merged_from_lines` 记录原始行号

已由 integration test `test_chapter_merged_full_title`（哮喘）和 `test_tb_chapter_merged_full_title`（肺结核）断言。

### 6.2 `dict` 只有 span bbox，`rawdict` 提供字符级

审计器使用 `page.get_text("rawdict", sort=True)`，每个 span 含 `chars[]` 数组，每个 char 有独立 `bbox` 和 `c`（字符）。`dict` 模式的 span 只有整体 bbox，无法定位单个分隔符字符的位置。

### 6.3 规范化 JSON span 数组 + SHA-256（≥128 bit）

```python
normalized = [{"t": text, "f": font, "s": round(size,2), "b": [round(x,2) for x in bbox]}, ...]
payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
sha256 = hashlib.sha256(payload.encode("utf-8")).hexdigest()
raw_anchor = f"p{page}:b{block}:l{line}:{sha256[:32]}"   # 128 bit 指纹
anchor_id  = f"dt:{version}:{scope}:{full_pdf_sha256}:{raw_anchor}"  # 256 bit 源绑定
```

- 不依赖 `str(float)`（用 `round(x, 2)` + `json.dumps`）
- 不依赖分类结果（pre-classification payload）
- 不依赖标题文本（splitter 规则改变不影响 ID）
- raw_anchor 指纹段 32 hex chars = **128 bit**（满足 ≥128 bit 要求）
- anchor_id 保留**完整** PDF SHA-256（64 hex chars = 256 bit），不截断

### 6.4 marker × font 强相关

| marker | heading font | body font | 结论 |
|---|---|---|---|
| `bracket` 【】 | 100% FZLTHK | 0% | 标题专用 |
| `chinese_parenthetical` （一） | 100% FZZYSK1 | 0% | 标题专用 |
| `arabic_dot` 1. | 哮喘 70% / TB 100% | 哮喘 30% | 哮喘有编号正文混入 |
| `arabic_parenthetical` （1） | 0% | 100% | **编号正文专用** |
| `arabic_right_parenthesis` 1） | 0% | 100% | **编号正文专用** |

生产 splitter 可据此设定规则：
- `bracket` / `chinese_parenthetical` → 标题（font 确认）
- `arabic_dot` + heading font → 标题；+ body font → 编号正文
- `arabic_parenthetical` / `arabic_right_parenthesis` → 编号正文（不进标题栈）

### 6.5 真正歧义的块（需人工裁决）

哮喘 9 个、肺结核 3 个 `heading_candidate` with body font，例如：
- 肺结核 p.114 `（1） 治疗方案`（9 字符，body font，无 body 标点）

这些块短到像标题，但 font 是 body，且无标点佐证。生产 splitter 应将其标记为 `pending_review`，不自动归入标题栈。

## 7. 字体桶定义（proposed，待人工确认）

```
PAGE_HEADER_FONTS = {FZLTZHUNHK--GBK1-0}   # 页眉，8pt，y0<50
HEADING_FONTS     = {FZLTHK--GBK1-0,        # bracket / arabic_dot 标题
                     FZZYSK1--GBK1-0,        # chinese_parenthetical 标题
                     FZLTZCHK--GBK1-0}       # chapter 标题（21pt）
BODY_FONTS        = {FZSSK--GBK1-0}          # 正文 + 编号正文
```

未归入上述桶的字体（`DIN-Medium`, `SimSun`, `FZKTK`, `FZLTXHK`, `FZLTXIHK`, `E-BX`）标记为 `unknown`，需人工确认是否需要扩展桶定义。

## 8. 测试结构

两层测试结构，core tests 永不 skip：

| 层级 | 数量 | 跳过条件 | 内容 |
|---|---|---|---|
| Core tests | 26 | 永不跳过 | 合成 fixture 直接调用 `classify_line` / `compute_raw_anchor` / `verify_golden_paths`；fitz 懒加载 |
| PDF integration | 26 | `generated/heading_audit/*.json` 缺失时跳过 | 加载审计 JSON 验证稳定性、页眉、黄金路径、BPT/BDT、章节合并、bracket 正文、编号正文、字体相关、anchor_id |

Core tests 覆盖：
- `TestDetectMarker`（7）：marker 正则
- `TestClassifySplit`（8）：chapter 不拆、bracket 拆（U+2003 和普通空格）、bracket 独立不拆、BPT/BDT 拆、编号正文归 body
- `TestPageHeader`（1）：font+size+bbox 检测页眉
- `TestDeterministicID`（5）：128 bit anchor、完整 checksum、稳定性、不依赖 str(float)
- `TestGoldenPathVerifier`（5）：有序匹配 pass、out-of-order fail、missing node fail、页眉不影响路径、verifier 边界

PDF integration 覆盖（新增部分）：
- `TestPDFBPTBDT.test_chapter_merged_full_title`：哮喘 chapter 合并为 "第四章 支气管哮喘"，joint SourceAnchor `l0-1`
- `TestPDFChapterMergeTB.test_tb_chapter_merged_full_title`：肺结核 chapter 合并为 "第八章 肺结核"
- `TestPDFBracketBody`（5）：`【流行病学】` 有正文、独立 bracket 无正文、`【结核病的分类标准】` 有正文、`【结核分枝杆菌】` 有正文、`【结核病的化学治疗】` 独立无正文

clean checkout 模拟（移除 gitignored 的 `generated/heading_audit/`）：26 core passed，26 integration skipped，符合设计。

## 9. 未解决项

| # | 项 | 说明 |
|---|---|---|
| U1 | per-scope Transition Rule Table 仍为 `proposed` | 需人工审核 marker→marker 转移规则后才能 `approved` |
| U2 | `HEADING_FONTS`/`BODY_FONTS` 完整性 | `unknown` 字体（DIN-Medium 等）未归类，需确认是否影响标题识别 |
| U3 | 真正歧义块（12 个） | body font + 短文本 + 无标点，需人工裁决是标题还是编号正文 |
| U4 | bbox 坐标空间 | 审计器保存了 span/char bbox（pdf_points），但现有 evidence.json 的 bbox 坐标语义尚未核实 |
| U5 | 表格/图/题注覆盖 | 审计器只处理 `block.type==0`（文本块），未审计表格和图的完整性 |
| U6 | verifier 不检测 heading_candidate 内的页眉误分类 | `page_headers_are_not_nodes` 只看 `classification=="page_header"` 的 line；若页眉被 `classify_line` 误分为 `heading_candidate`，verifier 无法检测（由 core test `test_page_header_misclassified_as_heading_fails` 记录此边界） |
| U7 | 章节合并仅限 chapter marker | 其他多行标题（如 bracket/chinese_parenthetical 跨行）未合并；当前两个 scope 未观察到此类情况 |

## 10. 结论

所有阻断项均已通过只读审计解决：

1. **U+2003 边界问题**：split 按 marker 分派；bracket 按 `】` 定界，chapter 不拆，body font + body 标点覆盖 U+2003
2. **bracket 普通空格**：bracket 按 `】` 闭合定界拆分，不依赖 U+2003
3. **章节标题跨两行**：`merge_chapter_continuations` 合并同 block 续行，joint SourceAnchor `l{first}-{last}`
4. **Windows 控制台兼容**：ASCII `[OK]`/`[NO]` 输出，默认 PowerShell `--twice` 退出码 0
5. **rawdict 字符级**：已采用，分隔符有独立 bbox
6. **规范化 JSON + SHA-256（≥128 bit）**：raw_anchor 取 128 bit（32 hex），不依赖 `str(float)` 和分类结果
7. **ID 绑定完整 PDF checksum**：`anchor_id` 含完整 64 char PDF SHA-256（256 bit），不截断

raw anchors 跨运行稳定（含合并后的 joint anchor），五条黄金路径全部通过严格有序节点匹配（2/2 或 4/4），页眉未成为节点。52 项测试在有产物时全部通过；clean checkout 下 26 个 core tests 仍全部通过。

**建议**：审计通过，可提交最终 splitter 与 ID 契约。生产 splitter 应实现：
- marker + font + body 标点三信号分类
- bracket 按 `】` 闭合定界拆分；`chinese_parenthetical`/`arabic_dot`/`appendix` 按 U+2003 拆分；chapter 不拆
- 章节标题跨行合并，joint SourceAnchor 用行范围标记
- `arabic_parenthetical` / `arabic_right_parenthesis` 不进标题栈
- 真正歧义块标记 `pending_review`
- raw anchor 基于 pre-classification span payload，≥128 bit
- anchor_id 保留完整 PDF SHA-256，不截断
- 控制台输出使用 ASCII，不依赖 PYTHONIOENCODING
