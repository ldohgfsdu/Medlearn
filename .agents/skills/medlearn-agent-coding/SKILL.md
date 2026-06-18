---
name: medlearn-agent-coding
description: Implement, debug, refactor, or document MedLearn repository changes while preserving product identity, medical safety, current scope, and existing architecture. Use for code changes, bug fixes, service work, route changes, tests, documentation updates, and cross-cutting repository tasks that are not exclusively UI, ingestion, medical review, or model-training evaluation.
---

# Implement MedLearn Changes

## Orient

1. Read `AGENTS.md` and its startup sources.
2. Route the task through `context/TASK_ROUTER.yaml`.
3. Inspect the relevant code, tests, contracts, and accepted ADRs.
4. Resolve implementation facts from code and tests; resolve identity and
   priority from authoritative docs and state.

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
For broad client changes:

```powershell
npm run check
```

For governance changes:

```powershell
.\.venv-sft\Scripts\python.exe scripts\validate_project_state.py
.\.venv-sft\Scripts\python.exe scripts\generate_current_state.py --check
```

Report commands that could not run and distinguish automated evidence from
manual verification.

## Escalate

Stop for user input only when unresolved intent could affect medical accuracy,
privacy, irreversible data, or product direction. Discover ordinary
implementation details from the repository.

