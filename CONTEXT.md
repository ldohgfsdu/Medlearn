# MedLearn Canonical Context

This file defines shared language and durable interpretation. It does not track
current execution status. Read `docs/CURRENT_STATE.md` for status.

## Product

**MedLearn** is an educational system that uses structured medical knowledge to
train clinical reasoning.

> 书是基础。框架是核心。推理是终点。

The product has two independent core capabilities:

- **Knowledge**: search, catalog browsing, textbook-grounded detail, and review.
- **Case Simulator**: clinical information gathering, diagnosis, treatment
  decisions, scoring, feedback, and retry.

Knowledge is not a prerequisite that unlocks cases. Cases may link back to
relevant Knowledge after feedback, but must not create a forced funnel.

## Canonical Terms

- **Textbook Version**: the ownership boundary for catalog structure, content,
  evidence, and page references. Editions never silently share these records.
- **Catalog Node**: a position in one textbook version's display hierarchy.
- **Knowledge Detail Instance**: the detail content for one catalog object in
  one textbook version.
- **Source Aspect**: a heading or section owned by the textbook. Product labels
  may help retrieval but must not rewrite the source structure.
- **Knowledge Item**: a learner-facing organized statement derived from local
  evidence.
- **Evidence Artifact**: independently preserved source material such as text,
  table, figure, caption, row, or cell.
- **Source Scope Manifest**: the approved boundary describing which source
  regions belong to a Knowledge Detail Instance.
- **Verification Decision**: an immutable, auditable decision controlling
  publication or review state.
- **Active Object**: the single project-level execution priority recorded in
  `state/active_object.yaml`.
- **Pipeline Operational State**: subsystem progress such as
  `state/knowledge_ingestion.yaml`; it does not create a second project-level
  Active Object.

## Medical Boundary

- Intended users are medical students and junior residents.
- The system is for education only.
- Never accept identifiable real-patient data.
- Never present generated text as textbook evidence.
- Never publish unsupported or conflicting organized conclusions.
- Dosage, contraindication, indication, first-choice treatment, treatment
  priority, critical values, and procedural steps are high risk by default.
- Automated checks support but do not replace qualified medical review.

## Knowledge Display

Keep display hierarchy and semantic relationships separate:

```text
Display: textbook -> system -> chapter/category -> disease -> source aspect
Semantic: disease, symptom, mechanism, test, treatment, complication, relation
```

Search should navigate:

```text
query -> correct catalog object -> correct source aspect -> evidence -> page
```

Search must not become open-ended medical answer generation.

## Current Technology

- Expo Router, React Native, React, and TypeScript for the client.
- Supabase Auth, PostgreSQL, RLS, and Edge Functions for backend services.
- PostgreSQL full-text search and pgvector for retrieval.
- Python ingestion and local model-training workflows.

Treat `docs/TECHNICAL_ARCHITECTURE.md` cautiously where it is marked historical.
Use current code, `package.json`, migrations, and tests for implementation facts.

## Authority Map

| Question | Source |
|---|---|
| What is MedLearn? | `docs/PROJECT_CONSTITUTION.md` |
| What is in the MVP? | `docs/MVP_PRD_V2.md` |
| What is active now? | `docs/CURRENT_STATE.md`, `state/*.yaml` |
| Why was an architecture choice made? | accepted entries in `docs/ADR_INDEX.yaml` |
| What exists in code? | code, migrations, tests, reproducible runtime evidence |
| How should a task be routed? | `context/TASK_ROUTER.yaml` |
