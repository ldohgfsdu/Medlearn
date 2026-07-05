# ADR-008: Reuse Medical Concepts, Isolate Knowledge Detail Instances

**Status**: Accepted
**Date**: 2026-06-14

## Context

The same medical concept can appear in multiple textbook versions and multiple catalog locations. Each occurrence may emphasize different material, use different headings, and cite different source pages.

Sharing one mutable detail page across those occurrences would mix textbooks, flatten catalog context, and blur meaning.

## Decision

MedLearn separates:

- **Medical Concept**: a reusable semantic identity for the future knowledge graph
- **Knowledge Detail Instance**: a source-bound presentation instance owned by one textbook version and one catalog location

Each Knowledge Detail Instance independently owns:

- content kind
- source aspects
- source order
- display items
- evidence
- page references
- content status

A catalog node may contain multiple Knowledge Detail Instances. A detail instance
is unique by:

```text
textbook_version_id + catalog_node_id + content_identity_id
```

Display title is mutable presentation data and does not define identity.

When no stable cross-textbook concept exists, the system creates a textbook-local
Content Identity. It can later be associated with a Medical Concept without
changing the identity of the existing Knowledge Detail Instance.

Multiple Knowledge Detail Instances may link to the same Medical Concept. They must not share or merge mutable textbook detail content.

Any future cross-textbook comparison or synthesis is a separate page type. It must preserve links to the independent source detail instances and cannot replace them.

## Consequences

- Knowledge graph edges target Medical Concepts.
- Textbook navigation opens Knowledge Detail Instances.
- Source fidelity remains local to a textbook version and catalog location.
- Concept resolution and detail extraction become separate workflows.
- Cross-textbook synthesis requires explicit provenance for every statement.
- Renaming a displayed title does not break detail identity.
