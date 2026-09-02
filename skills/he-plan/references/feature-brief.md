# Feature Brief Contract

## Workflow

1. Read repository evidence + canonical owners + inspect the relevant current product screen + affected flow → current truth known → `record-step code-study`; visual reference → `atomic-ui` verifies root `DESIGN.md` + production owners; current screenshots ground the proposed state but never substitute for it.
2. External facts → `research` → `record-research`; fill seven sections with accepted current state → no planning history.
3. Run Applicability Scan → `record-step edge-scan` (every axis, `none` when no hit) → material results recorded in the brief only.
4. Resolve material uncertainty via `question-me` dependency frontiers + batch independent decisions + no per-section approval → `record-step decisions` after every answer; record its not-yet-specifiable items as `deferred` and its user-action items as `blocked_on`, then continue.
5. Enumerate every vertical slice with `depends_on` → `record-step slices`; run `plan_state.py validate` → deterministic PASS with `plan_steps=5/6`.
6. Present lean brief + exact risk/unknowns → `ux_reference_markdown` emitted → display it verbatim in chat before approval, never only its path; HTML reference + in-app browser available → localhost preview opened and kept live for user review.
7. `validate` emits `ready_for_approval=yes` + explicit current-prompt autonomous directive → pass that directive to `plan_state.py approve --approval-reply` → `he-build`; no second approval question.
8. Standard mode → show the complete brief + the closing question (split into tickets? which probed tracker?) in one message → user's plain yes (any literal reply) → `record-step closing` with the ticket answer + pass the same reply to `plan_state.py approve --approval-reply` → show the printed handoff block → `he-build`; decision answers + pre-brief replies = reject.

- Decision answer to an open question + reply before the complete brief ≠ approval; never synthesize the reply.

## Shape

- Path = `features/<feature-slug>/PLAN.md`.
- State block = script-owned; prose sections = living accepted state.
- Required order = Outcome → Non-goals → Material decisions → Acceptance examples → Affected canonical areas → Risk and rollback → First vertical slice.
- Entry = concise bullets; evidence links/commands only when they change a decision.
- Placeholder = allowed during planning + forbidden at Ready-to-build approval.
- Material decisions requires `ux_reference` + `ux_reference_sources`; no visual surface → both `n/a`.
- Non-`n/a` reference = absolute local lifecycle-media image outside the repository + sibling `<image>.visual-review.json` + `ux_reference_sources = DESIGN.md + <repo-relative-production-owner>...`; canonical `e2e` receipt PASS binds exact route, real baseline, reviewed delivery images, source hashes + presentation label; reference media stays outside Git.
- Existing screen = render exact running route OR production component; planning-only static data on that route uses label `static preview on current app screen`; standalone HTML/ImageGen/invented combined page = invalid.
- Genuinely new surface = nearest existing flow + explicit gap + standalone concept allowed; `new-ui-concept` may not represent an existing screen.
- Every affected screen/state = one reviewed delivery screenshot shown in chat; current screenshot alone, path-only, `file://`, unopened URL, missing sidecar, wrong route, or source/digest mismatch = invalid.
- User visual feedback = update same preview → refresh + recapture + redisplay before approval; superseded visual is invalid.
- Efficiency = once desired UI behavior is settled, prepare the visual while remaining independent read-only brief discovery runs in parallel; when delegation is user-authorized, use one bounded read-only design-forensics sub-agent, otherwise the main agent performs the same pass; no extra model review, serial design stage, or separate design approval round.

## Frozen Constraints

- Frozen = Outcome + Non-goals + Material decisions + Acceptance examples + `risk_level` + `critical_overlay`.
- Approval fingerprint = frozen content only.
- Changed frozen bytes after approval = deterministic FAIL → restore approved bytes; reopen only when accepted constraints materially changed.
- Engineering context = Affected canonical areas + rollback + `deferred` + `blocked_on` + First vertical slice; edit without reapproval.

## Risk

- `risk_level = standard|critical`.
- `critical_overlay = none` for standard.
- Critical = payment/auth/security/privacy/destructive-data/irreversibility OR unresolved material safety uncertainty.
- Critical overlay = named risky slice + boundary owner + failure/recovery/rollback + negative proof.
- `rollback` = safest recovery action or `not-applicable: <reason>`.
- `deferred` = visible decision not yet precisely phrasable + what must sharpen it, or `none`; graduate it when an accepted answer sharpens it; never a reason to hold the brief.
- `blocked_on` = exact user action outside the agent + dependent slice, or `none`; it delays approval only when it changes a frozen constraint.
- Both rows are living engineering context; recording one keeps unblocked planning and building moving.

## Applicability Scan

- Scan once = actors/permissions + happy/empty/error/retry/recovery + state/data lifecycle + delivery form/lifetime + external/concurrency/idempotency boundaries + accessibility + rollout/rollback/observability.
- Delivery form/lifetime = record only when one-off/local versus repository/deployed changes observable operation + durable ownership + external/risk boundary.
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
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given an authorized editor, when they publish a valid draft, then its public URL resolves.
- Given a viewer, when they attempt to publish, then access is denied without changing the draft.

## Affected canonical areas
- Draft command owner + authorization policy + publish route.

## Risk and rollback
- risk_level = critical
- critical_overlay = S-1 authorization + no-unauthorized-write proof
- rollback = disable the publish route and preserve drafts.
- deferred = public URL format; sharpens once the first published draft exists.
- blocked_on = none

## First vertical slice
- S-1 = authorized publish command → stored published state → visible URL.
- proof = focused command tests + denied-role test + one end-to-end publish scenario.
```
