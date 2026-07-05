# ADR-007: Separate Catalog Position, Content Identity, And Detail Page

**Status**: Accepted
**Date**: 2026-06-14

## Context

A textbook subsection can describe a disease, technique, classification, principle, treatment topic, overview, or general knowledge. Treating every catalog subsection as a disease creates false disease identities and forces unrelated content into diagnosis and treatment page structures.

Catalog position, medical identity, and presentation are related but distinct concerns.

## Decision

MedLearn separates:

```text
catalog_node → textbook position
content_identity → medical identity
detail_page → presentation capabilities
```

Supported content kinds include:

- disease
- technique
- classification
- principle
- treatment_topic
- overview
- general_knowledge

The four vocabularies remain separate:

```text
catalog_node.node_kind:
  part | chapter | section | subsection

content_identity.content_kind:
  disease | overview | technique | classification | principle |
  treatment_topic | general_knowledge

knowledge_detail.detail_page:
  disease_detail | knowledge_detail

knowledge_detail.content_status:
  replaced by independent access and coverage states
```

`overview` belongs only to Content Kind. It is not a catalog node kind, page
type, or status. A UI badge labeled "总览" is merely the display label for that
content kind.

Only headings represented by the textbook's formal table of contents, chapter
navigation, or other explicit navigation hierarchy become Catalog Nodes.
Body headings, aspect headings, table titles, and paragraph groups belong to a
Knowledge Detail as Source Aspects or Knowledge Items.

Only content explicitly identified as a disease receives a disease identity and opens a Disease Detail Page. Other content opens a Knowledge Detail Page.

Routing is based on Content Kind:

```text
if content_kind == disease → Disease Detail Page
else → Knowledge Detail Page
```

Both detail-page forms must:

- display source aspects rather than normalized aspect labels
- preserve source order
- bind every visible item to evidence
- allow unmodified textbook evidence to be expanded
- show source page references
- avoid merging content based only on normalized labels or semantic similarity

A Disease Detail Page adds disease-specific capabilities, not a mandatory set of aspects. Its visible aspect structure remains owned by the selected textbook version.

Knowledge Detail Instance state is split into independent axes:

```text
access_status:
  available | in_progress | unavailable

coverage_status:
  evidence_only | partial | complete
```

Access Status determines whether an ordinary user can open the detail.
Coverage Status communicates how much of the selected textbook scope has been
organized and verified. Knowledge Item Verification State determines whether an
individual display conclusion is visible.

An available evidence-only detail may display verified original text, tables,
figures, captions, and page references, but no organized conclusion. Partial
details show only verified items and omit empty or unverified aspects. Complete
details represent closed and audited source coverage for the declared textbook
scope. Complete does not mean that every source artifact has been converted into
a Knowledge Item. A complete detail may still contain evidence-only text,
tables, figures, and captions when those artifacts have been registered,
reviewed, and intentionally retained as source evidence.

Evidence Only has an explicit ordinary-user presentation:

```text
仅展示教材原始证据
该部分尚未形成可展示的审校整理结论
```

The notice remains visible in the title area or at the top of the evidence
region. Evidence-only pages do not render numbered knowledge points, summary
cards, first-choice or recommended-plan UI, or any other conclusion-shaped
component. Text, tables, figures, and captions retain original-evidence labels.

The page shows textbook version, catalog path, and page range. Search results
use the user-facing label "仅原始证据". Internal terms such as Needs Review,
Rule Version, and Coverage Status remain outside ordinary-user UI.

Evidence-only search results may show a hit excerpt only when it is labeled
"原文片段". A text excerpt is a continuous slice of `source_verified` source
text. It is never rewritten, summarized, or completed by an LLM, and ellipsis
must not alter the sentence's meaning.

A table result includes the table title and relevant row and column context
rather than an isolated cell. A figure result provides a thumbnail entry,
figure title, or original caption; OCR text does not replace the image, and
model interpretation is not presented as a caption. Selecting the result
navigates to the Evidence Artifact and page location rather than generating a
medical answer.

`coverage_status = complete` is a controlled audit result. It requires all of
the following:

- the Knowledge Detail Instance has an approved Source Scope Manifest
- all text, tables, figures, and captions in the declared source scope are
  registered as Evidence Artifacts
- every explicit Source Aspect in that scope has been processed
- every Evidence Artifact has a recorded disposition: supports a Verified
  Knowledge Item, remains evidence-only, or is excluded for an explicit,
  auditable reason
- no unresolved Source Uncertain, Evidence Conflict, or Needs Review state
  remains, and no Unsupported conclusion is exposed to ordinary users
- a deterministic coverage audit passes
- a human reviewer confirms the result

An LLM may extract Evidence Artifacts, suggest Source Aspects and Knowledge
Items, and flag suspected conflicts or uncertainty. It must not directly set
Coverage Status to Complete.

If the Source Scope Manifest is invalidated by a source-file checksum or boundary
change, an existing Complete status is immediately demoted to Partial. Coverage
audit and human confirmation must then be repeated.

The previous overloaded `content_status` field must migrate to these two axes.

## Consequences

- Catalog nodes require an identity association rather than an implicit disease interpretation.
- Search results can label the content kind.
- Routing depends on content identity.
- Non-disease topics receive a first-class evidence-backed detail experience.
- Disease-specific training and reasoning capabilities remain unavailable to non-disease content unless separately designed.
- Existing routing based on `node_type = overview` must migrate to content identity.
- Existing routing and badges based on one overloaded `content_status` must
  migrate to Access Status plus Coverage Status.
- Complete status requires auditable source-scope accounting and human approval;
  it cannot be inferred from item count or asserted by a model.
- Coverage Status cannot reach Complete without an approved Source Scope
  Manifest.
- Evidence-only pages and search results must clearly distinguish source lookup
  from reviewed medical conclusions.
