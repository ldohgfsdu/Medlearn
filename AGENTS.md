# MedLearn Agent Entry Point

This file is the shortest safe path into the repository. Treat it as routing,
not as a replacement for the authoritative documents.

## Startup

Before changing files, perform the minimum safe boot:

1. Read `docs/PROJECT_CONSTITUTION.md`.
2. Read `docs/MVP_PRD_V2.md`.
3. Read `state/active_object.yaml` — the only source of the current active
   object.
4. Read sibling state files as needed: `state/blocked_objects.yaml`,
   `state/completed_objects.yaml`, `state/knowledge_ingestion.yaml`,
   `state/training_dataset.yaml`.
5. Read `docs/CURRENT_STATE.md`; it is generated/read-only for agents. If it
   conflicts with the source YAML, treat the YAML as authoritative and report
   the drift instead of reconciling it silently.
6. Use `context/TASK_ROUTER.yaml` to select task-specific sources, skills, and
   acceptance checks.

Then load task-specific context as needed:

- Read `docs/ADR_INDEX.yaml` and load only accepted ADRs relevant to the task.
  ADR bodies live under `docs/adr/ADR-0XX-*.md` (lowercase subdirectory).
- Read `CONTEXT.md` when repository history or handoff context is needed.
- For UI, copy, or visual work, also read `docs/DESIGN_CONTEXT.md` and
  `docs/BRAND_VOICE.md`.
- For documentation, Obsidian, or VitePress work, also read
  `docs/OBSIDIAN_VAULT.md`.

If state must change, update the authoritative YAML/source file and regenerate
derived state documents instead of editing `docs/CURRENT_STATE.md` manually.

Running code and tests define what exists. The constitution and PRD define what
the product is and what matters. State YAML defines current execution priority.

Authority precedence (higher wins):

1. The user's explicit request, unless it violates project rules or safety
   boundaries.
2. `docs/PROJECT_CONSTITUTION.md` and `docs/MVP_PRD_V2.md`.
3. Source state YAML under `state/`.
4. `context/TASK_ROUTER.yaml`, the selected skill's `SKILL.md`, and the
   checklists it names:
   - `context/TASK_ROUTER.yaml` determines which task sources, skills, and
     checklists apply.
   - The selected skill's `SKILL.md` governs task procedure and scope.
   - Named checklists define acceptance criteria within that selected scope.
   - If they conflict, report the conflict instead of resolving it silently.
5. Generated docs, reports, artifacts, and historical handoff notes.

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
- **Do not push to the remote repository unless the user explicitly asks.**
  Create a local commit only when the user asks for a commit or the task
  contract explicitly requires one; otherwise report changed files and
  verification results.
- Relative paths in `.agents/skills/**/SKILL.md` and all `checklists/**`
  references resolve from the repository root unless stated otherwise.
- Markdown links of the form `[text](path)` may use `../` prefixes as needed
  for correct rendering from the file's own directory; this rendering exception
  does not apply to plain root-relative text references.

## Skills

Project skills live in `.agents/skills/`. Skill names map to
`.agents/skills/<skill-name-without-$>/SKILL.md`; always read the selected
skill's `SKILL.md` before applying it.

- `$medlearn-agent-coding`: implement or fix repository code and docs.
- `$medlearn-review-ui`: review or change app screens and interactions.
- `$medlearn-review-ingestion`: review textbook extraction, normalization, and
  upload changes.
- `$medlearn-phase1-visual-evidence`: implement Phase 1 textbook page-image
  back-jump, source locators, and PageViewer evidence highlighting.
- `$medlearn-validate-medical-content`: assess content grounding, evidence, and
  publication safety.
- `$medlearn-evaluate-training-stage`: assess SFT datasets, stage metrics, and
  training promotion gates.

`.claude/skills/` contains thin redirects to the canonical skills above; do
not expand them.

Use the smallest set that covers the task. For cross-cutting work, apply
`$medlearn-agent-coding` first, then the relevant specialist skill.

## Checklists

Authoritative checklists live under `checklists/` and resolve from the
repository root:

- `checklists/phase1-golden-path-acceptance.md` — Phase 1 golden path
  acceptance checklist. Apply only when selected by `context/TASK_ROUTER.yaml`
  or the current `state/active_object.yaml`; do not infer current priority from
  this checklist name.
- `checklists/app-integration-gate.md` — app integration gate.
- `checklists/production-acceptance.md` — production acceptance.
- `checklists/no-regression-rules.md` — regression rules.
- `checklists/evidence-copy-eval.md` — evidence copy evaluation.

When a skill names a checklist, load it from this directory.

## Design And Voice

- `docs/DESIGN_CONTEXT.md` — visual design language: color semantics,
  typography, spacing rhythm, component hierarchy, state colors, number styles.
- `docs/BRAND_VOICE.md` — brand tone and copy rules: positioning, voice
  principles, sample copy, forbidden phrasing, feedback language.
- `constants/theme.ts`, `constants/textbookEditorial.ts`, `constants/layout.ts`,
  `constants/pageStyles.ts` — design tokens; do not introduce ad-hoc colors,
  fonts, or spacing.

UI work must satisfy the Product Constraints in
`.agents/skills/medlearn-review-ui/SKILL.md`.

## Verification

Run the smallest verification set that proves the requested change:

- Code changes: `npm run typecheck`, `npm run lint`, and relevant tests.
- Testable behavior changes: add or update tests. If tests are not practical,
  state the reason and provide the smallest manual verification that proves the
  behavior.
- Public docs changes: `npm run docs:build` when the site output could be
  affected.
- Documentation-only internal notes: tests may be skipped, but the final report
  must say why.

Do not describe skipped, failing, or unrun checks as passed.

Reference commands:

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # expo lint
npm test            # node --test tests/*.test.{js,ts}
```

## Documentation And Obsidian (Agent Handoff)

For documentation-site or Obsidian-related work, read `docs/OBSIDIAN_VAULT.md`
before editing. The git repo is authoritative; the Obsidian vault is a human UI
and must not override code, `docs/`, or state YAML. Agents edit the git repo
directly and must not depend on Obsidian being open.

| What | Authoritative path |
|------|-------------------|
| Public docs site (VitePress) | `site/` |
| Internal engineering docs | `docs/` |
| Obsidian vault (human UI) | `F:\MedLearn Vault\Medlearn\` (outside git) |

Key rules (full detail in `docs/OBSIDIAN_VAULT.md`):

- After changing public docs under `site/`, run `npm run docs:obsidian:nav` if
  `site/.vitepress/config.mts` changed, then `npm run docs:build` when needed.
- Do not treat `F:\MedLearn Vault` notes as product truth.
- Do not duplicate content into `docs-site/` (legacy); use `site/` only.
- Do not hand-edit generated vault pages; regenerate them.

## Definition Of Done

A task is complete only when:

- requested behavior or artifact exists;
- applicable tests and checklists pass;
- medical and privacy boundaries remain intact;
- no unsupported content is exposed;
- state or authority documents are updated only when the task changes them;
- the final report distinguishes verified facts, inferences, and unverified
  manual checks;
- the final report lists changed files, commands run, checks skipped with
  reasons, and known residual risks.
