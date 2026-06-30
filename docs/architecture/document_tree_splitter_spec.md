# Document Tree Splitter & ID Encoding Specification

> 状态：生产规范（依据 ADR-011 和 heading signal audit）
> 日期：2026-06-30
> 作用域：`内科学（第10版）` 哮喘、肺结核黄金章节
> 依据：`docs/adr/ADR-011-document-tree-v1.md`、`docs/architecture/heading_signal_audit_report.md`

本文档是生产 splitter 和 ID 编码的权威实现规范。所有规则已通过只读审计器
`scripts/textbook_pipeline/heading_signal_auditor.py` 在真实 PDF 上验证。

## 1. ID 编码

### 1.1 raw_anchor

```
raw_anchor = p{pdf_page}:b{block_index}:l{line_index}:{sha256(span_payload)[:32]}
```

- `pdf_page`：1-based PDF 页码
- `block_index`：rawdict block 索引（0-based）
- `line_index`：block 内 line 索引（0-based）；合并行用 `{first}-{last}` 范围
- 指纹段：SHA-256 前 32 hex chars = **128 bit**

### 1.2 span_payload 规范化

```python
normalized = [
    {"t": span.text, "f": span.font, "s": round(span.size, 2),
     "b": [round(x, 2) for x in span.bbox]}
    for span in spans
]
payload = json.dumps(normalized, ensure_ascii=False, sort_keys=True)
```

约束：
- 使用 `round(x, 2)` + `json.dumps`，不依赖 `str(float)`
- pre-classification payload：基于原始 span 数据，不依赖分类结果
- splitter 规则改变不影响 ID

### 1.3 anchor_id

```
anchor_id = dt:{textbook_version_id}:{scope_id}:{full_pdf_sha256}:{raw_anchor}
```

- 第 4 段为**完整** PDF SHA-256（64 hex chars = 256 bit），不截断
- 不同 scope 或 textbook version 产生不同 ID
- ID 冲突使生成失败，不自动覆盖

### 1.4 稳定性要求

- 同源文件、同 manifest、同解析规则重复运行 → ID 不变
- 源 PDF 或提取模式（`rawdict`/`sort=True`）改变 → ID 改变
- 合并多行标题的 joint anchor 跨运行稳定

## 2. 标题栈规则

### 2.1 提取模式

```python
page.get_text("rawdict", sort=True)
```

- `rawdict`：字符级 bbox，每个 span 含 `chars[]`
- `sort=True`：按位置排序，保证 block/line 索引稳定

### 2.2 页眉检测（不进标题栈）

```python
is_page_header = (
    first_font in PAGE_HEADER_FONTS      # {"FZLTZHUNHK--GBK1-0"}
    and first_size <= 9.0
    and bbox_y0 < 50.0
)
```

页眉 `classification = "page_header"`，`marker = None`，永不成为 DocumentNode。

### 2.3 Marker 检测

| marker | 正则 | 示例 |
|---|---|---|
| `chapter` | `^第[一二三四五六七八九十百零〇\d]+[篇章节]` | `第四章` |
| `bracket` | `^【([^】]+)】` | `【流行病学】` |
| `chinese_parenthetical` | `^（[一二三四五六七八九十百]+）` | `（一）` |
| `arabic_dot` | `^\d+\.\s` | `1. ` |
| `arabic_parenthetical` | `^（\d+）` | `（1）` |
| `arabic_right_parenthesis` | `^\d+）` | `1）` |
| `appendix` | `^附[：:]` | `附：` |

### 2.4 Font Bucket

```python
PAGE_HEADER_FONTS = {"FZLTZHUNHK--GBK1-0"}
HEADING_FONTS     = {"FZLTHK--GBK1-0", "FZZYSK1--GBK1-0", "FZLTZCHK--GBK1-0"}
BODY_FONTS        = {"FZSSK--GBK1-0"}
```

- `FZLTHK`：bracket / arabic_dot 标题
- `FZZYSK1`：chinese_parenthetical 标题
- `FZLTZCHK`：chapter 标题（21pt）
- `FZSSK`：正文 + 编号正文

未归入上述桶的字体标记 `unknown`，需人工确认。

### 2.5 marker × font 决策表

| marker | heading font | body font | 行为 |
|---|---|---|---|
| `chapter` | heading_candidate（不拆） | — | 进标题栈，根节点 |
| `bracket` | heading_candidate（按 `】` 拆） | — | 进标题栈 |
| `chinese_parenthetical` | heading_candidate（按 U+2003 拆） | — | 进标题栈 |
| `arabic_dot` | heading_candidate（按 U+2003 拆） | body | heading 进栈；body 为正文 |
| `arabic_parenthetical` | — | body（不进栈） | 编号正文 |
| `arabic_right_parenthesis` | — | body（不进栈） | 编号正文 |
| `appendix` | heading_candidate（按 U+2003 拆） | — | 进标题栈 |

### 2.6 不进标题栈的 marker

`arabic_parenthetical`（`（1）`）和 `arabic_right_parenthesis`（`1）`）恒用 body
font，是编号正文，不产生 DocumentNode。

## 3. Split 分派规则

### 3.1 bracket：按 `】` 闭合定界

```python
if marker == "bracket":
    close_pos = line_text.find("】")
    if close_pos >= 0:
        candidate_body = line_text[close_pos + 1:].strip()
        if candidate_body:
            heading_text = line_text[:close_pos + 1]   # 含 】
            body_text = candidate_body
        # else: bracket-only heading, no body
```

**关键**：真实 PDF 的 bracket 标题用普通空格（U+0020）而非 U+2003 作正文分隔。
必须按 `】` 闭合位置定界，不依赖 U+2003。

### 3.2 chinese_parenthetical / arabic_dot / appendix：按 U+2003 拆

```python
elif marker in {"chinese_parenthetical", "arabic_dot", "appendix"}:
    if em_space_pos >= 0:
        candidate_body = line_text[em_space_pos + 1:].strip()
        if candidate_body:
            heading_text = line_text[:em_space_pos].strip()
            body_text = candidate_body
```

这些 marker 用 U+2003（EM SPACE）作标题/正文边界。

### 3.3 chapter：不拆

chapter 标题内部的 U+2003 是尾部填充，不是标题/正文边界。
`split_position = None, body_text = ""`。

### 3.4 body font + body 标点 → 正文

```python
has_body_punct = any(p in line_text for p in "：；。")
if font_bucket == "body" and has_body_punct:
    classification = "body"  # 即使有 U+2003 也不拆
```

`（1） 气道炎症形成机制：...` 有 U+2003 + body font + `：` → 正确归为 body。

## 4. 章节标题跨行合并

### 4.1 触发条件

chapter heading_candidate 后续行满足：
- 同 `pdf_page`
- 同 `raw_block_index`
- 同 `first_font`
- 同 `first_size`
- `marker is None`
- `classification == "body"`

### 4.2 合并操作

```python
merged_text = " ".join(text_parts)          # 空格连接
line_range = f"{first}-{last}"              # 行范围标记
raw_anchor = compute_raw_anchor(page, block, line_range, combined_spans)
```

- `heading_text`：合并后完整标题（如 `第四章 支气管哮喘`）
- `raw_line_index`：行范围（如 `"0-1"`）
- `raw_anchor`：基于合并行联合 spans 的指纹（joint SourceAnchor）
- `merged_from_lines`：记录原始行号列表
- 续行从 `lines` 列表移除

### 4.3 已验证实例

| scope | 合并前 | 合并后 |
|---|---|---|
| asthma | `第四章\u2003`(l0) + `支气管哮喘`(l1) | `第四章 支气管哮喘`, `l0-1` |
| tuberculosis | `第八章\u2003`(l0) + `肺结核`(l1) | `第八章 肺结核`, `l0-1` |

## 5. 歧义块处理

### 5.1 真正歧义块

body font + 短文本（≤40 字符）+ 无 body 标点 → `heading_candidate` 但不拆分。

```python
if font_bucket == "body" and not has_body_punct and len(line_text) <= 40:
    is_heading_candidate = True  # tentative
    split_position = None        # 不拆
```

### 5.2 生产处理

这些块标记为 `pending_review`，不自动进标题栈，需人工裁决。

已观察到 12 个（哮喘 9 + 肺结核 3），例如：
- 肺结核 p.114 `（1） 治疗方案`（9 字符，body font，无标点）

## 6. SourceScopeManifest Checksum

### 6.1 Canonical Serialization

```python
d = manifest_dict_without_checksum
canon = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
```

- 移除 `manifest_checksum` 字段
- `sort_keys=True`：键按字典序
- `separators=(",", ":")`：无多余空格
- `ensure_ascii=False`：保留中文

### 6.2 Checksum

```python
manifest_checksum = hashlib.sha256(canon.encode("utf-8")).hexdigest()
```

可重复计算：相同 manifest 内容 → 相同 checksum。

## 7. 输出结构

### 7.1 DocumentTree

```json
{
  "contract_version": "document_tree.v1",
  "textbook_version_id": "internal-medicine-10",
  "scope_id": "asthma",
  "catalog_path": ["第二篇", "第四章 支气管哮喘"],
  "nodes": [],
  "content_blocks": []
}
```

### 7.2 DocumentNode

```json
{
  "id": "dt:internal-medicine-10:asthma:{full_pdf_sha256}:{raw_anchor}",
  "parent_id": null,
  "depth": 0,
  "source_title": "第四章 支气管哮喘",
  "source_title_raw": "第四章\u2003\n支气管哮喘",
  "marker_kind": "chapter",
  "origin": "explicit_marker",
  "source_order": 0,
  "sibling_order": 0,
  "heading_anchor": {
    "pdf_page_number_1based": 62,
    "raw_block_index": 0,
    "raw_line_index": "0-1",
    "raw_anchor": "p62:b0:l0-1:{sha256[:32]}"
  },
  "content_block_ids": []
}
```

### 7.3 ContentBlock

```json
{
  "id": "cb:internal-medicine-10:asthma:0",
  "document_node_id": "dt:...",
  "block_type": "text_block",
  "raw_text": "教材原文",
  "source_order": 0,
  "source_anchor": {
    "pdf_page_number_1based": 62,
    "raw_block_index": 8,
    "raw_line_index": 0
  },
  "evidence_artifact_ids": []
}
```

## 8. 标题栈构建算法

```python
stack: list[DocumentNode] = []
source_order = 0
block_order = 0

for line in classified_lines:
    if line.classification != "heading_candidate":
        if line.classification == "body" and line.body_text:
            # 归属当前栈顶节点
            emit_content_block(stack[-1], line.body_text, block_order)
            block_order += 1
        continue

    # 新标题
    depth = determine_depth(line.marker, stack)
    parent = stack[depth - 1] if depth > 0 else None
    node = DocumentNode(
        id=compute_anchor_id(...),
        parent_id=parent.id if parent else None,
        depth=depth,
        source_title=line.heading_text,
        marker_kind=line.marker,
        origin="explicit_marker",
        source_order=source_order,
        sibling_order=next_sibling_order(parent),
        heading_anchor=line.raw_anchor,
    )
    stack = stack[:depth] + [node]
    source_order += 1

    if line.body_text:
        emit_content_block(node, line.body_text, block_order)
        block_order += 1
```

### 8.1 depth 推断（per-scope，非全局）

depth 由 marker kind 和当前栈状态推断，不是全局硬编码：

| marker | depth 推断规则 |
|---|---|
| `chapter` | 0（根） |
| `bracket` | 栈中最近 chapter 之后 → 1 |
| `chinese_parenthetical` | 栈中最近 bracket 之后 → 2 |
| `arabic_dot` | 栈中最近 chinese_parenthetical 之后 → 3 |

**注意**：此规则只适用于已验证的两个黄金 scope。其他 scope 的嵌套关系由
per-scope Transition Rule Table 确定（待人工审核）。

## 9. 验证清单

生产 splitter 实现后必须通过：

- [ ] raw anchors 跨运行稳定（`identical_order`, `identical_set`）
- [ ] 5 条黄金路径严格有序匹配（T1-T5）
- [ ] chapter 标题合并完整（`第四章 支气管哮喘`、`第八章 肺结核`）
- [ ] bracket 按 `】` 拆分（`【流行病学】` + body）
- [ ] 编号正文归 body（`arabic_parenthetical` 不进栈）
- [ ] 页眉不成为节点
- [ ] ID ≥128 bit（raw_anchor）+ 256 bit 源绑定（anchor_id）
- [ ] 结构不变量 INV1-INV10
- [ ] manifest checksum 可重复计算
