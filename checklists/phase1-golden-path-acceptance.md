# Phase 1 Golden Path Acceptance (App)

**Active Object**: see `state/active_object.yaml`
**Sections** (no full-book scope):

- `第二篇_呼吸系统疾病__第四章_支气管哮喘`
- `第二篇_呼吸系统疾病__第八章_肺结核`

Validate in the **App**, not via pipeline JSON alone.

## Stability boundary

This checklist contains only stable acceptance questions. Counts, dates,
`[x]` marks, and pass/fail status are **not** kept here — they drift. Run the
existing verification scripts to produce timestamped evidence:

- `scripts/validate_phase1_pageviewer.py --check-export` — verifies the
  PageViewer require map, locator bundle, and clean-checkout asset tracking.
- `scripts/audit_phase1_visual_evidence_origin.py` — audits the explicit-ID
  lineage join (no fuzzy text matching).

Cite their JSON/text outputs for run evidence. Do not invent new report
scripts here; if a new report is needed, add the script first, then reference
it.

Current pipeline/app state for the golden sections lives in:

- `state/knowledge_ingestion.yaml` → `app_integration` (status, `ui_visible`,
  `textbook_reading_experience`, `page_image_return_path`, `golden_sections`)
- `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md` → lineage and page-asset status
- `generated/phase1_visual_evidence/` → locator bundle and validation outputs

## Asthma

- [ ] Section opens from catalog/search with correct breadcrumb / chapter context
- [ ] Hierarchy matches textbook (e.g. 实验室和其他检查 → 肺功能检查 → 通气/激发/舒张/PEF)
- [ ] Long scroll remains usable (no card-soup layout)
- [ ] Evidence control visible for sampled nodes
- [ ] Return to textbook page image (or documented fallback) works on sampled nodes
- [ ] `evidence_only` / raw evidence does not present as verified organized conclusion

## Pulmonary tuberculosis

- [ ] Classification / subsection tree renders recursively without OCR fragment pollution at top level
- [ ] Same evidence + return-path checks as asthma on sampled nodes
- [ ] Documented equivalent-original-context fallback (page-level or text) is present where a PageViewer bundle is not yet wired

## Out of scope for this checklist

- Full remote EV1 upload
- Concept graph or relation edges
- New chapter ingestion
- Case Simulator changes

## References

- `docs/architecture/phase1_phase2_gate.md`
- `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md`
- `state/knowledge_ingestion.yaml` → `app_integration.golden_sections`
