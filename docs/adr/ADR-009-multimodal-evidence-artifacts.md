# ADR-009: Preserve Text, Tables, Figures, And Captions As Evidence Artifacts

**Status**: Accepted
**Date**: 2026-06-14

## Context

Medical textbooks communicate important knowledge through prose, tables,
figures, imaging, flowcharts, captions, and notes. Flattening those sources into
plain text destroys table headers, row and column meaning, image relationships,
and the ability to verify the original source.

## Decision

Every Knowledge Detail Instance declares its evidence boundary through a Source
Scope Manifest before complete coverage can be audited. The manifest records:

- textbook version, catalog node, and knowledge detail identity
- page range and optional start and end anchors
- included source regions for text, tables, figures, and captions
- excluded regions with explicit, auditable reasons
- source file identity and checksum
- boundary basis: catalog title, layout boundary, manual selection, or a mixture
- review state: draft, reviewed, approved, or invalidated
- reviewer identity and review time when applicable

Scope boundaries must come from textbook navigation, explicit layout boundaries,
or manual selection. Disease-name frequency and LLM semantic inference cannot
define the boundary. When one Catalog Node contains multiple Knowledge Detail
Instances, each instance receives an independent manifest rather than relying on
a model to partition one mixed source range.

Only an approved manifest may support `coverage_status = complete`. Unclear
boundaries cap coverage at Partial. A change to the source checksum, page range,
anchors, included regions, or excluded regions invalidates the manifest and its
previous coverage audit. The LLM may assist extraction inside an approved scope,
but cannot approve or define that scope.

A Source Scope Manifest may contain multiple ordered Source Segments when the
detail's source is genuinely discontinuous, such as a continued table or a
separated caption. Every segment records:

- segment order in textbook reading order
- independent page and anchor boundaries
- an explicit inclusion reason
- approval state
- included regions ordered within the segment

Material skipped between segments must be explicitly excluded with a reason,
assigned to another Knowledge Detail Instance, or marked pending. Pending or
unaccounted gaps block Complete coverage. Segment and region order follow
textbook reading order, never extraction time. Semantic similarity cannot join
discontinuous ranges; a human must approve every such segment.

Cross-chapter and other out-of-scope references are represented as External
Evidence References. They record the target textbook version, optional catalog
node, target page range, and a reference reason such as `see_also`,
`appendix_reference`, `table_reference`, `figure_reference`, or
`cross_chapter_reference`. They remain outside the current manifest and do not
count toward its source coverage. A continued table or structurally attached
caption may be an approved Source Segment; a textbook instruction to see another
chapter remains an external reference.

An External Evidence Reference cannot by itself support a Verified Knowledge
Item in the referring detail. Verification requires at least one
`source_verified` Evidence Artifact inside the current Source Scope Manifest.
External references may add context and navigation, but cannot substitute for
local evidence or import a conclusion from the target detail.

When the local source says only "see chapter/table/figure", the referring detail
shows that reference without generating the target content as a local Knowledge
Item. Following the reference opens the target Knowledge Detail Instance, whose
own manifest, evidence artifacts, page references, and verification states
govern its content.

Coverage audit may confirm that an external reference appearing inside the
local source scope has been faithfully registered. The target detail's content,
verification, and coverage do not participate in the referring detail's
Coverage Status or Knowledge Item Verification State.

External Evidence References carry an independent state:

- `resolved`: the verified target may be opened, with its textbook version,
  catalog path, and page reference displayed
- `unresolved`: preserve the original "see..." text, label the target as pending,
  and provide no guessed navigation
- `broken`: show that the target is invalid, disable navigation, and send the
  reference to editorial review
- `circular`: preserve a valid mutual-reference relationship while preventing
  automatic chained navigation

Unresolved and Broken references do not erase the fact that the local reference
was registered, but they block Complete coverage. Circular references do not
block Complete when every target in the cycle is valid.

Resolution requires matching textbook version, catalog node, page or anchor
information, or an explicit human-confirmed relationship. Title similarity,
semantic similarity, and LLM inference cannot automatically mark a reference
Resolved. A broken target must never silently fall back to a similar chapter,
same-named concept, or another textbook version.

External Evidence Reference stores the current state and current target.
External Reference Revision is an immutable append-only audit record for every
change to the target detail, manifest, anchor, page range, or reference state.
Each revision records old and new values, the change reason, actor, and time.
Existing revision records must never be updated in place.

A referenced Knowledge Detail Instance, Source Scope Manifest, or anchor cannot
be physically deleted. It may only be archived or invalidated. When a target
becomes invalid, the reference first becomes Broken. A replacement target may be
assigned only after human confirmation, with a new revision appended.

Textbook-version upgrades do not migrate existing references. A reference in an
older edition remains attached to that edition; a newer edition establishes its
own reference relationship. Historical audit must reconstruct the exact
textbook version, catalog path, page range, and anchor visible at the time of
each revision.

Source Anchors have permanent identities independent of OCR text, page
coordinates, page number, and content fingerprints. Those values are locating
attributes, not identity keys.

Re-OCR, recropping, source-file replacement, and manual relocation append a
Source Anchor Revision rather than replacing prior anchor data. Each revision
records source file and checksum, page number, region geometry, content
fingerprint, optional OCR text, revision reason, confidence, and review
metadata.

When the source checksum is unchanged and the region match is exact, a revision
may mark the anchor Relocated. When the checksum changes, matching signals such
as page number, layout neighborhood, figure or table number, surrounding-text
fingerprints, and content fingerprint may only create an Anchor Relocation
Candidate. They cannot automatically preserve identity; a human must approve
the relocation.

An anchor that cannot be stably matched becomes Uncertain. Its Evidence
Artifacts can no longer support Verified Knowledge Items, related Source Scope
Manifests are invalidated or downgraded, dependent External Evidence References
may become Broken, and Coverage Status cannot remain Complete. Anchor revisions
and relocation reviews are append-only audit records.

Uncertain anchors trigger dependency-scoped degradation rather than automatic
whole-page removal:

- directly dependent Evidence Artifacts become `source_uncertain`
- a Knowledge Item supported only by those artifacts becomes `needs_review` and
  is hidden from ordinary users
- an ordinary Knowledge Item may remain Verified when other local
  `source_verified` artifacts still provide sufficient support
- the affected Knowledge Detail Instance becomes Partial
- unaffected Verified items and trustworthy evidence-only artifacts remain
  visible
- Access Status becomes In Progress only when no trustworthy user-visible
  content remains

High-risk medical items use a stricter rule. Dosage, contraindication,
indication, first-choice treatment, treatment priority, critical values, and
procedural steps become Needs Review when any core evidence becomes uncertain,
even if other verified evidence remains.

Knowledge Items carry a controlled Risk Class of Standard or High Risk. High
Risk is assigned by versioned, human-maintained Risk Rules or by an explicit
human decision. Rules may match source aspect, keyword, content kind, item type,
or a manual designation. LLM output may suggest a class but cannot lower High
Risk to Standard or decide publication safety.

Dosage, contraindication, indication, treatment priority, first-choice
treatment, critical values, and procedural steps default to High Risk until
classification is complete. A Risk Rule version change triggers reevaluation
with a new append-only audit record rather than modifying historical decisions.

Evidence bindings carry one of three roles:

- `core`: its loss, uncertainty, or conflict may change the conclusion,
  applicability, or safety
- `corroborating`: additional support that is not independently required for
  publication
- `contextual`: background that does not establish the conclusion

Core roles require human confirmation; an LLM may only nominate candidates. A
Standard item requires at least one local `source_verified` supporting artifact.
A High Risk item requires every Core artifact to remain `source_verified`. Any
Core artifact with uncertainty, conflict, or a broken dependency makes the item
Needs Review and hides it.

Evidence Role cannot suppress contradiction. A Core, Corroborating, or
Contextual artifact that explicitly opposes the current conclusion triggers
Evidence Conflict.

Publication checks run in this order:

1. detect opposing evidence; if present, mark Evidence Conflict, hide the
   organized conclusion, preserve both sides, and require human review
2. require local `source_verified` supporting evidence; otherwise mark
   Unsupported or Needs Review
3. for High Risk items, require every Core artifact to remain reliable
4. publish only when no conflict exists and all evidence requirements pass

Risk Class changes strictness, not contradiction handling. Standard items do
not receive a conflict exception. High Risk items add stricter Core-evidence
requirements. Apparent conflict may become conditional items only when the
textbook explicitly states the differing applicability conditions; a model
cannot infer those conditions.

Contradiction detection compares structured Evidence Claims rather than vector
similarity, keyword mismatch, or an LLM's subjective judgment. A Claim records:

- subject
- predicate
- value
- applicability conditions
- polarity: affirm or deny
- optional source time or stage

A confirmed Evidence Conflict requires two confirmed sources to address the
same subject, medical predicate, and applicability conditions while making
incompatible assertions through polarity, value, dosage, priority, or another
semantically exclusive field.

"First choice A" and "optional B" are not inherently contradictory. "First
choice A" and "first choice B" may conflict only under the same applicability
conditions. Explicitly different populations, disease stages, treatment stages,
severity, resistance status, or other source-stated conditions become separate
conditional items.

When claim scope or applicability is unclear, the system records Suspected
Conflict and sets the related item to Needs Review rather than declaring
Evidence Conflict. The conclusion remains hidden from ordinary users until
human review. A model cannot invent missing conditions or resolve ambiguity.

One Evidence Artifact may yield multiple Evidence Claims. Each Claim must carry
a precise Source Locator for a text span, table row, column or cell, figure
region, or caption span, together with its Source Anchor. Subject, predicate,
value, applicability conditions, and polarity cannot exceed what that exact
source location states.

Multiple Claims may share a source location, but co-location does not create an
inference relationship between them. When stable separation is impossible, the
system retains a Composite Claim and marks it Needs Review rather than forcing
an atomic split.

Claim State is Candidate, Confirmed, Needs Review, or Invalidated. An LLM may
only propose Candidate Claims. Only Claims confirmed by deterministic rules or
human review participate in Evidence Conflict detection, Knowledge Item
Verified decisions, or High Risk review. Candidate and Needs Review Claims are
excluded from those automated decisions.

Evidence Claim is a stable logical identity. Evidence Claim Revision stores a
specific version of its subject, predicate, value, applicability conditions,
polarity, optional source time or stage, and Source Locator. Confirmed Claim
content is immutable. Every correction appends a revision with its previous
revision, reason, actor, time, and confirmation metadata.

Until a new revision is confirmed, the prior revision remains the Current
Effective Version. After confirmation, the prior revision becomes Superseded
and the system reruns Evidence Conflict detection, Knowledge Item verification,
Risk Class review, and Evidence Role review.

A Source Locator change requires revalidation of the associated Source Anchor,
Source Scope Manifest, and Evidence Artifact. Conflict detection, Verified
decisions, and High Risk review may use only the Confirmed Current Claim
Revision. Draft, Candidate, Superseded, Needs Review, and Invalidated revisions
are excluded. Historical audit must reconstruct the exact Claim Revision used at
any prior point.

Verification Decisions are immutable, versioned records for Knowledge Items,
Evidence Claims, and Knowledge Detail Instances. A decision records its type,
target, Claim Revision IDs, optional Evidence Artifact IDs, Rule Version,
result, source, time, reason, state, and replacement relationship.

Every Claim Revision, evidence-state, or applicable-rule change creates a new
Verification Decision. An old decision may become Superseded or Invalidated,
but its result cannot be edited or deleted. The current page reads only the
latest Active decision. Historical audit must recover the exact Claim Revision,
rule version, result, and publication reason used at any prior time.

Confirmation of a new Claim Revision immediately invalidates any Active
Verified decision that depends on the old revision. The related Knowledge Item
becomes Needs Review until a new decision completes. High Risk items cannot
continue displaying under an old decision. New Verified status must be produced
from the Current Claim Revision and current rules.

An `llm_suggested` result is review input, not a publishable Active Verification
Decision. Ordinary-user publication requires a decision produced by an allowed
deterministic rule or a human reviewer.

Editorial tooling must expose the complete impact chain from Uncertain Anchor to
Evidence Artifact, Knowledge Item, Source Aspect, and Knowledge Detail Instance.
Restoration requires a new coverage audit after the anchor or evidence is
reviewed.

Evidence is represented as independent Evidence Artifacts:

- `text_block`
- `table`
- `figure`
- `caption`
- `table_row`
- `table_cell` when necessary

A Knowledge Item may reference one or more Evidence Artifacts.

Table-derived items must preserve:

- table title
- headers
- row and column relationships
- notes
- page references
- a path back to the original table

Figure-derived evidence must preserve:

- original image
- figure title
- caption
- page reference
- relationship between image and accompanying text

Search excerpts preserve the same artifact semantics. Text hits use only a
continuous `source_verified` source span and are labeled as original excerpts,
without LLM rewriting or completion. Table hits retain the table title and
relevant row-column context. Figure hits expose the original figure, title, or
caption rather than substituting OCR text or model interpretation. Search
selection navigates to the source artifact; it does not generate a conclusion.

Reliable flowcharts may be organized into display steps. When a table, figure,
or flowchart cannot be parsed reliably, it remains an original Evidence Artifact
and does not generate a Knowledge Item.

Knowledge Items carry a verification state:

- `verified`
- `evidence_conflict`
- `unsupported`
- `needs_review`

Evidence Artifacts independently carry a source verification state:

- `source_verified`
- `source_uncertain`
- `source_invalid`

When multiple Evidence Artifacts inside one textbook version and one Knowledge
Detail Instance contradict the same claim:

- no source type automatically overrides another
- the display conclusion is hidden
- all conflicting source artifacts, types, and page references remain available
- an Evidence Conflict review record is created
- the model must not explain or resolve the conflict

The item may be split into conditional items only when the textbook explicitly
provides the differing applicability conditions. Those conditions must themselves
be evidenced.

Ordinary-user visibility is:

- `verified`: show the display conclusion and expandable evidence
- `evidence_conflict`: hide the conclusion, show a review warning and conflicting source artifacts
- `unsupported`: hide completely
- `needs_review`: hide completely

Editorial and review interfaces may inspect every state.

A Source Aspect with no ordinary-user-visible item or independently displayable
verified source artifact is omitted rather than rendered as an empty card.

A `source_verified` artifact may be shown even when no Knowledge Item can be
reliably derived. It must remain labeled and presented as original textbook
evidence, never as a verified summary or standard knowledge point.

## Consequences

- Evidence storage cannot remain a single text field plus page range.
- Extraction must preserve document structure and media assets.
- Ingestion must create and approve source-scope manifests before claiming
  complete coverage.
- Source-scope storage must preserve ordered discontinuous segments and keep
  external references outside local coverage accounting.
- The detail page needs evidence renderers for text, tables, and figures.
- OCR text never replaces the original visual artifact.
- Quality gates must block derived items that lose required table or figure context.
- Conflict review becomes a first-class ingestion and editorial workflow.
- Reference revisions require immutable append-only audit storage, and
  referenced source objects require archival rather than physical deletion.
- Source anchors require permanent identities, append-only location revisions,
  and human-reviewed relocation when source files change.
- Anchor uncertainty requires dependency-aware publication degradation and a
  stricter policy for high-risk medical items.
- Risk classification and Core evidence roles require versioned rules,
  append-only review history, and human control.
- Confirmed Claims require immutable revisions and dependency reevaluation
  whenever the Current Effective Version changes.
- Verification results require immutable decisions, immediate invalidation on
  dependency change, and current-rule reevaluation before republication.
