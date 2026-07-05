# ADR-006: Textbooks Own Knowledge Aspect Structure

**Status**: Accepted
**Date**: 2026-06-14

## Context

Medical textbooks do not describe every disease with one universal set of headings. Some combine topics such as etiology and pathogenesis, omit common headings, or introduce topic-specific sections.

A product-defined aspect template would make pages look uniform, but it would also invent structure that the source textbook did not provide and weaken source trust.

## Decision

Knowledge detail structure follows the selected textbook version.

- Explicit textbook headings define the knowledge aspects.
- Source Aspects belong inside a Knowledge Detail and never become catalog
  hierarchy merely because they are visually emphasized in body text.
- Combined textbook headings remain combined.
- Missing aspects remain absent.
- Topic-specific aspects remain available.
- Product-level aspect labels may assist matching and navigation, but must not create, split, merge, or display a structure that the textbook does not express.
- Model output is never authoritative when it conflicts with the textbook.
- Normalized aspect labels are internal metadata for retrieval, intent matching, normalization, and quality checks.
- Detail-page titles, order, grouping, and structure come from source aspects in the selected textbook version.
- Repeated material may be organized under one source aspect only when it belongs to the same textbook version, the same catalog object, and the textbook explicitly places it within that aspect.
- Each child item retains its own evidence, page reference, and source order.
- Semantic similarity alone is never sufficient grounds for merging source material.
- Unnumbered source prose may be split into numbered display items only when it continuously enumerates multiple explicit points within the same source aspect.
- Each editorially split item must map directly to a continuous source fragment and retain its evidence relationship.
- Editorial splitting must not add content, change scope, tone, or causality, or turn an inference into a textbook conclusion.
- When a stable split is not possible, the original paragraph remains intact.
- Item origin is recorded as `explicit_numbered`, `explicit_list`, `editorial_split`, or `original_paragraph`.

## Consequences

- Disease pages may have different aspect sets and ordering.
- Cross-disease visual consistency is secondary to textbook fidelity.
- Extraction must preserve source headings and their order.
- Search intent matching needs aliases that navigate to source-owned aspects without renaming them.
- Any inferred aspect requires evidence and must remain subordinate to the source structure.
- Storage and UI models must preserve both normalized labels and source-owned display structure.
- The learning layer may improve mobile readability while the evidence layer preserves unmodified textbook text.
