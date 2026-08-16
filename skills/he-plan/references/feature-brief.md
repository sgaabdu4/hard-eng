# Feature Brief Contract

## Workflow

1. Read repository evidence + canonical owners + inspect the relevant current product screen + affected flow → current truth known; visual reference → `atomic-ui` verifies root `DESIGN.md` + production owners; current screenshots ground the proposed state but never substitute for it.
2. Fill seven sections with accepted current state → no planning history.
3. Run Applicability Scan → material results recorded only.
4. Resolve material uncertainty via `question-me` dependency frontiers + batch independent decisions + no per-section approval; record its not-yet-specifiable items as `deferred` and its user-action items as `blocked_on`, then continue.
5. Run `plan_state.py validate` → deterministic PASS.
6. Present lean brief + exact risk/unknowns → `ux_reference_markdown` emitted → display it verbatim in chat before approval, never only its path; HTML reference + in-app browser available → localhost preview opened and kept live for user review.
7. `validate` emits `ready_for_approval=yes` + explicit current-prompt autonomous directive → pass that directive to `plan_state.py approve --approval-reply` → `he-build`; no second approval question.
8. Standard mode → create/show one exact Ready-to-build challenge → matching case-sensitive `APPROVE <code>` → pass that exact reply to `plan_state.py approve --approval-reply` → `he-build`; other prose/yes/old code = reject.

- Decision answer to an open question + reply before the complete brief ≠ approval; never synthesize the reply.

## Shape

- Path = `features/<feature-slug>/PLAN.md`.
- State block = script-owned; prose sections = living accepted state.
- Required order = Outcome → Non-goals → Material decisions → Acceptance examples → Affected canonical areas → Risk and rollback → First vertical slice.
- Entry = concise bullets; evidence links/commands only when they change a decision.
- Placeholder = allowed during planning + forbidden at Ready-to-build approval.
- Material decisions requires `ux_reference` + `ux_reference_sources`; no visual surface → both `n/a`.
- Non-`n/a` reference = absolute local lifecycle-media image outside the repository + `ux_reference_sources = DESIGN.md + <repo-relative-production-owner>...`; bare remote URL forbidden → save approved bytes locally first; SVG with scripts, events, animation, embedded active content, or external resources forbidden; inspect or reuse a valid design-forensics receipt binding it to the current screen + affected flow, or the nearest existing flow + recorded gap for a new surface; reference media shows the proposed state in chat and is never committed.
- New/changed UI = one smallest sufficient proposed-state visual: ImageGen mock OR HTML/CSS wireframe rendered to an image; create/show it only after design-forensics evidence; current runtime screenshot alone fails semantic review.
- Valid prior design-forensics receipt = PASS + exact repository revision/source fingerprint + route + current screen/affected flow + states + production owners; unchanged receipt may be reused; changed, stale, or missing receipt → rerun the pass; remembered chat context alone is not evidence.
- HTML/CSS + in-app browser available = one reusable localhost server/tab + matching chat image; path-only, `file://`, or unopened URL fails delivery; browser unavailable = rendered chat image.
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
