# Feature Brief Contract

## Workflow

1. Read repository evidence + canonical owners → current truth known.
2. Fill seven sections with accepted current state → no planning history.
3. Run Applicability Scan → material results recorded only.
4. Resolve material uncertainty via `$question-me` → independent choices in one bounded batch + dependent choices sequentially until aligned + no per-section approval.
5. Run `plan_state.py validate` → deterministic PASS.
6. Present lean brief + exact risk/unknowns → reviewable current state.
7. Ask once **Ready to build this Feature Brief?** → explicit answer.
8. Yes → `plan_state.py approve` → `$he-build` when implementation is in scope.

## Shape

- Path = `features/<feature-slug>/PLAN.md`.
- State block = script-owned; prose sections = living accepted state.
- Required order = Outcome → Non-goals → Material decisions → Acceptance examples → Affected canonical areas → Risk and rollback → First vertical slice.
- Entry = concise bullets; evidence links/commands only when they change a decision.
- Placeholder = allowed during planning + forbidden at Ready-to-build approval.

## Frozen Constraints

- Frozen = Outcome + Non-goals + Material decisions + Acceptance examples + `risk_level` + `critical_overlay`.
- Approval fingerprint = frozen content only.
- Changed frozen bytes after approval = deterministic FAIL → restore approved bytes; reopen only when accepted constraints materially changed.
- Engineering context = Affected canonical areas + rollback + First vertical slice; edit without reapproval.

## Risk

- `risk_level = standard|critical`.
- `critical_overlay = none` for standard.
- Critical = payment/auth/security/privacy/destructive-data/irreversibility OR unresolved material safety uncertainty.
- Critical overlay = named risky slice + boundary owner + failure/recovery/rollback + negative proof.
- `rollback` = safest recovery action or `not-applicable: <reason>`.

## Applicability Scan

- Scan once = actors/permissions + happy/empty/error/retry/recovery + state/data lifecycle + external/concurrency/idempotency boundaries + accessibility + rollout/rollback/observability.
- Record only material results in Material decisions + Acceptance examples + Risk and rollback.
- Irrelevant axis = omit; no required N/A prose.

## Example

```md
## Outcome
- A signed-in editor can publish a draft and see its public URL.

## Non-goals
- Draft collaboration is excluded.

## Material decisions
- Existing authorization policy remains canonical.

## Acceptance examples
- Given an authorized editor, when they publish a valid draft, then its public URL resolves.
- Given a viewer, when they attempt to publish, then access is denied without changing the draft.

## Affected canonical areas
- Draft command owner + authorization policy + publish route.

## Risk and rollback
- risk_level = critical
- critical_overlay = S-1 authorization + no-unauthorized-write proof
- rollback = disable the publish route and preserve drafts.

## First vertical slice
- S-1 = authorized publish command → stored published state → visible URL.
- proof = focused command tests + denied-role test + one end-to-end publish scenario.
```
