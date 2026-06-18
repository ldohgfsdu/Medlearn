---
name: medlearn-validate-medical-content
description: Validate MedLearn medical statements, textbook summaries, evidence bindings, page references, case content, risk classes, and publication states. Use whenever a change adds or modifies medical content, treatment information, dosage, contraindications, critical values, procedural steps, source evidence, or review decisions.
---

# Validate Medical Content

This skill evaluates grounding and publication safety. It does not replace
qualified medical review or grant review authority.

## Gather

Read the exact organized statement, all bound evidence artifacts, textbook
version, source scope, page references, risk class, evidence roles, and current
review state. Load accepted ADRs for knowledge aspects, evidence artifacts, and
transactional review.

Do not validate from a summary when the source artifact is available.

## Decide

Apply `checklists/evidence-copy-eval.md` and classify each item:

- **Verified candidate**: local source-verified evidence supports the complete
  statement, no conflict exists, and required review is present.
- **Needs review**: evidence or applicability is uncertain, a high-risk gate is
  incomplete, or the statement depends on interpretation.
- **Evidence conflict**: confirmed evidence makes incompatible claims under the
  same applicability conditions.
- **Unsupported**: no valid local evidence supports the statement.
- **Evidence only**: source material may be shown, but no organized conclusion
  is safe to publish.

## Hard Rules

- Never use an LLM judgment as publication approval.
- Never invent missing applicability conditions or reconcile a conflict.
- Never substitute evidence from another edition or a similar topic.
- Never use an external reference as the only support for a local conclusion.
- Treat dosage, contraindication, indication, first choice, treatment priority,
  critical values, and procedural steps as high risk by default.
- Hide unsupported, needs-review, and conflicting organized conclusions.
- Preserve original evidence even when a conclusion is hidden.

## Output

For every finding, identify the claim, evidence locator, classification, risk,
required action, and whether qualified human review is still required. Do not
say "medically approved" without the required review record.

