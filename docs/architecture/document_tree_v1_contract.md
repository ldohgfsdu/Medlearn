# Document Tree v1 Contract

> 状态：设计草案，尚未成为 accepted ADR  
> 日期：2026-06-30  
> 作用域：`内科学（第10版）`的哮喘、肺结核黄金章节  
> 依据：PDF 实态核实、现有产物审计、ADR-004/005/006/007/009  
> 变更边界：本文只定义契约，不改变生成器、App、状态文件、数据库或远端数据

## 1. 已验证事实

| # | 事实 | 工作树证据 |
|---|---|---|
| F1 | 源 PDF 身份已核实 | 982 页；SHA-256 为 `C0BB559FA2C8448A54612F7EDF751C9342DF584D15CE90D0CF7E4F97BF852D78` |
| F2 | 两个现有 `evidence.json` 都没有印刷页码字段 | 哮喘 288 条、肺结核 494 条均只有 PDF 页字段，没有 `printed_page` / `printed_page_label` |
| F3 | 两个现有 `normalized.json` 都是平铺结果 | 哮喘 104 条、肺结核 343 条均为 `level=3`；标题均非空；均无 `parent_id` |
| F4 | 当前 extractor 没有标题栈 | 只维护单个 `current_heading`，不能表达多级父子路径 |
| F5 | 当前肺结核 evidence 丢失子标题 | 494 条的 `source_heading` 均为“第八章 肺结核” |
| F6 | 当前哮喘 evidence 拆散了组合标题 | “病因和发病机制”被拆成“病因”和“发病机制” |
| F7 | PDF 中存在可定位的显式结构标记 | 包括 `【…】`、`（一）`、`1.`、`（1）`、`1）`及独立版式标题 |
| F8 | catalog 只表达形式目录 | 有书、篇、章、节等标题层次，但没有稳定节点 ID、页码或 evidence 绑定 |
| F9 | 两个黄金章节的页面边界已核实 | 哮喘为 PDF 62–70 / 印刷 31–39；肺结核为 PDF 102–116 / 印刷 71–85；PDF 117 / 印刷 86 开始“第九章 肺癌” |
| F10 | 在两个黄金章节中观察到固定页差 | 已抽查页面均满足 `PDF 1-based 页码 - 印刷数字页码 = 31`；该结论只对已验证 scope 成立，不是全书公式 |

事实边界：

- F1–F10 是本草案可依赖的事实。
- 尚未验证全书所有版式、前置页、插页、非数字印刷页码及现有 bbox 坐标语义。
- 本文不把内存试解析结果写成已发布产物，也不据此声明覆盖完整。

## 2. 权威边界与三轴分离

```text
教材结构轴：TextbookVersion → SourceScope → DocumentNode → ContentBlock
医学审核轴：KnowledgeItem → EvidenceArtifact → VerificationDecision
检索语义轴：SemanticTag / ConceptMention → DocumentNode
```

约束：

- `TextbookVersion` 拥有目录、来源 scope 与 Document Tree；不得退回 series-owned 结构。
- source aspect 必须属于具体教材版本，不得跨版本静默复用。
- `SemanticTag`、关键词、治疗正则、标题相似度及 LLM 推断都不能决定 `parent_id`。
- `KnowledgeItem` 是教材原文之上的审核层，不能反向改写教材树。
- 搜索只导航到有来源锚点的教材内容，不生成开放式医学回答。
- Document Tree 保存来源结构与原文，不承载发布审核状态；发布与风险门禁仍由 `VerificationDecision` 等既有审核对象负责。

## 3. SourceScopeManifest v1

### 3.1 必需语义

每个 manifest 必须记录：

- 教材版本和源文件身份；
- scope 的目录路径、边界依据和有序来源片段；
- 纳入区域、明确排除项、待核缺口；
- PDF 页身份与印刷页标签的映射依据；
- `draft` / `reviewed` / `approved` / `invalidated` 审核状态；
- 审核人和审核时间；未审核时必须为 `null`，不得虚构；
- 可重复计算的 manifest checksum。

manifest 的 `approved` 只表示来源范围经审核，不等于医学内容已审核或可发布。

### 3.2 当前草案实例

以下是契约示例，不是已接受 manifest。catalog 当前没有稳定节点 ID，所以 v1 使用 `catalog_path`；不得伪造 `catalog_node_id`。

```json
{
  "manifest_version": "1",
  "textbook_version_id": "internal-medicine-10",
  "source_identity": {
    "book_title": "内科学（第10版）",
    "relative_path": "textbook/内科学（第10版）.pdf",
    "sha256": "C0BB559FA2C8448A54612F7EDF751C9342DF584D15CE90D0CF7E4F97BF852D78",
    "pdf_page_count": 982
  },
  "review_state": "draft",
  "reviewer": null,
  "reviewed_at": null,
  "coverage_claim": "not_evaluated",
  "scopes": [
    {
      "scope_id": "asthma",
      "catalog_path": ["第二篇", "第四章 支气管哮喘"],
      "boundary_basis": "chapter_title_through_page_before_next_chapter",
      "source_segments": [
        {
          "segment_order": 0,
          "pdf_page_start_1based": 62,
          "pdf_page_end_1based": 70,
          "printed_page_start_label": "31",
          "printed_page_end_label": "39"
        }
      ],
      "included_region_types": ["text", "table", "figure", "caption"],
      "explicit_exclusions": [],
      "pending_gaps": []
    },
    {
      "scope_id": "tuberculosis",
      "catalog_path": ["第二篇", "第八章 肺结核"],
      "boundary_basis": "chapter_title_through_page_before_next_chapter",
      "source_segments": [
        {
          "segment_order": 0,
          "pdf_page_start_1based": 102,
          "pdf_page_end_1based": 116,
          "printed_page_start_label": "71",
          "printed_page_end_label": "85"
        }
      ],
      "included_region_types": ["text", "table", "figure", "caption"],
      "explicit_exclusions": [],
      "pending_gaps": []
    }
  ],
  "page_mapping_evidence": {
    "status": "verified_for_listed_scopes_only",
    "observed_numeric_page_delta": 31,
    "samples": [
      {"pdf_page_1based": 62, "printed_page_label": "31"},
      {"pdf_page_1based": 64, "printed_page_label": "33"},
      {"pdf_page_1based": 102, "printed_page_label": "71"},
      {"pdf_page_1based": 107, "printed_page_label": "76"},
      {"pdf_page_1based": 117, "printed_page_label": "86"}
    ]
  },
  "manifest_checksum": "<computed-after-canonical-serialization>"
}
```

`pending_gaps: []` 只表示当前没有登记的缺口，不构成完整覆盖声明；只有完成 source-scope 审核后，`coverage_claim` 才能改变。

## 4. DocumentTree v1

### 4.1 持久化形态

v1 采用平铺节点表作为唯一持久化真相：

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

`children` 只能由 `parent_id` 和顺序字段在运行时派生，不与 `parent_id` 双重持久化。

### 4.2 DocumentNode

```json
{
  "id": "dt:<textbook-version>:<scope>:<structural-path>:<occurrence>",
  "parent_id": null,
  "depth": 0,
  "source_title": "第四章 支气管哮喘",
  "source_title_raw": "第四章 支气管哮喘",
  "marker_kind": "chapter",
  "origin": "layout_heading",
  "source_order": 0,
  "sibling_order": 0,
  "heading_anchor": {},
  "content_block_ids": []
}
```

字段规则：

| 字段 | 规则 |
|---|---|
| `id` | 必须确定性生成，并包含教材版本、scope、显式结构路径和同路径 occurrence；不得只对标题做 hash |
| `parent_id` | 根为 `null`；其余必须指向同 scope 内先出现的节点 |
| `depth` | 从父链派生；根为 0；不得直接由标记样式全局硬编码 |
| `source_title` | 保留教材标题文本；只允许契约明确的空白/断行规范化 |
| `source_title_raw` | 保存抽取时可回查的原始标题文本 |
| `marker_kind` | 记录来源标记样式，不等同于结构深度 |
| `origin` | 记录标题被识别的依据 |
| `source_order` | scope 内全局严格递增 |
| `sibling_order` | 同一 `parent_id` 下从 0 开始严格递增 |
| `heading_anchor` | 必须定位到实际来源；不能只有推断标签 |
| `content_block_ids` | 按来源顺序引用直属正文块，不包含子节点正文 |

允许的 `marker_kind`：

```text
chapter
bracket
chinese_parenthetical
arabic_dot
arabic_parenthetical
arabic_right_parenthesis
appendix
layout
```

允许的 `origin`：

```text
explicit_marker
layout_heading
manual_confirmed
```

`manual_confirmed` 只能确认源页上实际可见、可定位的标题，必须保存 `source_title_raw` 和 `heading_anchor`；它不能补写模板标题或医学概念。禁止 `llm_inferred`、`semantic_keyword`、`treatment_regex`、`title_similarity`。

不同标记在具体章节中的嵌套关系由显式结构路径和 scope 审核确定。不得声明 `【】=固定深度 2`、`（一）=固定深度 3` 之类的全书映射。

### 4.3 标识稳定性

最终 ID 编码算法仍待实现设计，但必须满足：

- 同一源文件、manifest、解析规则重复运行时 ID 不变；
- 同名标题按显式结构路径和 occurrence 区分；
- 标题文字的展示规范化不改变身份；
- scope 或教材版本不同，ID 必须不同；
- ID 冲突必须使生成失败，不能自动覆盖。

## 5. ContentBlock v1

```json
{
  "id": "cb:<textbook-version>:<scope>:<source-order>",
  "document_node_id": "dt:...",
  "block_type": "text_block",
  "raw_text": "教材原文",
  "source_order": 0,
  "source_anchor": {},
  "evidence_artifact_ids": []
}
```

允许的 `block_type`：

```text
text_block
table
table_row
table_cell
figure
caption
```

只有来源本身存在显式列表结构并保存对应标记与锚点时，后续版本才能增加 `list_item`。不得把表格行、单元格或普通段落仅凭语义改造成列表。

规则：

- `raw_text` 保存来源文本，不做医学改写。
- 每个 scope 内可见内容块必须恰好直属一个 DocumentNode。
- `source_order` 在 scope 内严格递增。
- `evidence_artifact_ids` 用于兼容既有 evidence，但现有 artifact 在补齐页码和坐标契约前不得被宣称与 v1 完全兼容。
- 表格、图、题注须保留相互关系和来源顺序，不能静默扁平化成正文。

## 6. PageIdentity 与 SourceAnchor v1

PDF 页身份和印刷页标签必须分别存储。印刷页标签是字符串，不能在通用契约中由固定偏移公式即时计算。

```json
{
  "pdf_page_number_1based": 62,
  "pdf_page_index_0based": 61,
  "printed_page_label": "31",
  "printed_page_mapping_origin": "scope_manifest_verified",
  "coordinate_space": "pdf_points",
  "page_width": 595.0,
  "page_height": 842.0,
  "bbox": [0.0, 0.0, 10.0, 10.0],
  "bbox_norm": null
}
```

约束：

- `pdf_page_index_0based = pdf_page_number_1based - 1`。
- `printed_page_label` 必须来自已验证页映射或页面解析；未知时为 `null`，不得猜测。
- `coordinate_space` 必须显式声明，可取 `pdf_points`、`pixel` 或 `normalized_0_1`。
- 非归一化坐标必须同时保存 `page_width` 和 `page_height`。
- `bbox_norm` 只能由已知尺寸转换得到，并验证四个值均在 `[0, 1]`。
- 现有 evidence 的 bbox 坐标空间尚未核实，不能直接标注为归一化坐标。

示例数值只说明字段形态，不是任何医学内容或现有 artifact 的真实定位数据。

## 7. 结构不变量与黄金 fixture

### 7.1 全局不变量

| # | 不变量 | 最低检查 |
|---|---|---|
| INV1 | 每个可见 ContentBlock 在 scope 内恰好直属一个 DocumentNode | 无孤儿、无重复归属 |
| INV2 | 每个非根节点的父节点存在于同 scope，且先于子节点 | 无悬空父节点、无环 |
| INV3 | 父子关系必须有可回查的显式结构证据 | `origin`、`source_title_raw`、`heading_anchor` 完整 |
| INV4 | 组合标题按来源原样保留 | 不按医学语义拆成多个同级模板节点 |
| INV5 | 来源中缺失的标题保持缺失 | 不补“诊断”“治疗”等统一模板节点 |
| INV6 | 全局和同级顺序可重复构建 | `source_order` 全局严格递增；`sibling_order` 同父严格递增 |
| INV7 | PDF 页与印刷页身份分别保存 | 不使用未验证的全书固定偏移 |
| INV8 | UI 可折叠、分块或分页，但不得改变标题、父子关系和来源顺序 | UI 输出可追溯回持久化树 |
| INV9 | 每个可见标题和内容块都有 SourceAnchor | 能定位回版本、PDF 页和页面区域 |
| INV10 | Document Tree 不携带或伪造医学发布状态 | 发布只由 KnowledgeItem / VerificationDecision 轴决定 |

### 7.2 当前黄金 fixture 断言

这些断言只适用于本轮两个章节，不是全书通用模板：

- 哮喘中“病因和发病机制”必须作为单一来源标题存在。
- 哮喘路径必须能表达“实验室和其他检查 → 肺功能检查 → 支气管舒张试验”。
- 肺结核路径必须能表达“结核病的分类标准 → 活动性结核病 → 按病变部位分类”。
- 肺结核路径必须保留“结核病的化学治疗”下来源中实际存在的下级标题。
- 两章的最后一个块不得越过各自 approved scope 边界。

fixture 中的每个断言都必须附 SourceAnchor；只看到标题文字而没有来源定位，不算通过。

## 8. 现有资产处理决策

| 现有部分 | v1 决策 | 边界 |
|---|---|---|
| `book_registry.py` / `book_id` | 保留 | 作为本地 TextbookVersion 身份起点，后续仍需与正式版本身份契约对齐 |
| `catalog.internal-medicine.json` | 保留 | 只提供形式目录路径；当前不宣称它已有稳定节点 ID |
| `EvidenceArtifact` / `evidence.json` | 兼容迁移 | 原文和来源顺序可复用；印刷页码及 bbox 坐标语义须补验 |
| `normalized.json` | 作为 KnowledgeItem 候选输入 | 不再充当教材结构真相 |
| `display_contract` | 派生视图 | 不作为父子关系事实源 |
| `textbookStudy.ts` 的 topic 分组 | 冻结扩展 | UI 迁移前保留现状，不再增加结构推断 |
| `TREATMENT_TERMS` 等语义正则 | 冻结扩展 | 不参与 Phase 1 Document Tree |
| `chapter_sections` | 不原样复用 | series-owned 结构不满足 ADR-005 的版本所有权 |

## 9. 下一阶段顺序

1. 人工确认本草案，必要时形成或更新 accepted ADR。
2. 为两个 scope 写正式 SourceScopeManifest，并完成 source-scope 审核。
3. 设计确定性 ID 编码和标题栈规则。
4. 扩展 extractor 生成 DocumentTree 和 ContentBlock；不同时改 UI。
5. 建立带 SourceAnchor 的黄金 fixture，执行全局不变量和章节断言。
6. 核实并迁移 bbox / PageIdentity 契约。
7. App 改为读取已验证树，移除第二轮 topic 结构推断。
8. 完成页面回跳、可访问性和 APK 验收。
9. 两章稳定后再设计数据库迁移；不得提前远端写入。

## 10. 仍未验证或未决定

- [ ] 现有 evidence bbox 的单位、原点、页面尺寸和归一化方式。
- [ ] 全书各版式标记的嵌套语法；当前只承诺两个黄金 scope。
- [ ] 确定性 ID 的最终编码、转义和迁移策略。
- [ ] catalog 稳定节点身份的生成与版本化方式。
- [ ] front matter、罗马数字页码、插页及其他非连续页映射是否需要独立 scope。
- [ ] 表格、图和题注在两个 scope 内的覆盖完整性。
- [ ] SourceScopeManifest canonical serialization 与 checksum 算法。

肺结核终点不再是待确认项：PDF 117 / 印刷 86 已核实为下一章“第九章 肺癌”的起点。
