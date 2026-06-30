# Phase 1 Golden Path Acceptance (App)

**Active Object**: `phase1_document_tree_golden_path_validation`  
**Sections only** (no full-book scope):

- `第二篇_呼吸系统疾病__第四章_支气管哮喘`
- `第二篇_呼吸系统疾病__第八章_肺结核`

Validate in the **App**, not via pipeline JSON alone.

**差距表（链路实态）**: [`phase1_golden_path_gap_analysis.md`](../docs/architecture/phase1_golden_path_gap_analysis.md)

## Pipeline vs App（2026-06-29）

| 样本 | 数据链 | App 阅读 | 页图回跳 | 验收 |
|------|--------|----------|----------|------|
| 哮喘 | ✅ 275 refs / 238 unique locators / 9 pages | ✅ 已接线 | ✅ 代码就绪 | 🔴 P0 签字 + APK |
| 肺结核 | ✅ EV1 contract | ✅ Web 运行时结构树通过 | ✅ p.107 / p.109 原文 fallback | ✅ Web golden path |

“先结构树”是实施顺序，不降低最终验收范围；肺结核在 Active Object
关闭前仍需完成下方抽样 evidence + return-path 检查。

## Asthma

- [ ] Section opens from catalog/search with correct breadcrumb / chapter context
- [ ] Hierarchy matches textbook (e.g. 实验室和其他检查 → 肺功能检查 → 通气/激发/舒张/PEF)
- [ ] Long scroll remains usable (no card-soup layout)
- [ ] Evidence control visible for sampled nodes
- [ ] Return to textbook page image (or documented fallback) works on sampled nodes
- [ ] `evidence_only` / raw evidence does not present as verified organized conclusion

## Pulmonary tuberculosis

- [x] Classification / subsection tree renders recursively without OCR fragment pollution at top level
  - 2026-06-29 Web runtime: catalog → pulmonary tuberculosis unit → classification expanded.
  - Visible hierarchy indentation: activity TB `x=52`, classification axis `x=96`, subtype `x=135`; no console errors.
- [x] Same evidence + return-path checks as asthma on sampled nodes
  - 2026-06-29 Web runtime: expanded textbook-original fallback for latent infection `p.107` and recurrent pulmonary tuberculosis `p.109`.
  - Both samples exposed the page label, exact bound source text, and working expand/collapse state. A PageViewer bundle remains an optional later extension.

## Out of scope for this checklist

- Full remote EV1 upload
- Concept graph or relation edges
- New chapter ingestion
- Case Simulator changes

## References

- `docs/architecture/phase1_phase2_gate.md`
- `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md`
- `state/knowledge_ingestion.yaml` → `app_integration.golden_sections`
