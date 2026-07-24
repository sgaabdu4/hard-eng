---
name: question-me
description: Resolve material decisions with evidence-first questions when explicit or delegated by $he-plan.
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
| Feature Brief alignment delegated by `$he-plan` | [feature-brief.md](references/feature-brief.md) | Material decisions settled + readiness returned |
| Direct question request | [direct.md](references/direct.md) | Every material decision accounted |

## Admission

- Decision status = `settled | objective-gap | user-decision | contradiction`.
- Inspect available code/tests/schema/contracts/config/history/runtime/notes; objective gap → bounded `$research` first.
- Ask only desired intent + priority + scope + success + trade-off + unresolved evidence conflict.
- Current behavior may be accidental → ask whether to preserve it.
- Recorded answer → reuse; contradiction → show claims/evidence → request resolution.
- Dependent → one question; independent → one bounded batch; choice → 2–3 exclusive consequences + `Other`.
- Unlimited material questions; zero repeated, speculative, or downstream-premature questions.

## Question

- Every user-facing question = one bullet; dependent decisions never share a bullet.

```md
### Evidence
- <verified current fact + path/URL>

### Unresolved
- <decision or contradiction>

### Why it matters
- <material consequence>

### Questions
- **Q1. <one clear question>?**
  - **Option 1:** <choice + consequence>
  - **Option 2:** <choice + consequence>
  - **Other:** <unlisted choice>

### Recommendation
- **Option:** <recommended choice>
- **Reason:** <evidence-backed reason>
- **Trade-off:** <cost>
- **Status:** Awaiting approval.
```

- Omit options when the answer is inherently open-ended.
- Recommendation = unapproved until explicit acceptance.
- Ambiguous/partial answer → record confirmed portion only → ask the smallest unresolved remainder.
- User correction changing accepted outcome/risk → restate exact delta + downstream impact before continuing.
- Clear correction to reversible engineering detail → record + continue without approval.

## Return

- Direct invocation → verified facts + accepted/delegated decisions + pending decisions + contradictions + assumptions requiring confirmation + next question.
- Complete only when every material unknown is approved, delegated, proven irrelevant, or explicitly deferred with consequence.
- Any unresolved material decision → `CONCERNS`; never claim alignment.
