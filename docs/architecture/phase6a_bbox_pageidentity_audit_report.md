# Phase 6A: bbox / PageIdentity Read-Only Audit Report

> 作用域：哮喘 PDF 62-70（肺结核保留 equivalent-context fallback）
> 日期：2026-06-30
> 状态：核查通过（所有结论区分已验证与待核项）

## 1. 执行摘要

| 项 | 结论 |
|---|---|
| PageIdentity map | 零歧义，已验证 |
| evidence.json page_start 语义 | 存 PDF 1-based 页码（62-70），非印刷页码 |
| bbox 坐标系 | top-left 原点，无需 Y 翻转 |
| 显式 ID 连接 | 281/281 通过 artifact_id 精确 join |
| 10 条抽样 | 10/10 全通过 |
| 校准图 | BDT no_flip + y_flip 已生成 |

## 2. 已验证事实

### F1: PageIdentity map 零歧义

| PDF 1-based | pdfPageIndex (0-based) | printed pageLabel |
|---|---|---|
| 62 | 61 | "31" |
| 63 | 62 | "32" |
| 64 | 63 | "33" |
| 65 | 64 | "34" |
| 66 | 65 | "35" |
| 67 | 66 | "36" |
| 68 | 67 | "37" |
| 69 | 68 | "38" |
| 70 | 69 | "39" |

- 页差 `PDF 1-based - printed = 31`，与 ADR-011 / SourceScopeManifest 一致
- 9 个印刷页码均在页面文本中找到
- 页面尺寸一致：575.43 × 793.70 pt（A4-ish）

### F2: evidence.json page_start 存 PDF 1-based 页码

- 288 条 evidence 的 `page_start` 范围：62-70（全部在 PDF 1-based 范围内）
- 不在印刷页码范围 31-39 内
- `locator.page` 与 `page_start` 一致

### F3: bbox 坐标系 = top-left 原点，无需 Y 翻转

BDT（支气管舒张试验）校准：
- evidence bbox: `[79.37, 200.34, 495.34, 212.14]`（块级，全宽 × 单行高）
- rawdict needle bbox: `[93.57, 200.34, 302.66, 211.x]`（针文本级，包含在块内）
- Y 值精确匹配（200.34），needle 完全包含在 evidence bbox 内
- Y 翻转后 needle 不包含在 bbox 内 → 确认 top-left 原点
- **bboxNorm 公式**：`[x0/w, y0/h, x1/w, y1/h]`（无翻转）

### F4: 显式 ID 连接 281/281 通过（严格门禁）

- locator_source: `knowledge_node_evidence_json`
- join field: `artifact_id`（display contract → evidence.json）
- 281 条 display evidence refs 全部携带 `artifact_id` 并精确解析到 evidence.json
- **严格门禁**：`resolved == total == 281`、`unresolved == 0`、`all_have_artifact_id == true`
- 任一条件不满足即 `status = BLOCKED`，进入 overall blockers
- **无模糊文本匹配**

### F5: 10 条抽样全通过（bbox 区域文本验证）

每条检查 7 项：
1. `page_start == locator.page` ✓
2. `page_start` 在哮喘 PDF 范围内 ✓
3. bbox 存在且 4 值 ✓
4. bbox 在页面边界内 ✓
5. **raw_text 片段在 bbox 区域文本内**（rawdict char 交集，非整页匹配）✓
6. bboxNorm 全在 `[0, 1]` ✓
7. bbox 区域文本非空 ✓

抽样覆盖 5 个不同页面（PDF 63, 65, 66, 68, 70），满足"至少覆盖多个页面"要求，支持冻结全 scope 的 top-left 变换。

抽样失败会进入 `overall_status` blockers，导致整体 BLOCKED。

## 3. 现有脚本问题（已识别，未修改）

### P1: `export_phase1_evidence_lineage.py` 页码字段混淆

```python
# 现有脚本（line 20, 47, 71）:
PAGE_LABELS = list(range(62, 71))  # 实际是 PDF 1-based 页码
idx = label - 1                     # pdfPageIndex 计算正确
mappingRule: "pdfPageIndex_0based = int(pageLabel) - 1"  # 字段名错误
```

**问题**：把 PDF 1-based 页码（62-70）命名为 `pageLabel`，但实际 pageLabel 是印刷页码（31-39）。

**影响**：
- `pdfPageIndex` 计算正确（`62 - 1 = 61`）
- 但 `pageLabel` 字段值错误（存 "62" 而非 "31"）
- SourceLocator 的 `pageLabel` 字段会显示错误的页码给用户

**修复要求**（待后续阶段执行）：
- `pageLabel` 改为印刷页码 `str(pdf_page_1based - 31)`
- `pdfPageIndex` 保持 `pdf_page_1based - 1`
- evidence.json 的 `page_start` 保持 PDF 1-based（这是源数据，不改）

### P2: parser lineage 路径 NO-GO（已知）

- 281 条 evidence 无 `originArtifactIds`
- ev1-* ID 不在 parser `artifact-*` 索引中
- 当前走哮喘 bridge（`artifact_id → evidence.json`），符合规范

## 4. 待核项

- [ ] BDT 校准图需人工视觉确认（no_flip 黄框覆盖 BDT 段落）
- [ ] 现有 `export_phase1_evidence_lineage.py` 的 pageLabel 修正（未在本阶段执行）
- [ ] bbox 精度：块级 bbox 覆盖整行，非精确段落级（当前可接受，PageViewer 用块级高亮）
- [ ] 肺结核 scope 的 bbox/PageIdentity 未核查（按指令保留 fallback）

## 5. PageIdentity / bbox 契约

### 5.1 PageIdentity

```json
{
  "pdf_page_number_1based": 64,
  "pdf_page_index_0based": 63,
  "printed_page_label": "33",
  "page_delta": 31,
  "page_width_pt": 575.43,
  "page_height_pt": 793.70
}
```

约束：
- `pdf_page_index_0based = pdf_page_number_1based - 1`
- `printed_page_label = str(pdf_page_number_1based - 31)`（仅哮喘 scope 验证）
- 印刷页码必须来自已验证页映射，不得用全书固定公式

### 5.2 bbox 坐标系

```json
{
  "coordinate_space": "pdf_points",
  "origin": "top_left",
  "y_axis": "downward (PyMuPDF text extraction default)",
  "bbox": [x0, y0, x1, y1],
  "bboxNorm": "[x0/page_width, y0/page_height, x1/page_width, y1/page_height]"
}
```

约束：
- **无需 Y 翻转**：evidence.json 的 bbox 已是 top-left 原点
- `bboxNorm` 直接用 `[x/w, y/h, x/w, y/h]`
- 所有 `bboxNorm` 值在 `[0, 1]` 范围内（10 条抽样验证）
- bbox 为块级（覆盖整行宽度），非精确 span 级

### 5.3 显式 ID 连接

```text
display_contract.evidence_items[].artifact_id
  → knowledge_nodes/*.evidence.json artifacts[].id
  → locator.page + locator.bbox
```

- locator_source: `knowledge_node_evidence_json`
- 禁止模糊文本匹配
- 禁止从 `originArtifactIds` 伪造（当前缺失，走 bridge）

## 6. 自动测试

25 项测试通过：
- 12 core（PageIdentity 常量、page 语义逻辑、ID join 严格门禁逻辑、bbox 包含逻辑）
- 13 PDF 集成（audit 运行、页身份、bbox 坐标系、ID join 281/281 严格断言、10 条抽样含 bbox 区域文本验证、多页覆盖、校准图）

## 7. 边界遵守

- 未修改 Document Tree、display contract、App、APK、数据库、远端
- 未修改生产 extractor
- 未修改现有 lineage 脚本（仅识别问题，待后续修复）
- 肺结核保留 equivalent-context fallback
