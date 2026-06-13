# Medlearn MVP PRD

> Status: Draft for execution
> Source: `docs/PRD.md`
> Scope: Phase 1 MVP only
> Last updated: 2026-06-11

---

## 1. Product Decision

Medlearn Phase 1 will validate one product bet:

> Medical learners will choose to complete multiple interactive clinical reasoning cases because the feedback feels more useful than passive question banks.

Phase 1 is not a complete medical learning platform. It is a focused clinical case simulator with scoring and feedback.

## 2. Target Users

### Primary MVP User

Medical students in clinical transition: late pre-clinical or early clinical years, preparing to move from memorizing facts to reasoning through patient presentations.

### Secondary MVP User

Junior residents who want fast practice on common chief complaints during short breaks.

### Not Targeted in MVP

- Full USMLE prep replacement
- Hospital credentialing or competency assessment
- Real patient decision support
- Faculty dashboard or institution administration

## 3. MVP Goals

### Product Goals

1. Validate that users complete more than one case voluntarily.
2. Validate that structured feedback is perceived as more useful than standard answer explanations.
3. Validate that AI patient interaction can remain safe, consistent, and medically bounded.
4. Establish a measurable baseline for clinical reasoning improvement.

### Business Goals

1. Learn whether the product has repeat-use behavior before monetization.
2. Estimate AI cost per completed case.
3. Identify whether case quality or AI latency is the main adoption constraint.

### Motivation Design Principle

Medlearn records learning instead of policing attendance:

- Set a small daily floor: complete one case.
- Do not set a daily completion ceiling. Any additional case is optional extra learning.
- Preserve every completed case and active learning day as a cumulative record.
- Do not reset progress, shame the learner, or use streak-loss warnings after a break.
- After the daily floor is met, explicitly tell the learner that today's commitment is complete.

The intent is to move attention from protecting a streak to engaging with the clinical reasoning activity itself.

### Output and Feedback Principle

Medlearn treats learning as an iterative production loop:

```
produce an answer -> receive specific feedback -> fix one blind spot -> produce again
```

Product requirements:

- Ask the learner to make a real attempt before showing explanations or model answers.
- Feedback must identify observable gaps in the learner's work, not merely display a score.
- After feedback, recommend one highest-value correction instead of a broad study list.
- Let the learner immediately retry the same case, explanation, or weak-node quiz.
- Prefer targeted retries over repeating an unchanged full task.
- Frame mistakes and difficulty as diagnostic information, never as shame, punishment, or evidence of low ability.
- Positive feedback should describe what was done well; avoid empty praise.
- Critical safety errors override ordinary score-based prioritization and become the next correction target.

The product should optimize for **feedback applied**, not only feedback viewed.

### Cognitive Clarity and Stretch Principle

- Recommend task difficulty from recent performance so practice stays near the learner's stretch edge.
- Before a consequential answer is submitted, capture confidence and the learner's largest uncertainty.
- Use the result to calibrate self-judgment: overconfidence, underconfidence, or accurate self-assessment.
- Keep each screen centered on one clear action and one completion condition.
- Treat rest and stopping after a meaningful attempt as valid parts of learning.

See `docs/LEARNING_DESIGN_PRINCIPLES.md` for the complete design translation.

## 4. Non-Goals

The following are explicitly out of scope for Phase 1:

- Feynman Tutor
- Socratic Tutor outside case flow
- VINDICATE standalone trainer
- FSRS memory system
- Community features
- Search
- Subscription and payment
- Full analytics dashboard
- RAG
- Institution/team accounts
- Custom user-generated cases

## 5. MVP Feature Scope

### P0: Required for Alpha

| ID | Feature | Requirement |
|---|---|---|
| MVP-001 | Account access | User can sign up, log in, and resume their own sessions. |
| MVP-002 | Case start | User can select chief complaint and difficulty, then start a case. |
| MVP-003 | Patient conversation | AI responds as the patient using only case ground truth. |
| MVP-004 | Physical exam | User can request predefined exam areas and receive structured findings. |
| MVP-005 | Tests | User can order predefined tests and receive structured results. |
| MVP-006 | Diagnosis submission | User submits primary diagnosis, differentials, evidence, and treatment. |
| MVP-007 | Scoring | System scores diagnosis, differentials, evidence, and treatment. |
| MVP-008 | Feedback loop | User sees score breakdown, one prioritized blind spot, a concrete correction, and can immediately retry. |
| MVP-009 | Event tracking | Core funnel and safety events are recorded. |
| MVP-010 | Medical disclaimer | Education-only disclaimer appears at onboarding and before first case. |
| MVP-011 | Error reporting | User can report incorrect or unsafe medical content from a case. |

### P1: Required for Closed Beta

| ID | Feature | Requirement |
|---|---|---|
| MVP-101 | Case resume | Interrupted case can be resumed from last phase. |
| MVP-102 | Hint | User can request a bounded hint that does not reveal diagnosis. |
| MVP-103 | Practice record | User sees today's one-case floor, completed cases, and cumulative active learning days without streak-loss pressure. |
| MVP-104 | Case quality state | Admin or internal reviewer can mark a case as draft, approved, paused, or retired. |
| MVP-105 | Cost guardrail | System tracks estimated LLM cost per user and per case. |

### P2: Later

- Full home dashboard
- Skill trend charts
- Spaced repetition
- Subscriptions
- RAG-backed medical knowledge
- Faculty or team reporting

## 6. MVP Case Library

MVP will launch with 15 approved cases:

| Chief Complaint | Cases |
|---|---|
| Chest pain | STEMI, aortic dissection, pulmonary embolism |
| Dyspnea | heart failure, asthma/COPD exacerbation, pneumonia |
| Abdominal pain | appendicitis, cholecystitis, pancreatitis |
| Fever | pneumonia, meningitis, pyelonephritis |
| Altered mental status | hypoglycemia, DKA, stroke |

Each case must include:

- Ground truth diagnosis
- Acceptable diagnosis aliases
- Must-ask history points
- Key exam findings
- Available tests and results
- Critical positive evidence
- Critical negative evidence
- Required differentials
- Required initial treatment steps
- Unsafe treatment actions
- Scoring rubric
- Reviewer sign-off

## 7. User Journey

1. User opens app.
2. User sees education-only disclaimer on first use.
3. User chooses a chief complaint and difficulty.
4. User interviews the AI patient.
5. User requests exam findings.
6. User orders tests.
7. User submits diagnosis, differentials, evidence, and treatment.
8. User receives score, evidence-based feedback, and one prioritized correction.
9. User retries the same case with that correction, starts another case, or reports an issue.

## 8. Scoring Model

### Score Dimensions

| Dimension | Weight | Scored By |
|---|---:|---|
| Diagnosis accuracy | 40 | Alias and semantic match against rubric |
| Differential diagnosis | 20 | Required differential coverage and reasoning |
| Evidence use | 20 | Key positive and negative evidence coverage |
| Treatment plan | 20 | Required actions minus unsafe actions |

### Required Scoring Rules

- Every case must have a deterministic rubric before release.
- LLM may assist scoring, but final score must be constrained by rubric fields.
- Unsafe treatment actions must be visible in the feedback report.
- User-facing feedback must explain why points were lost.
- The lowest-performing dimension becomes the default next focus.
- A dangerous treatment action takes priority over all other dimensions.
- The primary action on the feedback screen is a targeted retry, not passive review.
- Scores must be reproducible within an acceptable variance of 5 points across repeated scoring of the same submission.

## 9. North Star Metric: CRIS

CRIS means Clinical Reasoning Improvement Score.

### Definition

CRIS is the change between a user's baseline and follow-up performance on unseen clinical reasoning cases.

```
CRIS = follow-up assessment score - baseline assessment score
```

Both assessments use the same 100-point scoring structure:

- Diagnosis accuracy: 40
- Differential diagnosis: 20
- Evidence use: 20
- Treatment plan: 20

### Measurement Plan

- Baseline: first 2 assessment cases before free practice.
- Follow-up: 2 different assessment cases after the user completes at least 5 practice cases.
- Assessment cases are excluded from normal practice and cannot be repeated during the test window.
- 10% of assessment submissions are manually reviewed to calibrate AI scoring.

### MVP Success Threshold

Closed Beta is successful if:

- Median CRIS among users completing both assessments is at least +8 points.
- At least 60% of completers improve by 5 or more points.
- AI and human review differ by no more than 8 points on average.

## 10. Core Metrics

### Activation

| Metric | Alpha Target | Closed Beta Target |
|---|---:|---:|
| First case start rate after signup | 70% | 75% |
| First case completion rate | 50% | 60% |
| Median time to first case start | < 3 min | < 2 min |

### Engagement

| Metric | Alpha Target | Closed Beta Target |
|---|---:|---:|
| Second case start rate | 35% | 45% |
| 3-case completion rate | 25% | 35% |
| D7 retention | 20% | 25% |
| D30 retention | Not measured | 20% |

### Quality

| Metric | Alpha Target | Closed Beta Target |
|---|---:|---:|
| Medical content issue rate | < 5% of completed cases | < 2% |
| Diagnosis leakage rate | 0 critical cases | 0 critical cases |
| Average scoring dispute rate | < 10% | < 5% |
| App store rating | Not measured | 4.3+ |

### Cost and Performance

| Metric | Alpha Target | Closed Beta Target |
|---|---:|---:|
| Median AI response latency | < 4 sec | < 3 sec |
| P95 AI response latency | < 10 sec | < 8 sec |
| Cost per completed case | <$0.60 | <$0.40 |
| AI availability | 99% | 99.5% |

## 11. Analytics Events

Required events:

- `user_registered`
- `case_started`
- `patient_message_sent`
- `patient_message_received`
- `exam_requested`
- `test_ordered`
- `hint_requested`
- `diagnosis_submitted`
- `case_completed`
- `case_abandoned`
- `feedback_viewed`
- `second_case_started`
- `medical_issue_reported`
- `diagnosis_leakage_detected`
- `scoring_dispute_submitted`
- `llm_error`
- `llm_cost_recorded`

Each event must include:

- `user_id`
- `session_id`
- `case_id`
- `chief_complaint`
- `difficulty`
- `timestamp`
- `app_version`

## 12. AI Safety and Medical Risk

### Safety Requirements

1. AI patient must not reveal the diagnosis before scoring.
2. AI patient must not claim to be a clinician.
3. AI patient must not provide treatment advice to the learner.
4. AI must respond from case ground truth, not open-ended medical knowledge.
5. Prompt injection attempts must be logged.
6. Suspected diagnosis leakage must immediately flag the session for review.

### Product Handling of Failures

| Failure | User Experience | Internal Action |
|---|---|---|
| AI timeout | Show retry option and preserve session state. | Log `llm_error`. |
| Low confidence response | Show cautious response and invite user to continue gathering data. | Flag for sampling. |
| Possible medical error | Let user report the issue from feedback screen. | Create review item. |
| Diagnosis leaked | End or reset affected turn with apology. | Flag case and model output. |
| Unsafe advice generated | Suppress output if detected. | Escalate as P0. |

## 13. Medical Review Process

### Before Release

Every case must be reviewed by at least one medically qualified reviewer before it can be marked approved.

Reviewer checklist:

- Diagnosis and aliases are correct.
- Key history and exam findings are medically plausible.
- Test results are coherent.
- Required treatment is guideline-consistent for educational purposes.
- Unsafe actions are listed.
- Rubric matches the intended learning objective.

### After Release

- All reported medical issues are reviewed before the next release.
- P0 medical issues pause the affected case immediately.
- Prompt changes require regression testing on all approved cases.
- Model changes require regression testing plus manual sample review.

## 14. Legal and Privacy Requirements

MVP must state clearly:

- Medlearn is an educational tool, not medical advice.
- Users must not enter real patient-identifying information.
- AI-generated content may be inaccurate.
- Real clinical decisions require licensed medical professionals.

MVP must define:

- What user data is stored.
- Whether conversations are used for product improvement.
- How users can delete their data.
- How long case conversations are retained.

## 15. Release Gates

### Internal Test to Alpha

Go only if:

- 15 cases are approved.
- 0 known P0 bugs.
- Diagnosis leakage test passes on all cases.
- First complete case can be finished end-to-end on iOS and Android.
- Cost tracking is active.

### Alpha to Closed Beta

Go only if:

- First case completion rate is at least 50%.
- Second case start rate is at least 35%.
- No unresolved P0 medical issues.
- Medical content issue rate is below 5% of completed cases.
- Median AI response latency is below 4 seconds.
- Cost per completed case is below $0.60.

### Closed Beta to Public Beta

Go only if:

- Median CRIS is at least +8.
- 3-case completion rate is at least 35%.
- D7 retention is at least 25%.
- Scoring dispute rate is below 5%.
- P95 AI response latency is below 8 seconds.
- Cost per completed case is below $0.40.

## 16. Open Decisions

| Decision | Owner | Needed By |
|---|---|---|
| Which country or curriculum anchors the first 15 cases? | Product + Medical reviewer | Before case writing |
| Who qualifies as medical reviewer? | Founder team | Before Alpha |
| Are assessment cases separate from practice cases? | Product | Before Alpha |
| What model is used for patient rendering and scoring? | AI lead | Before implementation |
| What is the exact retention policy for conversations? | Product + Legal | Before Alpha |
| What happens when free usage exceeds cost limits? | Product | Before Beta |
| Is HIPAA in scope or explicitly avoided by banning PHI input? | Legal | Before Alpha |

## 17. Key Risks

| Risk | Severity | Mitigation |
|---|---|---|
| AI leaks diagnosis during patient conversation | High | Ground-truth output checks, injection tests, leakage event, manual review. |
| Scoring feels unfair or inconsistent | High | Deterministic rubric, variance target, dispute tracking. |
| Users treat content as medical advice | High | Repeated education-only framing, no real patient workflows, no treatment advice. |
| Cost grows faster than usage value | Medium | Cost per completed case target, model routing, usage guardrails. |
| MVP too broad to ship | High | P0-only Alpha scope and explicit non-goals. |
| Cases are too few for repeat use | Medium | Track second case start and 3-case completion before expanding. |

## 18. Immediate Next Steps

1. Confirm MVP scope and non-goals.
2. Assign owners for open decisions.
3. Create the 15-case rubric template.
4. Build Alpha event tracking plan.
5. Define medical reviewer workflow.
6. Convert P0 features into implementation tickets.
