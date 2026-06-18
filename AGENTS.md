# MedLearn Agent Entry Point

This file is the shortest safe path into the repository. Treat it as routing,
not as a replacement for the authoritative documents.

## Startup

Before changing files:

1. Read `docs/PROJECT_CONSTITUTION.md`.
2. Read `docs/MVP_PRD_V2.md`.
3. Read `docs/CURRENT_STATE.md`; never edit it manually.
4. Read `docs/ADR_INDEX.yaml` and load only accepted ADRs relevant to the task.
5. Read `CONTEXT.md`.
6. Use `context/TASK_ROUTER.yaml` to select task-specific sources, skills, and
   acceptance checks.

Running code and tests define what exists. The constitution and PRD define what
the product is and what matters. State YAML defines current execution priority.

## Project Rules

- MedLearn is an educational system, not clinical decision support.
- Knowledge and Case Simulator are independent core capabilities.
- Search navigates to grounded textbook content; it does not answer open-ended
  medical questions.
- Do not invent medical facts, textbook structure, evidence, page references,
  review status, user data, or product metrics.
- Preserve textbook-version ownership, source aspect structure, and evidence
  provenance.
- Protect case answers, scoring rubrics, reviewer fields, service credentials,
  and real-patient information.
- Keep changes inside the user's requested scope and the current active object.
  If they conflict, state the conflict before expanding scope.
- Do not infer current priority from old reports, archived docs, generated
  artifacts, or code existence.

## Skills

Project skills live in `.agents/skills/`:

- `$medlearn-agent-coding`: implement or fix repository code and docs.
- `$medlearn-review-ui`: review or change app screens and interactions.
- `$medlearn-review-ingestion`: review textbook extraction, normalization, and
  upload changes.
- `$medlearn-validate-medical-content`: assess content grounding, evidence, and
  publication safety.
- `$medlearn-evaluate-training-stage`: assess SFT datasets, stage metrics, and
  training promotion gates.

Use the smallest set that covers the task. For cross-cutting work, apply
`$medlearn-agent-coding` first, then the relevant specialist skill.

## Definition Of Done

A task is complete only when:

- requested behavior or artifact exists;
- applicable tests and checklists pass;
- medical and privacy boundaries remain intact;
- no unsupported content is exposed;
- state or authority documents are updated only when the task changes them;
- the final report distinguishes verified facts, inferences, and unverified
  manual checks.

