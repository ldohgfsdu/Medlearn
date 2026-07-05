# Production Acceptance

Use before claiming a MedLearn change is production ready.

## Automated

- [ ] Project state validation passes.
- [ ] Generated current state is current.
- [ ] `npm run check` passes.
- [ ] Relevant Python tests pass.
- [ ] Database migrations, RLS, and service contracts are verified when changed.
- [ ] No secrets or machine-specific paths entered tracked files.

## Product

- [ ] The change supports a current MVP capability or approved experiment.
- [ ] Acceptance criteria are observable and have recorded evidence.
- [ ] Failure states do not expose fabricated or stale medical content.
- [ ] User-facing claims distinguish education from clinical advice.

## Medical And Privacy

- [ ] Medical content passed the applicable evidence and review gate.
- [ ] High-risk organized conclusions have qualified review.
- [ ] Real-patient or identifiable information is absent.
- [ ] Case ground truth, scoring rules, and reviewer data remain server-side.

## Runtime

- [ ] The primary path was exercised in a production-like environment.
- [ ] Relevant iOS, Android, web, or remote checks are recorded.
- [ ] Performance, cost, and observability were checked where relevant.
- [ ] Remaining manual checks and release blockers are explicit.

