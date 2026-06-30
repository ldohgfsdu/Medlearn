# Phase 1：视觉证据回跳闭环（工程规格）

> **状态**：已采纳（与 V1 Source Asset / Evidence Anchor / PageAsset 设计一致）  
> **试点范围**：仅《内科学》第10版 **第四章 支气管哮喘** 一整节（非整篇呼吸系统）  
> **Golden Path 边界**：哮喘执行页图试点；肺结核先验结构树，并可用带页码的教材原文展开作为 `equivalent original textbook context` fallback。肺结核页图属于后续显式扩展，不是关闭当前 Active Object 的硬门。  
> **当前 bundle 页码标签**：`page_label` / `page_start` 约 **p.62–p.70**（验收条目含「支气管舒张试验」约 **p.64**）  
> **执行手册**：`.agents/skills/medlearn-phase1-visual-evidence/SKILL.md`

## 目标闭环

```text
PDF（不进 APK）
  → 本地导出页图 webp + page_assets.json
  → source-artifacts：page + bbox + text + parser artifact_id
  → display_contract evidence_items：显式 lineage ID（哮喘 bridge 用 artifact_id；未来用 originArtifactIds）
  → export source_locators.json（显式映射，禁止模糊匹配）
  → App：教材原文 → PageViewer（bboxNorm 高亮）
```

## 四条铁律

1. **不用 LLM 猜 bbox**（定位来自 parser；LLM 只参与 ingest 整理）。
2. **不把整本 PDF 打进 APK**（Phase 1 仅试点节页图；正式按需下载 + 缓存）。
3. **ev1 evidence 必须走显式 ID 绑定**：目标路径是 `originArtifactIds`
   （parser `artifact-*` → EV1）；当前哮喘 bridge 使用 display
   `artifact_id` 精确连接 `knowledge_node_evidence_json`。禁止在两者之间伪造 ID。
4. **`pageLabel` 与 `pdfPageIndex` 必须分开**（印刷页码 ≠ PDF 文件页索引）。

## 五条实现收紧

### 1. 页码双字段

| 字段 | 含义 |
|------|------|
| `pdfPageIndex` | PDF 文件真实页（0-based PyMuPDF，全项目固定） |
| `pageLabel` | 教材印刷页码，给用户看（如 `"33"`） |
| `pageAssetId` | 页图资产 id（如 `page_internal_medicine_10_33`） |

### 2. bbox 坐标系

Phase 1 同时存：

- `bboxPdf`: `[x0, y0, x1, y1]`（PDF 点坐标）
- `bboxNorm`: `[x0, y0, x1, y1]`（相对页宽高的 0–1）
- `pageWidth` / `pageHeight`（导出 webp 的像素尺寸）

App **优先用 `bboxNorm`**。坐标变换已于 Phase 6A 在哮喘 scope 冻结为 **top-left 原点、不翻转 Y 轴**：`bboxNorm = [x0/w, y0/h, x1/w, y1/h]`（PyMuPDF 的 bbox 即左上原点）。export 脚本中通过 BDT 已知块单测覆盖。

### 3. SourceLocator 显式映射

禁止仅靠 `text` / `source_order` 反查 bbox。

```ts
// EvidenceItem（display contract / App）
{
  id: string
  text: string
  pageLabel: string
  artifact_id?: string          // 当前哮喘 bridge
  originArtifactIds?: string[]  // parser artifact_id，未来标准路径（可多条）
  sourceLocatorIds?: string[]
}

// SourceLocator（export 产物）
{
  id: string
  evidenceItemId: string
  locatorSource: 'knowledge_node_evidence_json' | 'pipeline_v3_source_artifacts'
  sourceEvidenceId?: string  // 当前哮喘 bridge
  sourceArtifactId?: string  // parser lineage 标准路径
  textbookId: string
  textbookVersion: string
  pdfPageIndex: number
  pageLabel: string
  pageAssetId: string
  bboxPdf: [number, number, number, number]
  bboxNorm: [number, number, number, number]
  rawText: string
  confidence: number
}

// PageAsset
{
  id: string
  textbookId: string
  textbookVersion: string
  pageLabel: string
  pdfPageIndex: number
  imageWidth: number
  imageHeight: number
  localAssetKey: string   // Phase 1：require map 的 key
  imageUrl?: string       // Phase 2：远程
}
```

两种显式 lineage 路径至少存在一种，并由 `locatorSource` 声明；SourceLocator
中恰好一个 source id 必须与该声明匹配。禁止文本模糊匹配。

**管线缺口 / 哮喘 pilot 实际路径（2026-06-25）**：display contract 无 `originArtifactIds`；
哮喘节 **权威定位源** 为 `generated/knowledge_nodes/.../支气管哮喘.evidence.json`
（`artifact_id` 显式 join → `locator.page` + `locator.bbox`）。SourceLocator 为桥接层，字段
`locatorSource: knowledge_node_evidence_json`。未来可再接 `pipeline_v3` parser `artifact-*`。
产物：`scripts/export_phase1_evidence_lineage.py`。

### 4. 试点范围

- **做**：`第二篇_呼吸系统疾病__第四章_支气管哮喘` + 其 `page_start`/`page_end` 对应页图 + 本节全部 evidence 的 locators。
- **可随后做**：肺结核通过 Document Tree 与抽样原文 fallback 验收后，如另行开启页图扩展，再以同样的数据契约补齐该节页图。
- **不做**：整篇呼吸系统、全书的 SourceLocator、远程 Storage（Phase 2）。

### 5. Expo / RN 资源

Phase 1 构建时生成 manifest，例如：

```ts
export const pageAssets: Record<string, number> = {
  im10_page_31: require('../assets/textbooks/im10/pages/31.webp'),
  // ... keys are im10_page_{printedPageLabel}
}
```

禁止依赖运行时字符串 `uri: 'assets/...'` 访问打包资源。Phase 2 再 `imageUrl` + 本地缓存。

## 最小开工顺序

| 步骤 | 脚本/交付物 | 输入 | 输出 |
|------|-------------|------|------|
| 1 | `export-page-assets` | PDF + 哮喘节 `pageLabel` 范围 + 页码映射表 | `webp/` + `page_assets.json` |
| 2 | `export-source-locators` | `display_contract` + 声明的显式 lineage 源 + `page_assets` | `source_locators.json` |
| 3 | `merge-locators-into-display-contract` | locators | `evidence_items.sourceLocatorIds`（或内联 locator ref） |
| 4 | `PageViewer` 屏 | page manifest + locators | 页图 + `bboxNorm` 高亮 |
| 5 | APK 验收 | 真机 | 点「支气管舒张试验」→ **教材 p.33** 页图 → 黄框对齐段落 |

## 与现有 App bundle 路径的关系

在 `docs/PIPELINE_INDEX.md` 的 `build-app-knowledge-bundle` 之后串联：

```text
… → export_ev1_display_contracts_ts.py → constants/ev1DisplayContracts.ts
  → [NEW] export-page-assets（哮喘节）
  → [NEW] export-source-locators
  → [NEW] merge + export pageAsset manifest TS
  → services/textbookService + PageViewer
```

## 验收标准

- [ ] 随机 10 条本节 `evidence_items`：能通过声明的显式 ID 源解析到 `bboxNorm`，无文本模糊匹配
- [ ] 每条 locator：`pageAsset` 文件存在或 `localAssetKey` 可 require
- [ ] 真机 3 条人工抽检（含支气管舒张试验）：高亮框与原文段落一致
- [ ] 无 LLM 运行时调用、无整本 PDF 内置
## Current Verification Status (2026-06-25)

- Static PageViewer wiring: PASS via `python scripts/validate_phase1_pageviewer.py`.
- Metro export asset check: PASS via `python scripts/validate_phase1_pageviewer.py --check-export`; Android export metadata contains 9 bundled `.webp` page assets.
- Release APK build in this agent run: NOT DONE. `JAVA_HOME` is not set on this host, so device/APK acceptance remains a manual follow-up.
- Manual APK check: build locally, install the APK, then open bronchial asthma -> source evidence -> textbook source P33 (printed pageLabel) and verify the highlighter aligns with the source paragraph.
