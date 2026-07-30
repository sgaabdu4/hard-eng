---
name: question-me
description: Resolve material decisions with evidence-first questions when explicit or delegated by he-plan.
---

# Question Me

## Boundary

- Evidence = current state; user = desired state.
- Research objective gaps only; never plan/implement.
- Never infer material outcome/UX/default/policy/security/privacy/data-loss/irreversible intent.
- Reversible engineering detail = agent-owned + excluded from the decision inventory.
- Delegated scope = exact Feature Brief alignment boundary.

## Route

| Invocation | Load | Completion |
|---|---|---|
| Feature Brief alignment delegated by `he-plan` | [feature-brief.md](references/feature-brief.md) | Material decisions settled + readiness returned |
| Direct question request | [direct.md](references/direct.md) | Every material decision accounted |

## Admission

- Decision status = `settled | objective-gap | user-decision | contradiction`.
- Before every question = refresh code/tests/schema/contracts/config/history/runtime/notes + resolve objective gaps through bounded `research`; evidence-settled item → record + never ask.
- Ask only desired intent + priority + scope + success + trade-off + unresolved evidence conflict.
- Delivery form/lifetime = material only when one-off/local versus repository/deployed changes observable operation + durable ownership + external/risk boundary.
- Current behavior may be accidental → ask whether to preserve it.
- Recorded answer → reuse + recompute dependencies; next frontier branches from accepted answers; prewritten downstream questionnaire forbidden; contradiction → show claims/evidence → request resolution.
- Question cadence = one dependency frontier per turn → batch every mutually independent material decision in that frontier → wait once; dependent decisions wait for upstream answers.
- Unlimited material questions; zero repeated, speculative, or downstream-premature questions.

## Question

- Every turn = one user-facing decision set + one question bullet per independent material decision.

```md
### Evidence
- <verified current facts + paths/URLs>

### Questions
- **Q1. <independent clear question>?**
  - **Option 1:** <choice + consequence>
  - **Option 2:** <choice + consequence>
  - **Other:** <unlisted choice>
- **Q2. <independent clear question>?**
  - **Option 1:** <choice + consequence>
  - **Option 2:** <choice + consequence>
  - **Other:** <unlisted choice>

### Recommendation
- **Q1:** <recommended option + evidence-backed reason + trade-off>
- **Q2:** <recommended option + evidence-backed reason + trade-off>
- **Status:** Awaiting approval.
```

- Omit options when the answer is inherently open-ended.
- Every recommendation = unapproved until explicit acceptance.
- Ambiguous/partial answer → record confirmed portion only → ask the smallest unresolved remainder.
- User correction changing accepted outcome/risk → restate exact delta + downstream impact before continuing.
- Clear correction to reversible engineering detail → record + continue without approval.

## Return

- Direct invocation → verified facts + accepted/delegated decisions + pending decisions + contradictions + assumptions requiring confirmation + next question.
- Complete only when every material unknown is approved, delegated, proven irrelevant, or explicitly deferred with consequence.
- Any unresolved material decision → `CONCERNS`; never claim alignment.
