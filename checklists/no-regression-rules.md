# No-Regression Rules

Use for every repository change.

- [ ] The change matches the user request and does not expand the active scope.
- [ ] Existing user changes and unrelated files are preserved.
- [ ] Product identity and MVP boundaries remain unchanged unless authorized.
- [ ] Knowledge and Case Simulator remain independently accessible.
- [ ] Search still navigates to grounded content instead of generating answers.
- [ ] No medical fact, evidence, page reference, review state, or metric is invented.
- [ ] No secret, rubric, ground truth, reviewer field, or patient data is exposed.
- [ ] Textbook version and source aspect ownership remain intact.
- [ ] Error, loading, empty, and unavailable states remain understandable.
- [ ] Tests cover the changed behavior at the narrowest useful layer.
- [ ] `npm run check` passes for client changes.
- [ ] Relevant Python tests pass for pipeline or training changes.
- [ ] Unrun manual or device checks are reported explicitly.

