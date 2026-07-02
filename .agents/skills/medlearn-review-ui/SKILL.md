---
name: medlearn-review-ui
description: Review or implement MedLearn screens, components, navigation, interaction states, accessibility, and visual hierarchy. Use for React Native or Expo UI changes, screenshots, design audits, route flows, loading or error states, and checking alignment with MedLearn's clinical editorial design and learning principles.
---

# Review MedLearn UI

## Read

- `AGENTS.md`
- `docs/DESIGN_CONTEXT.md`
- `docs/BRAND_VOICE.md`
- `docs/LEARNING_DESIGN_PRINCIPLES.md`
- the target route, components, hooks, and services
- `constants/theme.ts`, `constants/layout.ts`, and `constants/pageStyles.ts`
- `checklists/app-integration-gate.md`

## Review Order

1. Confirm the screen supports a current product journey.
2. Verify data and navigation behavior before visual polish.
3. Check loading, error, empty, partial, unavailable, and retry states.
4. Check information hierarchy and one obvious next action.
5. Check typography, spacing, alignment, touch targets, contrast, and safe areas.
6. Check that decorative treatment does not compete with clinical content.
7. Exercise the changed path in a browser, simulator, or device when available.

## Product Constraints

- Use the shared theme; do not introduce arbitrary colors.
- Keep body copy at least 15 px and touch targets at least 44 px.
- Prefer whitespace, type, and dividers over nested card grids.
- Use Ionicons for functional icons; do not use emoji as controls.
- Use shadows only for genuinely elevated surfaces.
- Static content cards use hairline borders (`borderWidth: 1` + `Colors.border`), not shadows.
- Titles (display, page, section, and navigation headers) use `FontFamily.serif` at fontWeight `600`; body and labels stay at 400/500.
- Cap font weight at `600`; do not use 700/800/900. Decorative `letterSpacing` is reserved for verification-code inputs.
- Numeric data uses the serif-600 number styles (`Typography.numberXL/Large/Medium`).
- No `textTransform: 'uppercase'`; write labels as natural copy (e.g., "学习问答 · 01", "临床判断 · 03").
- Keep the active screen focused on one task.
- Require learner output before revealing feedback in recall or reasoning flows.
- Preserve textbook source aspect order and evidence expansion behavior.
- Never fabricate statistics, ratings, progress, or medical content.

## Output

For reviews, lead with actionable findings ordered by severity and cite the
affected file or screen. For implementation, make the change, run relevant
tests, and report the runtime path exercised.

