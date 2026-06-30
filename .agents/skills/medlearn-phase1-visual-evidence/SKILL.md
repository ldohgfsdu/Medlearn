---
name: medlearn-phase1-visual-evidence
description: >-
  Phase 1 visual evidence back-jump for MedLearn — export section page images,
  PageAsset + SourceLocator manifests, wire display contract evidence items,
  PageViewer with bboxNorm highlights, APK acceptance. Repo F:/ml only; not
  ingest LLM, graph, AI QA, or Supabase upload.
---

# medlearn-phase1-visual-evidence

## When to use

Use this skill when **implementing or modifying** the Phase 1 **visual evidence
back-jump** loop:

```text
ContentBlock / evidence item → SourceLocator → PageAsset → PageViewer → highlighted textbook page
```

**In scope:** page export, locator wiring, display contract fields, PageViewer,
evidence UI entry「教材原文」, local/APK verification.

**Out of scope:** semantic concept extraction, knowledge graph, Neo4j, UMLS/CMeSH,
AI QA, Feynman, Supabase upload, full-book export, unrelated App features.

**Orient first (read-only):**

- `docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md` — engineering spec (iron laws, shapes)
- `docs/PIPELINE_INDEX.md` — app knowledge bundle path
- `docs/adr/ADR-009-multimodal-evidence-artifacts.md` — anchors / artifacts
- `docs/PDF_PARSER_ARCHITECTURE.md` — `source-artifacts.json`, bbox
- Hermes umbrella (if available): `medlearn-knowledge-evidence`
- Ingestion changes to `originArtifactIds`: `.agents/skills/medlearn-review-ingestion/SKILL.md`

## Locator source priority (Phase 1 asthma)

```text
EV1 evidence item (display layer)
  ↓ evidence_items[].artifact_id
knowledge_nodes/**/*.evidence.json (authoritative locator for asthma pilot)
  ↓ page + bbox + raw_text
SourceLocator (bridge)
  ↓ pageAssetId + bboxNorm
PageViewer
```

1. **Current (asthma):** `display_contract` → `knowledge_nodes/.../支气管哮喘.evidence.json`
   — set `locatorSource: knowledge_node_evidence_json`. Do **not** fake `originArtifactIds`
   as parser `artifact-*` when absent.
2. **Future:** `originArtifactIds` → `pipeline_v3/*.source-artifacts.json` when lineage is wired.
3. **Forbidden:** fuzzy text matching; LLM bbox guessing.

Lineage export script: `scripts/export_phase1_evidence_lineage.py` →
`generated/phase1_visual_evidence/`.

## Goal

Minimum **offline APK-verifiable** loop:

1. Export textbook **page images** for the target section only.
2. Build **PageAsset** metadata (`pageLabel` ≠ `pdfPageIndex`).
3. Build **SourceLocator** records through the explicit-ID path selected by
   **Locator source priority** (`artifact_id` for the asthma bridge;
   `originArtifactIds` when parser lineage is wired).
4. Attach **`sourceLocatorIds`** (and related fields) to display contract evidence items.
5. Add in-app **PageViewer** (image + `bboxNorm` highlights).
6. Verify on **Android APK** (manual + scripted checks below).

**Phase 1 pilot section (fixed until expanded):**

```text
《内科学》第10版 — 第二篇 呼吸系统疾病 — 第四章 支气管哮喘
```

This is the current page-image implementation pilot. The Active Object accepts
a documented equivalent-original-context fallback for pulmonary tuberculosis;
validate its Document Tree and sampled fallback first. Apply this skill to a
pulmonary-tuberculosis page-image bundle only when that optional extension is
opened explicitly. Do not expand beyond the two named golden sections.

Display contract file (reference):

`generated/display_contracts/internal-medicine-10/第二篇_呼吸系统疾病__第四章_支气管哮喘.display_contract.json`

Bundle evidence pages are approximately **p.62–p.70**; acceptance case includes
**支气管舒张试验** (~ **p.64**). Do not expand to whole respiratory part in first
delivery.

## Inputs

| Input | Path / note |
|-------|-------------|
| PDF source | `textbook/内科学（第10版）.pdf` (not APK payload) |
| Parser artifacts | `generated/pipeline_v3/*.source-artifacts.json` |
| EV1 display contracts | `generated/display_contracts/internal-medicine-10/*.json` |
| App bundle chain | `PIPELINE_INDEX.md` → `ev1DisplayContracts.ts` → `textbookService.ts` |
| Evidence UI | `app/textbook/[sectionId]/unit/[unitId].tsx` (`EvidenceToggle`) |
| Page label ↔ PDF index map | **Required** — build or load explicit map; never assume `pageLabel === pdfPageIndex` |

## Outputs

| Output | Path |
|--------|------|
| Page images | `generated/textbooks/internal-medicine-10/pages/{pageLabel}.webp` |
| Page manifest | `generated/textbooks/internal-medicine-10/page_assets.json` |
| Locators (section) | `generated/phase1_visual_evidence/source_locators/internal-medicine-10/{sectionId}.source_locators_v0.json` |
| App page require map (Phase 1) | e.g. `constants/textbookPageAssets.ts` or generated manifest for Expo `require()` |
| Display contract / bundle | evidence items with `sourceLocatorIds`, `pageLabel`, and the declared explicit lineage ID |
| PageViewer route | accepts `pageAssetId` + `sourceLocatorIds` |

## Invariants (iron laws)

1. **Do not** use LLM to guess bbox.
2. **Do not** embed the full textbook PDF in the APK.
3. **`pageLabel`** (printed, user-facing) and **`pdfPageIndex`** (file index) are **separate**; coordinate system documented once project-wide.
4. **SourceLocator** must use an explicit ID join: `originArtifactIds` → parser
   `artifact-*`, or the documented asthma `artifact_id` →
   `knowledge_node_evidence_json` bridge. **No** fuzzy text / `source_order`
   guessing.
5. Raw PDF stays source asset; App consumes **page images + locator metadata**.
6. If bbox missing or low-confidence: **page-level or text fallback** — do not invent coordinates.
7. **Do not** change Document Tree / catalog semantics while adding PageViewer.

## Minimal data contract

### PageAsset

```ts
type PageAsset = {
  id: string
  textbookId: string
  textbookVersion: string
  pdfPageIndex: number
  pageLabel: string
  imageWidth: number
  imageHeight: number
  localAssetKey?: string
  imageUrl?: string
}
```

### SourceLocator

```ts
type SourceLocator = {
  id: string
  evidenceItemId: string
  locatorSource: 'knowledge_node_evidence_json' | 'pipeline_v3_source_artifacts'
  sourceEvidenceId?: string  // current asthma bridge
  sourceArtifactId?: string  // parser lineage path
  textbookId: string
  textbookVersion: string
  pdfPageIndex: number
  pageLabel: string
  pageAssetId: string
  bboxPdf?: [number, number, number, number]
  bboxNorm?: [number, number, number, number]
  rawText: string
  confidence: number
}
```

Exactly one source identifier must match the declared `locatorSource`.

### Evidence item (display contract / App)

Must include for clickable 原文:

```ts
{
  id: string
  text: string
  pageLabel: string
  artifact_id?: string          // current asthma bridge
  originArtifactIds?: string[]  // parser lineage path
  sourceLocatorIds?: string[]
}
```

At least one declared explicit lineage path must be present; never synthesize
one identifier type from the other.

App rendering: prefer **`bboxNorm`** on rendered image size. Export must apply
**PDF Y-axis (often bottom-left) → image top-left** when computing `bboxNorm`.

## Implementation steps

### Step 0 — Prerequisite gate

Run lineage audit / export (`audit_phase1_visual_evidence_origin.py`,
`export_phase1_evidence_lineage.py`). For **支气管哮喘**, locators may come from
`knowledge_nodes/*.evidence.json` when `originArtifactIds` are absent — see
**Locator source priority** above.

If neither explicit id join nor `originArtifactIds` can supply bbox: **stop**.
Do not proceed with LLM or text matching.

### Step 0.5 — Lineage export (before page assets)

- `pageLabel` ↔ `pdfPageIndex` map (0-based PyMuPDF for this book: `pdfPageIndex = int(pageLabel) - 1`, verified p.64 BDT).
- `SourceLocator` v0 JSON (currently 238 unique locators covering 275 asthma
  display evidence references).
- Coordinate calibration (`phase1_visual_evidence_coordinate_check/`); freeze **bboxNorm** rule after visual + span check.

### Step 1 — Export page assets

- Scope: **支气管哮喘 section pages only** (from section page range + label map).
- Produce `.webp` + `page_assets.json` with `imageWidth` / `imageHeight` per page.

### Step 2 — Build source locators

- Join through the declared locator source: asthma `artifact_id` →
  `knowledge_nodes/*.evidence.json`, or `originArtifactIds` →
  `source-artifacts` → PageAsset.
- Output `source_locators.json` with all required fields (see contract above).

### Step 3 — Merge into display contract / app bundle

- Each evidence item: `sourceLocatorIds`, `pageLabel`, preserved `rawText` / text.
- App must **not** read parser artifacts at runtime.

### Step 4 — PageViewer

- Input: `pageAssetId`, `sourceLocatorIds`.
- Render page image; overlay highlights from `bboxNorm` using **marker-style fill**
  (`backgroundColor: rgba(255, 230, 80, 0.45)`, optional `borderColor: rgba(230, 180, 0, 0.35)`,
  `borderWidth: 1`) — not outline-only boxes. **Never bake highlights into webp.**
- Show textbook title + `pageLabel`.
- Fallback: page-only if bbox unavailable.

**Calibration PNGs:** outline-only overlays are for engineering sign-off only;
product UI must use semi-transparent highlighter fill.

### Step 5 — Evidence UI

- Add「**教材原文 P{pageLabel}**」on evidence toggle; navigate to PageViewer.

### Step 6 — Expo / RN assets (Phase 1)

- Local bundled pages: static `require()` map keyed by `localAssetKey` — **not**
  runtime string paths like `uri: 'assets/...'`.

### Step 7 — Verify

Run automated checks (script or test) where possible; then APK manual pass.

## Acceptance criteria

Apply `checklists/phase1-golden-path-acceptance.md` for the target golden
section's App-side checks: catalog/search entry with correct breadcrumb,
textbook hierarchy, long-scroll usability, evidence control visibility,
return-to-page path, and `evidence_only` gating. The checklist is authoritative
for those; do not re-list them here.

**Automated / local (data contract — not covered by checklist)**

- [ ] Every clickable evidence item in pilot section has ≥1 SourceLocator.
- [ ] Every SourceLocator references an existing PageAsset.
- [ ] Every PageAsset image file exists on disk (or valid `imageUrl` in Phase 2).
- [ ] All `bboxNorm` values ∈ [0, 1] when present.
- [ ] Both `pageLabel` and `pdfPageIndex` present on PageAsset and SourceLocator.
- [ ] Sample join: 10 random pilot `evidence_items` resolve through the declared
  explicit-ID locator source; no fuzzy text matching.

**APK manual (PageViewer highlight precision — not covered by checklist)**

- [ ] Tap「教材原文」on **支气管舒张试验** (or equivalent evidence).
- [ ] PageViewer shows **correct printed page** (pageLabel).
- [ ] Highlight aligns with source paragraph.
- [ ] Highlighted region text matches evidence item text (allow OCR line-break diffs only).

## Non-goals

Do **not** implement in this active object:

- Knowledge graph UI, concept/relation extraction
- AI QA, Feynman
- Supabase upload / remote storage (Phase 2)
- Full textbook page export
- Neo4j, UMLS, CMeSH alignment
- Runtime PDF rendering
- LLM-based bbox guessing
- Document tree redesign

## Failure modes (stop and report)

| Condition | Action |
|-----------|--------|
| Missing `originArtifactIds` on evidence | Stop; fix ingest/export. For the asthma pilot's explicit `knowledge_node_evidence_json` bridge, follow Step 0 instead. |
| `ev1-*` cannot map to `artifact-*` | Stop; trace candidate → artifact lineage |
| `pageLabel` disagrees with printed book for pilot pages | Stop; fix page map |
| Unclear bbox coordinate origin | Stop; document transform + add unit test on one block |
| Missing page image dimensions | Stop; re-export with width/height |
| Expo dynamic asset path only | Stop; generate `require()` manifest |

## Suggested Codex prompt (copy)

```text
Use `.agents/skills/medlearn-phase1-visual-evidence/SKILL.md`.

Active object: phase1_document_tree_golden_path_validation

Goal: Minimum visual evidence back-jump for Internal Medicine v10「第四章 支气管哮喘」.

Scope: page assets, source locators, display contract locator IDs, PageViewer only.

Acceptance: APK — tap「教材原文」on 支气管舒张试验 → correct page image + bbox on source paragraph.
```

## Relation to other docs

```text
docs/PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md  → why + what (spec)
this SKILL.md                                 → how + forbid + accept
```
