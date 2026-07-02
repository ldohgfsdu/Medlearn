# MedLearn Agent Entry Point

This file is the shortest safe path into the repository. Treat it as routing,
not as a replacement for the authoritative documents.

## Startup

Before changing files:

1. Read `docs/PROJECT_CONSTITUTION.md`.
2. Read `docs/MVP_PRD_V2.md`.
3. Read `docs/CURRENT_STATE.md`; never edit it manually.
4. Read `docs/ADR_INDEX.yaml` and load only accepted ADRs relevant to the task.
   ADR bodies live under `docs/adr/ADR-0XX-*.md` (lowercase subdirectory).
5. Read `CONTEXT.md`.
6. Read `state/active_object.yaml` — the **only** source of the current active
   object. Sister files (`state/blocked_objects.yaml`,
   `state/completed_objects.yaml`, `state/knowledge_ingestion.yaml`,
   `state/training_dataset.yaml`) give blocked/completed and ingestion state.
7. Use `context/TASK_ROUTER.yaml` to select task-specific sources, skills, and
   acceptance checks.
8. For UI, copy, or visual work, also read `docs/DESIGN_CONTEXT.md` and
   `docs/BRAND_VOICE.md`.
9. For documentation, Obsidian, or VitePress work, also read
   `docs/OBSIDIAN_VAULT.md` (agent handoff section).

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
- **Do not push to the remote repository unless the user explicitly asks.**
  Commit locally; the user pushes.
- Relative paths in `.agents/skills/**/SKILL.md` and all `checklists/**`
  references resolve from the repository root unless stated otherwise.
- Markdown links of the form `[text](path)` may use `../` prefixes as needed
  for correct rendering from the file's own directory; this rendering exception
  does not apply to plain root-relative text references.

## Skills

Project skills live in `.agents/skills/`:

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
  acceptance for the current active object
  `phase1_document_tree_golden_path_validation`.
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

```bash
npm run typecheck   # tsc --noEmit
npm run lint        # expo lint
npm test            # node --test tests/*.test.{js,ts}
```

Documentation-only changes do not require running tests.

## Documentation And Obsidian (Agent Handoff)

**Agents edit the git repo directly.** Do not depend on Obsidian being open.

| What | Authoritative path | Notes |
|------|-------------------|--------|
| Public docs site (VitePress) | `site/` | Nav in `site/.vitepress/config.mts` |
| Internal engineering docs | `docs/` | ADRs, pipeline, API; not the public site |
| Obsidian vault (human UI) | `F:\MedLearn Vault\Medlearn\` | Outside git; optional for users |
| Generated Obsidian nav | `scripts/generate-obsidian-doc-nav.mjs` | Writes into vault on `npm run docs:obsidian` |

**After changing public docs:**

1. Edit files under `site/` (verify against app code when describing behavior).
2. If you changed `site/.vitepress/config.mts`, run `npm run docs:obsidian:nav`.
3. Run `npm run docs:build` when a build check is needed.
4. Commit `site/` (and `docs/` if touched) in `F:\ml`; user pushes to GitHub.

**Do not:**

- Create Chinese-named Windows junctions for Obsidian (they garble in the UI).
- Treat `F:\MedLearn Vault` notes as product truth; code + `docs/CURRENT_STATE.md` win.
- Duplicate content into `docs-site/` (legacy, pending removal); use `site/` only.
- Hand-edit generated vault pages `发布文档站.md`, `10 发布文档/目录.md`, etc.; regenerate.

Full topology and user workflow: `docs/OBSIDIAN_VAULT.md`.

## Definition Of Done

A task is complete only when:

- requested behavior or artifact exists;
- applicable tests and checklists pass;
- medical and privacy boundaries remain intact;
- no unsupported content is exposed;
- state or authority documents are updated only when the task changes them;
- the final report distinguishes verified facts, inferences, and unverified
  manual checks.
