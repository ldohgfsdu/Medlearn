---
name: medlearn-validate-medical-content
description: Validate MedLearn medical statements, textbook summaries, evidence bindings, page references, case content, risk classes, and publication states. Use whenever a change adds or modifies medical content, treatment information, dosage, contraindications, critical values, procedural steps, source evidence, or review decisions.
---

# Validate Medical Content

This skill evaluates grounding and publication safety. It does not replace
qualified medical review or grant review authority.

## Gather

Read:

- `AGENTS.md` and its startup sources
- `context/TASK_ROUTER.yaml` — selects this skill and applicable checks
- `state/active_object.yaml` — current active object
- the exact organized statement, all bound evidence artifacts, textbook
  version, source scope, page references, risk class, evidence roles, and
  current review state
- `state/knowledge_ingestion.yaml` — records extraction status, pipeline
  closure, and `needs_review` / high-risk gating state
- accepted ADRs selected through `docs/ADR_INDEX.yaml`:
  - ADR-005 (textbook version boundaries)
  - ADR-006 (textbook-owned knowledge aspects)
  - ADR-007 (catalog / content identity / detail separation)
  - ADR-008 (concept reuse / detail isolation)
  - ADR-009 (multimodal evidence artifacts)
  - ADR-010 (transactional review consistency — Revision and Decision tables)

Do not validate from a summary when the source artifact is available.

## Decide

Apply `checklists/evidence-copy-eval.md` and `checklists/production-acceptance.md`,
then classify each item:

- **Verified candidate**: local source-verified evidence supports the complete
  statement, no conflict exists, and required review is present.
- **Needs review**: evidence or applicability is uncertain, a high-risk gate is
  incomplete, or the statement depends on interpretation.
- **Evidence conflict**: confirmed evidence makes incompatible claims under the
  same applicability conditions.
- **Unsupported**: no valid local evidence supports the statement.
- **Evidence only**: source material may be shown, but no organized conclusion
  is safe to publish.

These classifications are the operational vocabulary for this skill;
`checklists/evidence-copy-eval.md` checks source fidelity, organized copy, and
high-risk gates that produce these classifications.

## Ingestion Cross-Reference

Medical content validation depends on ingestion-side evidence binding and page
references. If ingestion changes evidence bindings, page references, or
`artifact_id` joins on a published section, re-validate affected medical
content. Coordinate with `.agents/skills/medlearn-review-ingestion/SKILL.md`
(it declares this dependency in its `## Cross-Reference` →
`### Medical content validation`).

## Hard Rules

- Never use an LLM judgment as publication approval.
- Never invent missing applicability conditions or reconcile a conflict.
- Never substitute evidence from another edition or a similar topic.
- Never use an external reference as the only support for a local conclusion.
- Treat dosage, contraindication, indication, first choice, treatment priority,
  critical values, and procedural steps as high risk by default.
- Hide unsupported, needs-review, and conflicting organized conclusions.
- Preserve original evidence even when a conclusion is hidden.

## Validate

Run targeted audits before declaring a publication state:

```powershell
.\.venv-sft\Scripts\python.exe scripts/ev1_evaluate_batch.py
node scripts/audit-ev1-knowledge-quality.mjs
```

`.\.venv-sft\Scripts\python.exe` is the Windows path used by this project. On
other platforms, activate `.\.venv-sft` and use `python` directly.

Do not run broad LLM re-extraction or remote upload merely to validate
content. Require explicit scope confirmation before mutating pipeline state.

## Failure Modes (Stop And Report)

| Condition | Action |
|-----------|--------|
| Evidence binding or page reference is missing or changed | Stop; route through `medlearn-review-ingestion` first |
| Required human review is absent for a high-risk item | Stop; hide the organized conclusion and record the gap |
| LLM judgment is the only support for a conclusion | Stop; never approve publication |
| Evidence from another edition or similar topic is the only support | Stop; mark Unsupported |
| Conflict between evidence sources under same applicability | Stop; hide conclusion and enter review |

## Output

For every finding, identify the claim, evidence locator, classification, risk,
required action, and whether qualified human review is still required.

### Where review state lives (do not conflate these)

| Source | What it records | Review authority |
|--------|-----------------|------------------|
| `state/knowledge_ingestion.yaml` | Pipeline status, extraction progress, `needs_review` concentration, high-risk gating summary, `ui_visible` / `page_image_return_path` flags | **None** — pipeline-level summary only; cannot approve medical content |
| Database Revision/Decision tables (ADR-010) | Per-statement review decisions: Revision (immutable proposed text), Active Decision (current verdict), reviewer identity, applicability conditions | **Only authoritative source of qualified review** |

Rules:

- A pipeline status of `verified_36_chapters` or `pipeline_closure_verified: true`
  in `state/knowledge_ingestion.yaml` does **not** mean medical content is
  approved. It means the pipeline ran.
- "Medically approved" / "医学审核通过" requires a matching Active Decision
  record in the Revision/Decision tables. No Decision → not approved, regardless
  of pipeline state.
- Cite the Decision record (revision id, decision id, reviewer) when claiming
  review; cite the state YAML field when claiming pipeline status.
