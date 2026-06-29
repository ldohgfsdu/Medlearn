# Phase 1 Golden Path — 差距表（App 教材消费）

**Active Object**: `phase1_document_tree_golden_path_validation`  
**生成**: 2026-06-29（对照仓库实态，非 pipeline 自述）  
**黄金样本**: 哮喘 `第二篇_呼吸系统疾病__第四章_支气管哮喘` · 肺结核 `第二篇_呼吸系统疾病__第八章_肺结核`

---

## 一句话结论

| 维度 | 状态 |
|------|------|
| **数据管线（哮喘页图 + locator）** | ✅ 275 条 evidence 引用全部接线；238 个唯一 locator；9 页 |
| **App 代码（PageViewer + 回跳入口）** | ✅ 已接线；荧光笔样式符合规格 |
| **产品验收（真机 / 叠图签字 / 勾选表）** | 🔴 **未闭环** — P0 叠图待主人签字；APK 手测未记录 |
| **肺结核黄金路径** | ✅ Web 运行时结构树通过；✅ p.107 / p.109 教材原文 fallback 通过；无 page-image bundle（非当前硬门） |

> 当前瓶颈不是「缺数据」，而是 **「哮喘页图链已写好但未完成 P0 / APK 验收」**；肺结核 Web golden path 已通过。

---

## 端到端链路对照

```text
Catalog / Map → Section → Study Unit → 原文展开 → 「教材原文 Pxx」→ PageViewer → webp + bboxNorm 高亮
```

### 哮喘（第四章）

| 环节 | 期望 | 仓库实态 | 差距 / 动作 |
|------|------|----------|-------------|
| Document Tree 数据源 | `EV1_DISPLAY_CONTRACT_SECTIONS` | `constants/ev1DisplayContracts.ts` 含哮喘节 | ✅ |
| 层级呈现（肺功能子项） | 实验室和其他检查 → 肺功能 → 通气/BPT/BDT/PEF | `utils/textbookStudy.ts`：`structuredSourceItemsForNode` + `pulmonaryFunctionChildrenFromEvidence` | 🟡 需 App/测试勾选确认，非仅代码存在 |
| Locator 绑定 | 每条 evidence → `sourceLocatorIds` | merge 报告：**275/275 引用已接线**、**238 个唯一 locator**、缺失 0；BDT p64 示例 `loc_ev1_57068078e29b9153d70d` | ✅ |
| 页图资产 | p62–70 webp + `require()` | `assets/.../pages/*.webp` ×9；`constants/phase1PageImageAssets.ts` | ✅ |
| Bundle 运行时 | `PHASE1_VISUAL_EVIDENCE_BUNDLE` | `constants/phase1VisualEvidenceBundle.ts`（仅哮喘 `sectionId`） | ✅ |
| 回跳入口 | 哮喘节 + 有 locator 时显示按钮 | `[unitId].tsx` → `/textbook/page-viewer` | ✅ |
| PageViewer | 干净 webp + 运行时高亮 | `page-viewer.tsx` + `PageViewerHighlightOverlay` `rgba(255,230,80,0.45)` | ✅ |
| P0 坐标签字 | 主人确认 BDT 框在 **64.webp** 上 | `generated/reports/phase1_step3_gate_visual_signoff.md` **⏳ 待确认** | 🔴 **阻塞「验收完成」表述** |
| 真机 APK | 哮喘 → 舒张试验 → P64 对齐 | `phase1_pageviewer_visual_evidence_summary.md`：validation PASS，**APK built: no** | 🔴 需本地 build + 手测并填 checklist |

### 肺结核（第八章）

| 环节 | 期望 | 仓库实态 | 差距 / 动作 |
|------|------|----------|-------------|
| EV1 阅读 | 分类树递归、少 OCR 碎片顶栏 | display contract：**293 nodes**，26 grouped，50 evidence_only；2026-06-29 Web 运行时展开分类树，无 console error | ✅ 结构树运行时验收通过 |
| Locator / 页图 | 可选的哮喘同规格扩展 | **无** `phase1` bundle / `source_locators` / App webp | ⚪ 当前 Active Object 接受教材原文 fallback；页图需另行开 scope |
| 原文 fallback | 抽样 evidence 返回等价教材上下文 | `EvidenceToggle` 展示页码与绑定原文 | ✅ p.107 / p.109 两个抽样通过 |

#### 肺结核运行时证据（2026-06-29）

- 路径：电子教材 → 第二篇 呼吸系统疾病 → 第八章 肺结核 → 进入知识点详情 → 展开「分类」。
- 分类标题和子类型可见，未出现 OCR 碎片污染顶层。
- DOM 几何位置证明递归缩进：活动性结核病 `x=52`、按病变部位分类 `x=96`、原发性肺结核 `x=135`；复治肺结核同样位于三级缩进。
- 分类展开后的内部滚动高度为 `3161px`（`720px` viewport），折叠组仍保留，不是平铺 card soup。
- 浏览器 console error / warning：`0`。
- 教材原文 fallback 抽样通过：潜伏感染者 `p.107`、复治肺结核 `p.109` 均显示页码、绑定原文及可逆展开/收起状态。
- 肺结核 page-image / PageViewer 仍未实现，但按当前 Active Object 属可选扩展，不阻塞 Web golden path。

---

## 关键文件索引（改哪里）

| 用途 | 路径 |
|------|------|
| 章节列表 / 详情数据 | `services/textbookService.ts` |
| 教材结构 → StudyUnit / 嵌套 | `utils/textbookStudy.ts` |
| 知识地图入口 | `app/map.tsx` |
| 章 → 小节列表 | `app/textbook/[sectionId].tsx` |
| 电子教材阅读 + 证据按钮 | `app/textbook/[sectionId]/unit/[unitId].tsx` |
| 页图 + 高亮 | `app/textbook/page-viewer.tsx`，`components/textbook/PageViewerHighlightOverlay.tsx` |
| Locator 解析 | `services/phase1VisualEvidenceService.ts` |
| 管线：页图 | `scripts/export_phase1_page_assets.py` |
| 管线：locator | `scripts/export_phase1_evidence_lineage.py` |
| 管线：bundle | `scripts/merge_phase1_locators_bundle.py` |
| 管线：拷进 App | `scripts/sync_phase1_page_assets_to_app.py` |
| 验收勾选 | `checklists/phase1-golden-path-acceptance.md` |

---

## 建议执行顺序（与 state blocked 一致）

1. **主人 P0**：打开 `generated/reports/phase1_visual_evidence_coordinate_check/asthma_p64_on_exported_webp_highlighter.png`（或 bboxNorm 工程图），回复 **「叠图 OK」** → 解锁「坐标链可信」表述。  
2. **哮喘 App 验收**：`npx expo start` 或 `npm run build:android:preview:local` → 按 checklist 勾哮喘 7 项。  
3. **肺结核**：Web Document Tree + 教材原文 fallback 已通过；仅在另行开启 page-image scope 时运行第八章页码范围的 phase1 脚本。  
4. **自动化补强**（可选）：`tests/phase1VisualEvidenceService.test.js` 锁 BDT locator → `buildPageViewerPayload` 非 null。  
5. **B 通过后**：才走 blocked 的 `knowledge_remote_upload_validation`（canary 哮喘+结核 → 再扩量）。

---

## 明确不做（当前 Active Object）

- 全量远端 upload（19961 nodes）
- Concept / Graph / AI 聊天
- 病例线功能扩展
- 全书 phase1 页图

---

## 相关报告（只读）

- `generated/reports/phase1_merge_locators_bundle_summary.md`
- `generated/reports/phase1_pageviewer_visual_evidence_summary.md`
- `generated/reports/phase1_step3_gate_visual_signoff.md`
- `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md`
