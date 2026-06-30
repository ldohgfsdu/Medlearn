# ADR-010: Enforce Transactional Review Consistency

**Status**: Accepted
**Date**: 2026-06-15

## Context

Evidence Claim Revisions and Verification Decisions control whether medical
content is visible. Two reviewers may concurrently act on the same prior state.
Allowing last-write-wins behavior could create two current claims, two active
decisions, or silently discard a medical review.

Application-level checks alone cannot guarantee consistency under concurrent
writes.

## Decision

Review confirmation uses database transactions, optimistic locking, and partial
unique indexes.

Each Evidence Claim has at most one Current Confirmed Revision:

```sql
create unique index uniq_current_confirmed_claim_revision
on evidence_claim_revision (claim_id)
where revision_state = 'confirmed' and is_current = true;
```

Each target and decision type has at most one Active Verification Decision:

```sql
create unique index uniq_active_verification_decision
on verification_decision (target_type, target_id, decision_type)
where decision_state = 'active';
```

A revision-confirmation transaction:

1. reads the claim version and Current Revision
2. receives an `expected_version` from the reviewer
3. verifies that the expected and stored versions match
4. supersedes the old Current Revision
5. confirms the new Revision and marks it Current
6. increments the claim version
7. supersedes dependent Verification Decisions
8. moves affected Knowledge Items to Needs Review until reevaluation

When the expected version is stale, the transaction does not overwrite the
current result. It creates a Review Conflict with the target, competing
revisions, reason, status, and creation time.

Review Conflict reasons include concurrent confirmation and stale expected
version. Resolution requires a human reviewer to create a new adjudicating
Revision. The competing Revisions remain immutable, the conflict becomes
Resolved, and Verification Decisions are rerun.

LLMs may create Candidate Claims or suggestions. Background tasks may detect
conflicts and create Pending Decisions. Only a human reviewer may confirm a
Current Revision or Active Decision. Neither an LLM nor a background task may
resolve a Review Conflict.

Medical review authority is separate from system administration:

- Reviewer may confirm Standard Claims and Knowledge Items and handle ordinary
  Needs Review work
- Senior Reviewer may confirm High Risk items and Core Evidence, resolve Review
  Conflicts, and approve Complete Coverage Audits
- Admin manages accounts, roles, Rule Versions, and system configuration but
  cannot substitute for medical review or mark medical content Verified

No reviewer may confirm a Candidate, Claim Revision, Evidence Role assignment,
or Risk Class revision that they created. High Risk items and Core Evidence
require a Senior Reviewer. Review Conflict adjudication requires a qualified
third Senior Reviewer who did not participate in either competing revision.

Every confirmation passes a common authorization check covering actor role,
target Risk Class, Evidence Role, target creator, conflict participants, and
Rule Version. Admin status alone grants no medical review permission.

Emergency override is append-only and audited. It cannot bypass the unique
Current Revision constraint, unique Active Decision constraint, or immutable
Revision history. Later role changes do not retroactively alter historical
decisions.

An early single-reviewer deployment does not relax separation-of-duty rules. A
single Reviewer may extract candidates, review ordinary content, register
Source Scopes and Evidence Artifacts, publish original textbook evidence, and
decide eligible Standard items they did not create. The same person cannot
create and confirm a High Risk item, confirm Core Evidence, resolve a Review
Conflict, or approve Complete coverage.

Without an independent qualified reviewer, High Risk Knowledge Items remain
Needs Review and their organized conclusions stay hidden. Source Verified
Evidence Artifacts may still be published as evidence-only textbook text,
tables, figures, captions, and page references. The Knowledge Detail Instance
may remain Available with Evidence Only or Partial coverage.

Single-reviewer operation supports personal use and trustworthy source lookup;
it does not present singly reviewed high-risk conclusions as fully reviewed
medical content.

## Consequences

- Review writes require transactional service or database-function boundaries.
- Database constraints remain the final protection against duplicate Current or
  Active records.
- Clients must submit expected versions and handle stale-review responses.
- Concurrent review never uses last-write-wins behavior.
- Review Conflict becomes a first-class editorial queue.
- Historical Revisions and Decisions remain append-only and auditable.
- Medical review roles remain distinct from administrative authority, and
  self-review is prohibited.
- Single-reviewer operation may publish verified source evidence but cannot
  certify high-risk conclusions or Complete coverage.
