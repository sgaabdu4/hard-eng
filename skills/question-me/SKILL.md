---
name: question-me
description: Resolve material decisions with evidence-first questions when explicit or delegated by $he-plan.
---

# Question Me

## Boundary

- Evidence establishes current state; user decides desired state.
- Research only objective gaps needed for the delegated decision; never plan or implement.
- Never infer approval, intent, priority, scope, defaults, errors, permissions, retention, migration, rollout, or UI shape.
- Delegated choice = exact recorded scope only; never expand it.

## Route

| Invocation | Load | Completion |
|---|---|---|
| Planning stage delegated by `$he-plan` | [stage-planning.md](references/stage-planning.md) | Stage review + final user response returned |
| Direct question request | [direct.md](references/direct.md) | Every material decision accounted |

## Admission

- Decision status = `settled | objective-gap | user-decision | contradiction`.
- Inspect available code/tests/schema/contracts/config/history/runtime/notes before asking objective current-state questions.
- Objective evidence missing → delegate the bounded gap to `$research`; consume its result before asking.
- Ask only for future intent + priority + scope + success + trade-off + conflicting/inaccessible evidence.
- Current behavior may be accidental → ask whether to preserve it.
- Answer already recorded → reuse it; contradiction → show both claims + evidence + request resolution.
- Dependent decisions → one question at a time; independent decisions → one narrow group.
- Choice question → 2–3 mutually exclusive options + `Other`; each option states consequence.
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
- User correction → restate changed decision + downstream impact before continuing.

## Return

- Direct invocation → verified facts + approved/delegated decisions + pending decisions + contradictions + assumptions requiring confirmation + next question.
- Complete only when every material unknown is approved, delegated, proven irrelevant, or explicitly deferred with consequence.
- Any unresolved material decision → `CONCERNS`; never claim alignment.
