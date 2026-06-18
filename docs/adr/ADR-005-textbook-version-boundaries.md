# ADR-005: Textbook Versions Own Their Catalog And Evidence

**Status**: Accepted
**Date**: 2026-06-14

## Context

MedLearn needs to support current, older, and future editions of the same medical textbook. Editions can change their catalog structure, wording, knowledge coverage, recommendations, and page references.

Storing one shared catalog or one shared body of content for a textbook series would make source attribution ambiguous and could silently replace one edition with another.

## Decision

Each textbook version owns an independent:

- catalog skeleton
- catalog nodes, including their parent relationships and source order
- knowledge detail
- textbook evidence
- page reference

A textbook series groups related versions but does not own version-specific content.

Medical topics across versions may be associated for comparison. That association must not merge, overwrite, or substitute the source content of either version.

Catalog nodes are independently created for every textbook version even when
their visible path text is identical. A catalog node represents a concrete
position inside one textbook version, not a reusable path string.

Cross-version catalog relationships are stored separately and may describe:

- same position
- renamed
- moved
- split
- merged

Those relationships support comparison and migration assistance only. They do
not permit shared detail content, evidence, page ranges, source order, or parent
hierarchy.

The previous model that keyed `chapter_sections` by textbook series and attached
multiple version IDs to one shared node is superseded by this decision.

## Consequences

- Users can intentionally select and browse a specific edition.
- Page references remain trustworthy within their source edition.
- Version changes can be compared without losing historical content.
- Catalog and content records must use textbook version identity as an ownership boundary.
- Cross-version comparison requires explicit associations rather than shared mutable content.
- Existing series-owned catalog records require migration to version-owned nodes.
