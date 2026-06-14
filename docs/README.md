# MedLearn Documentation

This directory separates current authority from historical context.

## Sources Of Truth

Read in this order:

1. [`PROJECT_CONSTITUTION.md`](PROJECT_CONSTITUTION.md) - stable product identity, boundaries and decision rules.
2. [`MVP_PRD_V2.md`](MVP_PRD_V2.md) - current MVP scope and capability priorities.
3. [`CURRENT_STATE.md`](CURRENT_STATE.md) - generated execution state; never edit manually.
4. [`ADR_INDEX.yaml`](ADR_INDEX.yaml) - machine-readable ADR index.
5. [`../CONTEXT.md`](../CONTEXT.md) - canonical domain glossary.

When sources conflict:

```text
running code and tests > current authoritative docs > memory > chat history
```

Code describes what exists. It does not change product identity or priority by itself.

## Maintained References

- [`API.md`](API.md) - backend and Edge Function interfaces.
- [`DESIGN_CONTEXT.md`](DESIGN_CONTEXT.md) - current visual and interaction principles.
- [`E2E_ACCEPTANCE_CHECKLIST.md`](E2E_ACCEPTANCE_CHECKLIST.md) - device and remote acceptance.
- [`LEARNING_DESIGN_PRINCIPLES.md`](LEARNING_DESIGN_PRINCIPLES.md) - learning-loop principles.
- [`PDF_EXTRACTION_GUIDE.md`](PDF_EXTRACTION_GUIDE.md) - textbook extraction workflow.
- [`RAG_SETUP_GUIDE.md`](RAG_SETUP_GUIDE.md) - retrieval configuration.
- [`REMOTE_DEPLOYMENT_GUIDE.md`](REMOTE_DEPLOYMENT_GUIDE.md) - Supabase deployment.
- [`TECHNICAL_ARCHITECTURE.md`](TECHNICAL_ARCHITECTURE.md) - architecture reference; sections marked historical are not authoritative.

## Archive

[`archive/`](archive/) contains superseded plans, reports and agent guidance. Archived documents preserve project history but must not be used as current requirements, status, architecture or implementation instructions.

## Update Rules

- Resolve domain terms immediately in [`../CONTEXT.md`](../CONTEXT.md).
- Record hard-to-reverse, surprising trade-offs as ADRs only when a real alternative was considered.
- Change execution state in `state/*.yaml`, then regenerate `CURRENT_STATE.md`.
- Update this index when a maintained document is added, replaced or archived.
