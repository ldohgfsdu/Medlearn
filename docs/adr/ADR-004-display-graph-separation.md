# ADR-004: Display Hierarchy vs Semantic Graph Separation

**Status**: Accepted
**Date**: 2026-06-12
**Author**: Hermes Agent (following user direction)

## Context

Our knowledge base has two fundamentally different needs:

1. **Display / Navigation** (教材目录树)
   - 内科学
     - 呼吸系统疾病
       - COPD
       - 哮喘
       - 肺炎
   - Order, hierarchy, and presentation matter.

2. **Semantic Relations** (知识图谱)
   - COPD → 呼吸衰竭 (complication)
   - COPD → 肺心病 (complication)
   - COPD → 肺功能检查 (related_test)
   - These are associative, not hierarchical.

Previously we were overloading `parent_id` and `knowledge_points` table to serve both purposes. This leads to:

- Duplicate nodes
- Broken order
- Difficulty in reconstruction
- Future refactoring pain

## Decision

We will separate the two concerns completely.

### New Tables

**knowledge_chapters**
- Pure display hierarchy (book → chapter → section)
- Has `order_index`
- Parent-child is **only** for navigation

**chapter_nodes**
- Many-to-many between chapters and knowledge_points
- Has `display_order`
- This is the "table of contents" mapping

**knowledge_relations** (existing)
- Pure semantic graph
- No display semantics

**knowledge_points**
- Core fact
- Has `normalized_title`, `aliases`
- No `parent_id` for chapters

## Consequences

**Positive**
- Future export_book() becomes trivial
- Chapter order is preserved forever
- Graph can evolve independently
- No more "COPD belongs to both respiratory and pathology"
- Easy to support multiple views (by disease, by symptom, by VINDICATE)

**Negative**
- One more table
- Migration needed for existing data
- Slightly more complex queries

**Risks**
- If we ever mix chapter_nodes and knowledge_relations, we are back to square one.

## Implementation Notes

- Add `normalized_title` to knowledge_points with unique constraint (book_id, type, normalized_title)
- Add `chapter_nodes` table with display_order
- Add validation_queries.sql to detect orphans, duplicates, hierarchy breaks
- Update ingestion pipeline to populate both chapter_nodes and knowledge_relations
- Update snapshot and report generation to reflect both views

This ADR is the foundation for all future features (Feynman Tutor, Socratic Tutor, Case Simulator, Knowledge Graph UI).

**Approved by**: User (explicit direction in conversation)
**Implemented**: Yes (knowledge_chapters.sql, chapter_nodes.sql, validation_queries.sql)

**Next**: Run validation_queries.sql after next ingestion to verify structure.

## Clarification: Source Structure vs Normalized Labels

The same separation applies inside knowledge detail pages:

- normalized aspect labels support retrieval, intent matching, normalization, and quality checks
- source aspects from a specific textbook version determine visible titles, ordering, grouping, and child items
- each child item retains its own evidence, page reference, and source order

Normalized labels must never reconstruct or override the textbook-owned display hierarchy.
