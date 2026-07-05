---
name: medlearn-agent-coding
description: Implement, debug, refactor, or document MedLearn repository changes while preserving product identity, medical safety, current scope, and existing architecture. Use for code changes, bug fixes, service work, route changes, tests, documentation updates, and cross-cutting repository tasks that are not exclusively UI, ingestion, medical review, or model-training evaluation.
---

# Implement MedLearn Changes

## Orient

1. Read `AGENTS.md` and its startup sources, including
   `state/active_object.yaml` — current execution priority must drive scope
   decisions.
2. Route the task through `context/TASK_ROUTER.yaml`.
3. Inspect the relevant code, tests, contracts, and accepted ADRs.
4. Resolve implementation facts from code and tests; resolve identity and
   priority from authoritative docs and state.

## When To Escalate To A Specialist Skill

`context/TASK_ROUTER.yaml` selects the canonical skill per route. If the task
matches a specialist route, switch to that skill instead of staying on the
default `medlearn-agent-coding` route:

- UI / screens / components / navigation → `medlearn-review-ui`
- Textbook extraction / ingestion / catalog / evidence binding / backfills →
  `medlearn-review-ingestion`
- Phase 1 page images / PageViewer / source locators / bbox →
  `medlearn-phase1-visual-evidence`
- Medical statements / evidence / page references / dosage / contraindications →
  `medlearn-validate-medical-content`
- SFT datasets / LoRA checkpoints / stage metrics / promotion gates →
  `medlearn-evaluate-training-stage`

For cross-cutting work, apply `medlearn-agent-coding` first, then the relevant
specialist skill. Do not silently handle specialist-domain decisions on the
default route.

## Implement

- Keep edits inside the requested behavior and existing ownership boundaries.
- Prefer existing services, hooks, utilities, route builders, and domain types.
- Preserve user changes and unrelated worktree content.
- Add no abstraction unless it removes real duplication or matches a local pattern.
- Do not expose secrets, case ground truth, rubrics, reviewer data, or patient data.
- Do not add open-ended medical answering where the product expects grounded
  navigation or constrained simulation.
- Update state YAML only when the task genuinely changes execution state.
  Regenerate `docs/CURRENT_STATE.md`; never hand-edit it.

## Validate

Apply `checklists/no-regression-rules.md`, then run the narrowest relevant tests.
Before claiming a change is production ready, also apply
`checklists/production-acceptance.md`.

For Phase 1 golden-path changes, also apply
`checklists/phase1-golden-path-acceptance.md`. For changes that cross into
data, services, routes, or UI behavior entering the app, also apply
`checklists/app-integration-gate.md`.

For broad client changes:

```powershell
npm run check
```

`npm run check` is the aggregate of `check:routes`, `typecheck`, `lint`, and
`test` (see `package.json`). For narrower runs use the individual scripts.

For governance changes:

```powershell
.\.venv-sft\Scripts\python.exe scripts\validate_project_state.py
.\.venv-sft\Scripts\python.exe scripts\generate_current_state.py --check
```

`.\.venv-sft\Scripts\python.exe` is the Windows path used by this project. On
other platforms, activate `.\.venv-sft` and use `python` directly.

Report commands that could not run and distinguish automated evidence from
manual verification.

## Failure Modes (Stop And Report)

| Condition | Action |
|-----------|--------|
| Requested change touches medical accuracy or safety | Stop; route through `medlearn-validate-medical-content` |
| Requested change would expose case answers, rubrics, reviewer fields, or patient data | Stop; report the conflict |
| Push to remote is **not** explicitly requested | Stop; AGENTS.md forbids push without explicit user request |
| Push to remote is explicitly requested but target environment / branch / remote is ambiguous | Stop; confirm target before executing |
| Active object scope is violated | Stop; report before expanding scope |
| Open-ended medical answering would be added where grounded navigation is expected | Stop; report the product-boundary conflict |

Push policy: an explicit user request to push is the only authorization for
push; "explicit" means the user said push / publish / deploy to remote (in any
language). When in doubt about target environment, branch, or remote, ask
before executing. Never force-push to main/master.

## Escalate

Stop for user input only when unresolved intent could affect medical accuracy,
privacy, irreversible data, or product direction. Discover ordinary
implementation details from the repository.
