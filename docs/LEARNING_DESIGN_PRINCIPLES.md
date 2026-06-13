# Medlearn Learning Design Principles

> Source inspiration: Zhou Ling, *Cognitive Awakening* (`认知觉醒`)
> Purpose: convert the book's useful ideas into product behavior, not reproduce its text.

## Product Loop

Medlearn uses one primary learning loop:

```
choose one clear target
-> make an attempt
-> receive specific feedback
-> identify one blind spot
-> retry at the edge of current ability
-> rest or continue by choice
```

## Principles

### 1. Remove ambiguity before asking for effort

- Every learning entry point should expose one obvious next action.
- Large goals must become a concrete attempt with a visible completion condition.
- Feedback should name the exact gap instead of saying only "review more."

### 2. Train at the stretch edge

- Repeating mastered work creates activity without growth.
- Tasks that are far beyond current ability create anxiety and disengagement.
- Case difficulty should adapt from recent performance: foundation, progression, or challenge.

### 3. Produce before consuming

- Ask for a diagnosis, explanation, answer, or plan before revealing guidance.
- Treat learner output as the object that receives feedback.
- Explanations become more valuable after the learner has exposed a real uncertainty.

### 4. Build a feedback loop

- Scores locate problems; they do not define the learner.
- Feedback must be timely, specific, and immediately actionable.
- One high-value correction is better than a long undifferentiated study list.
- Safety-critical errors override normal score prioritization.

### 5. Exercise metacognition

- At decision points, ask the learner to pause briefly and state confidence.
- Let the learner name the single most uncertain judgment before seeing results.
- Compare confidence with performance so users learn when to trust or question their intuition.

### 6. Protect attention

- Prefer short, focused attempts over long sessions with divided attention.
- Keep the active screen centered on one task.
- Avoid unrelated rewards, feeds, alerts, and decorative gamification during a learning attempt.

### 7. Respect cognitive bandwidth

- A low-energy learner should be able to complete a smaller meaningful attempt.
- Completion should release pressure; additional practice is optional.
- Rest is part of learning consolidation, not evidence of weak commitment.

### 8. Preserve patience and agency

- Early clumsiness is expected when a skill is forming.
- Never shame breaks, mistakes, low scores, or uncertainty.
- Record cumulative work without resetting progress.
- Let the learner choose whether to retry, switch tasks, or stop after completing the minimum.

## Current Implementation

| Principle | Product behavior |
|---|---|
| Remove ambiguity | Home presents a one-case floor; feedback identifies one next action. |
| Stretch edge | Case difficulty is recommended from the latest same-complaint performance. |
| Produce first | Feynman, cases, and exams require an attempt before feedback. |
| Feedback loop | Same-case retry, focused Feynman revision, and weak-node exam retry. |
| Metacognition | Diagnosis submission records confidence and the largest uncertainty. |
| Protect attention | Case phases and focused retry banners keep one active objective visible. |
| Cognitive bandwidth | No upper limit, no streak loss, and stopping after the floor is valid. |
| Patience and agency | Cumulative learning days and non-shaming feedback language. |

## Evaluation

Track whether these mechanisms improve:

- targeted retry rate after feedback;
- score change between first attempt and focused retry;
- confidence calibration error;
- completion rate by recommended difficulty;
- voluntary continuation after the daily floor;
- learner-reported clarity of the next action.
