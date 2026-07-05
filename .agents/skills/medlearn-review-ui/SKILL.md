---
name: medlearn-review-ui
description: Review or implement MedLearn screens, components, navigation, interaction states, accessibility, and visual hierarchy. Use for React Native or Expo UI changes, screenshots, design audits, route flows, loading or error states, and checking alignment with MedLearn's clinical editorial design and learning principles.
---

# Review MedLearn UI

## Read

- `AGENTS.md` and its startup sources
- `context/TASK_ROUTER.yaml` — selects this skill and applicable checks
- `state/active_object.yaml` — current active object; UI work must stay inside
  its scope or state the conflict before expanding
- `docs/DESIGN_CONTEXT.md`
- `docs/BRAND_VOICE.md`
- `docs/LEARNING_DESIGN_PRINCIPLES.md`
- the target route, components, hooks, and services
- `constants/theme.ts`, `constants/layout.ts`, and `constants/pageStyles.ts`
- `checklists/app-integration-gate.md`
- `checklists/phase1-golden-path-acceptance.md` — applies when the change
  touches Phase 1 golden-path reading experience (asthma or pulmonary
  tuberculosis sections) per `TASK_ROUTER.yaml`'s `phase1_golden_path` route

## Review Order

1. Confirm the screen supports a current product journey.
2. Verify data and navigation behavior before visual polish.
3. Check loading, error, empty, partial, unavailable, and retry states.
4. Check information hierarchy and one obvious next action.
5. Check typography, spacing, alignment, touch targets, contrast, and safe areas.
6. Check that decorative treatment does not compete with clinical content.
7. Exercise the changed path in a browser, simulator, or device when available.

## Phase 1 Cross-Reference

UI changes to evidence entry points (e.g., `EvidenceToggle` in
`app/textbook/[sectionId]/unit/[unitId].tsx`) and any `PageViewer` route affect
`.agents/skills/medlearn-phase1-visual-evidence/SKILL.md`. Coordinate before
merging changes to:

- Evidence toggle copy and navigation target (「教材原文 P{pageLabel}」)
- `pageAssetId` and `sourceLocatorIds` route parameters
- bbox highlight rendering (`bboxNorm`, top-left origin, no Y-flip)

## Product Constraints

Derived from `docs/DESIGN_CONTEXT.md`, `docs/BRAND_VOICE.md`, and accepted UI
decisions documented in project memory.

- Use the shared theme; do not introduce arbitrary colors.
- Keep body copy at least 15 px and touch targets at least 44 px.
- Prefer whitespace, type, and dividers over nested card grids.
- Use Ionicons for functional icons (React Native app); do not use emoji as controls.
- Use shadows only for genuinely elevated surfaces.
- Static content cards use hairline borders (`borderWidth: 1` + `Colors.border`), not shadows.
- Split fonts by information layer: knowledge/reading content uses `FontFamily.serif`;
  navigation, tabs, buttons, forms, dashboards, and settings use `FontFamily.sans`.
  `Typography.*` defines size/line-height/weight only — always pair it with an explicit
  `fontFamily` at the call site.
- Cap font weight at `600`; do not use 700/800/900. Decorative `letterSpacing` is reserved for verification-code inputs.
- Numeric data uses two distinct treatments per `docs/DESIGN_CONTEXT.md`:
  - **Editorial / medical content numbers** (textbook page numbers, dosages,
    lab values, medical statistics presented as learning content) use
    `FontFamily.serif` + 600 (the `Typography.numberXL/Large/Medium` styles).
  - **Dashboard / operational numbers** (progress bars, counts in
    navigation/UI chrome, completion percentages, system metrics) use
    `FontFamily.sans` + `fontVariant: ['tabular-nums']` to avoid 0/O confusion.
  When in doubt, ask: is this number part of the learning content (serif) or
  part of the operating interface (sans + tabular-nums)?
- No `textTransform: 'uppercase'`; write labels as natural copy (e.g., "学习问答 · 01", "临床判断 · 03").
- Keep the active screen focused on one task.
- Require learner output before revealing feedback in recall or reasoning flows.
- Preserve textbook source aspect order and evidence expansion behavior.
- Never fabricate statistics, ratings, progress, or medical content.

## Failure Modes (Stop And Report)

| Condition | Action |
|-----------|--------|
| Change would fabricate medical content, statistics, or progress | Stop; report the conflict |
| Change breaks textbook source aspect order or evidence expansion | Stop; report the contract violation |
| Change touches Phase 1 golden-path reading experience without applying `phase1-golden-path-acceptance.md` | Stop; apply the checklist |
| Active object scope is violated | Stop; report before expanding scope |
| Touch target < 44 px or body copy < 15 px after change | Stop; fix before claiming done |

## Output

For reviews, lead with actionable findings ordered by severity and cite the
affected file or screen. For implementation, make the change, run relevant
tests, and report:

- the runtime path exercised (route, screen, state)
- which checks passed, failed, or were not run
- whether the result is code-ready, app-visible, or device-verified
- manual checks still pending (e.g., device walkthrough, screenshot review)

These are distinct states; do not conflate them.
