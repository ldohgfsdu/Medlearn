# Evidence And Copy Evaluation

Use for textbook ingestion, medical content, search excerpts, and SFT datasets.

## Source Fidelity

- [ ] Evidence is a continuous source span or preserved structured artifact.
- [ ] Evidence belongs to the declared textbook version and source scope.
- [ ] Page references belong to the same source edition.
- [ ] Tables preserve title, headers, relationships, notes, and page.
- [ ] Figures preserve image, title/caption, relationship, and page.
- [ ] Editorial splitting adds no facts, causality, scope, or certainty.

## Organized Copy

- [ ] The organized statement does not exceed the evidence.
- [ ] `content` is not merely an unlabeled copy of `evidence`.
- [ ] Source aspect title and ordering follow the textbook.
- [ ] Missing or combined aspects are not replaced with invented UI structure.
- [ ] Contradictory evidence hides the conclusion and enters review.
- [ ] Unsupported and `needs_review` conclusions are hidden from ordinary users.

## High Risk

- [ ] Dosage, contraindication, indication, first choice, treatment priority,
      critical values, and procedural steps are treated as high risk.
- [ ] Every core artifact for a high-risk item remains source verified.
- [ ] LLM output is candidate input only and cannot approve publication.
- [ ] Required human or senior review is recorded; absent review blocks the
      organized conclusion.

