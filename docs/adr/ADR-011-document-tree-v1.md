# ADR-011: Document Tree v1 As The Structural Source Of Truth

**Status**: Accepted
**Date**: 2026-06-30

## Context

MedLearn currently derives its on-screen chapter structure from two
independent heuristic layers: a Python display-contract generator and a
TypeScript topic grouping in `textbookStudy.ts`. Neither layer is
grounded in a single canonical tree. Read-only audits of the asthma
(PDF 62-70) and tuberculosis (PDF 102-116) golden chapters confirmed
the cost of this approach:

- Combined headings such as "病因和发病机制" were split into separate
  sibling nodes.
- Tuberculosis evidence lost all sub-headings; 494 artifacts all carried
  `source_heading = "第八章 肺结核"`.
- The extractor maintained only a single `current_heading` and could not
  express multi-level parent-child paths.
- Node identity was unstable because it was derived from classified
  structural paths rather than raw source anchors.
- `normalized.json` was flat (all `level=3`, no `parent_id`) yet was
  treated as if it represented structure.
- Catalog (`catalog.internal-medicine.json`) expressed only formal
  paths, with no stable node IDs, page references, or evidence binding.

ADR-005 already established that textbook versions own their catalog and
evidence. ADR-004 separated display hierarchy from the semantic graph.
ADR-006 made textbooks own knowledge aspect structure. The missing piece
is a single structural source of truth owned by each textbook version
that preserves source hierarchy, binds evidence, and does not encode
medical review state.

A read-only heading signal auditor was built and accepted
(commit `6062e85a4`) to verify the proposed contract against the real
PDF. The audit confirmed:

- Raw anchors based on pre-classification span payloads are stable
  across runs (`identical_order`, `identical_set`).
- Five golden paths pass strict ordered node matching.
- Bracket headings split correctly at the closing `】` (real PDF uses
  ordinary space, not U+2003, after the bracket).
- Chapter titles spanning two lines merge with a joint SourceAnchor.
- U+2003 is not a generic heading/body boundary; body font plus body
  punctuation overrides it for numbered body blocks.
- 128-bit raw anchors (32 hex of SHA-256) and full 256-bit PDF checksum
  binding satisfy the identifier requirements.

## Decision

Adopt **Document Tree v1** as the single canonical structural source of
truth for each textbook version scope. The detailed specification lives
in `docs/architecture/document_tree_v1_contract.md`; this ADR records
the binding decisions and their boundaries.

### 1. Three-axis separation

```text
教材结构轴：TextbookVersion → SourceScope → DocumentNode → ContentBlock
医学审核轴：KnowledgeItem → EvidenceArtifact → VerificationDecision
检索语义轴：SemanticTag / ConceptMention → DocumentNode
```

The Document Tree owns source structure and original text only. It does
not carry medical publication status. Semantic tags, keywords, treatment
regex, title similarity, and LLM inference may not determine
`parent_id`. Medical review may not rewrite the tree. Search navigates
to grounded textbook content; it does not answer open-ended medical
questions.

### 2. Flat node table with derived children

The persistent form is a flat node table per scope. `children` are
derived at runtime from `parent_id` and order fields. `children` and
`parent_id` are never double-persisted.

### 3. DocumentNode and ContentBlock

Each `DocumentNode` records `source_title`, `source_title_raw`,
`marker_kind`, `origin`, `source_order`, `sibling_order`,
`heading_anchor`, and `content_block_ids`. `marker_kind` records the
source marker style (`chapter`, `bracket`, `chinese_parenthetical`,
`arabic_dot`, `arabic_parenthetical`, `arabic_right_parenthesis`,
`appendix`, `layout`) but does not equal structural depth. Allowed
`origin` values are `explicit_marker`, `layout_heading`, and
`manual_confirmed`. `llm_inferred`, `semantic_keyword`,
`treatment_regex`, and `title_similarity` are prohibited.

Each `ContentBlock` belongs to exactly one `DocumentNode` within its
scope. `raw_text` preserves source text without medical rewriting.
Tables, figures, and captions preserve their mutual relationships and
source order.

### 4. Deterministic identifiers binding the full source checksum

Identifiers are deterministic and bind the full source PDF checksum:

- `raw_anchor = p{pdf_page}:b{block}:l{line}:{sha256(span_payload)[:32]}`
  — 128 bits of fingerprint, computed from a pre-classification
  normalized JSON span array, independent of `str(float)` and
  classification results.
- `anchor_id = dt:{textbook_version_id}:{scope_id}:{full_pdf_sha256}:{raw_anchor}`
  — retains the full 256-bit PDF SHA-256 without truncation.

Same source file, manifest, and parse rules produce identical IDs.
Different scope or textbook version produces different IDs. ID
collision fails generation; it never silently overwrites.

### 5. SourceScopeManifest gates scope boundaries

Each scope is governed by a `SourceScopeManifest` with
`draft` / `reviewed` / `approved` / `invalidated` review states.
Reviewer and reviewed_at are `null` until a human reviews; they are
never fabricated. `approved` only means the source range was reviewed;
it does not mean medical content is reviewed or publishable.

### 6. PageIdentity and SourceAnchor

PDF page identity and printed page label are stored separately. Printed
page label is a string from verified page mapping or page parsing, never
guessed from a global offset formula. Non-normalized coordinates declare
their `coordinate_space` and carry `page_width`/`page_height`. Existing
evidence bbox coordinate semantics remain unverified until a separate
contract audit.

### 7. Structural invariants

The contract defines ten invariants (INV1-INV10), including: no orphan
content blocks, no dangling parents, parentage requires explicit
structural evidence, combined headings are preserved as-is, missing
headings stay missing, orders are reproducible, PDF and printed page
identities are separate, UI cannot alter titles or parentage, every
visible heading and block has a SourceAnchor, and the tree carries no
medical publication state.

### 8. Existing asset handling

- `book_registry.py` / `book_id`: retained as local TextbookVersion
  identity seed.
- `catalog.internal-medicine.json`: retained for formal path input only.
- `EvidenceArtifact` / `evidence.json`: compatible migration; printed
  page and bbox semantics require verification.
- `normalized.json`: candidate input for KnowledgeItem; no longer the
  structural truth.
- `display_contract`: derived view, not a parentage source.
- `textbookStudy.ts` topic grouping and `TREATMENT_TERMS` regex: frozen,
  no further structural inference.
- `chapter_sections`: not reused; series-owned structure violates
  ADR-005.

## Scope Boundary

This decision applies to Document Tree v1. The accepted scope is the
asthma and tuberculosis golden chapters of `内科学（第10版）`. It does
not claim full-book coverage. Per-scope transition rules, font bucket
completeness, ambiguous blocks, bbox coordinate semantics, and
table/figure coverage remain open items listed in the contract and audit
report. They do not block this decision; they gate later production
rollout.

This ADR does not modify the production extractor, UI, state files, or
remote data. Those changes follow in later stages under their own scope.

## Consequences

- The two heuristic structure layers (Python display-contract generator
  and TypeScript topic grouping) become derived views, not sources of
  parentage. They are frozen for extension, not deleted in this ADR.
- `normalized.json` is no longer treated as structural truth; it becomes
  a candidate input to the medical review axis.
- The production extractor must be extended to emit `DocumentTree` and
  `ContentBlock` records using the accepted identifier and split rules.
  UI changes are not done in the same step.
- Each scope requires a human-approved `SourceScopeManifest` before its
  tree is considered authoritative.
- Identifier stability depends on raw span payloads; splitter rule
  changes do not invalidate IDs, but source PDF or extraction mode
  changes do.
- Cross-version structure comparison requires explicit associations;
  shared mutable structure remains prohibited per ADR-005.
- The medical review axis (`KnowledgeItem`, `VerificationDecision`)
  remains the sole authority for publication and risk gating; the tree
  only provides grounded source content.
- Later stages (formal manifests, ID encoding spec, extractor extension,
  fixture validation, bbox contract, UI migration, DB migration) proceed
  in order; database migration is not started until the two golden
  scopes are stable.

## References

- `docs/architecture/document_tree_v1_contract.md` — full specification
- `docs/architecture/heading_signal_audit_report.md` — audit evidence
- `scripts/textbook_pipeline/heading_signal_auditor.py` — auditor
- ADR-004 (display vs semantic separation)
- ADR-005 (textbook version ownership)
- ADR-006 (textbook-owned knowledge aspects)
- ADR-007 (catalog, content, detail separation)
- ADR-009 (multimodal evidence artifacts)
