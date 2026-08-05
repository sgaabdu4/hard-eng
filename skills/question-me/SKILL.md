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

- Decision status = `settled | objective-gap | user-decision | unspecifiable | blocked-external | out-of-scope | contradiction`.
- Accepted outcome unnamed = first frontier; it bounds the inventory; scope/priority/trade-off questions never precede it.
- Before every question = refresh code/tests/schema/contracts/config/history/runtime/notes; evidence-settled item → record + never ask.
- Objective gap → `research`; depth = gap breadth, local owner lookup → full external primary-source route; unresolved after `research` → reclassify `user-decision` or `blocked-external`.
- Ask only desired intent + priority + scope + success + trade-off + unresolved evidence conflict.
- Unspecifiable = decision visible + not yet precisely phrasable; sharpness test = phrasing, never answerability; record + never ask + graduate when an accepted answer sharpens it.
- Out-of-scope = ruled beyond the accepted outcome; record once + never ask + never graduate; return requires an accepted outcome change.
- Blocked-external = decision waiting on user action outside the agent (access/account/credential/data/environment); return exact checklist + blocked dependents in that same turn → continue every independent decision; asking the undecidable question + idle waiting forbidden.
- Delivery form/lifetime = material only when one-off/local versus repository/deployed changes observable operation + durable ownership + external/risk boundary.
- Current behavior may be accidental → ask whether to preserve it.
- Recorded answer → reuse + recompute dependencies; next frontier branches from accepted answers; prewritten downstream questionnaire forbidden → record as `unspecifiable`; contradiction → show claims/evidence → request resolution.
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

- Direct invocation → verified facts + accepted/delegated decisions + pending decisions + `unspecifiable` items + `out-of-scope` rulings + `blocked-external` checklists + contradictions + assumptions requiring confirmation + next question.
- Complete only when every material unknown is approved, delegated, proven irrelevant, ruled `out-of-scope`, or explicitly deferred with consequence.
- Remaining `unspecifiable` or `blocked-external` item → `CONCERNS` + exactly what must settle or be done first.
- Any unresolved material decision → `CONCERNS`; never claim alignment.
