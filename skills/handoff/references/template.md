# Handoff Document Template

- Every section present; nothing to record → explicit `None`; placeholder text forbidden.
- Claims not directly re-verifiable by the reader = tagged `Verified | Inferred | Unknown`.
- Git receipts = current at write time: branch + commit + `git status` + `git diff --stat`.
- Terse via pointers, complete via sweep: artifact-backed content = `Pointers` entry; conversation-only content = inlined; every user ask/correction/constraint accounted for by exactly one section.

```md
# HANDOFF — <UTC timestamp> — <repo> @ <branch> <commit>

## Goal
- <accepted outcome + success criteria + requester constraints>
- Next-session focus: <invocation arguments | inferred continuation>

## State
- Done: <completed work + proof/receipt>
- In progress: <exact stopping point + where partial work lives>
- Not started: <remaining scope>

## Decisions
- <decision = reason; user-approved | agent-chosen>

## Files
- Changed: <path = what changed>
- Created/generated: <path = purpose; source vs generated separated>
- Relevant untouched owners: <path = why the next session needs it>

## Pointers
- <artifact path or URL = one-line gist; brief | plan | ADR | issue | PR | diff | doc>

## Verification
- <command run = result (pass/fail + key output)>
- Environment: <versions/services/config/flags that differ from repository default>

## Avoid
- <failed attempt | rejected approach | out-of-scope item = why>

## Open
- Blockers: <blocker = owner/authority>
- Questions: <unresolved material decision awaiting the user>
- Assumptions: <unverified assumption = how to verify>

## Skills
- <skill name = why the next session should invoke it>

## Next
1. <first concrete action = expected proof>
2. <subsequent ordered steps>
```

- `Next` step 1 = executable without any question to the user.
- Uncommitted work = say so explicitly + list paths; clean tree = say clean.
