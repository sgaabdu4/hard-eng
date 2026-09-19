# Clearer ship and plan errors from issues 121 to 124

Status: Ready

## Outcome + scope

Four self-filed issues reported errors that were correct but misleading. Each error now names the real cause, and the shipping contract documents that a required check must always conclude. A new agent rule asks for reproduced Hard Eng defects to be filed upstream with the user's approval. No check is weakened: `skipped` is still rejected, the plan is still read from the working tree, a merge with unfinished base CI still exits nonzero, and a field still needs text on its label's line. No new file other than this plan, no dependency, no workflow parser and no polling.

## Repository context

Owners: `.hooks/plans.py` `field` and `validate_plan` (issue 124), `.hooks/shipping.py` `_checks` and `_plan_target` (issues 121, 122, 123), `.hooks/ship_actions.py` `run` for the post-merge message (issue 123), `.agents/skills/he-ship/references/checks.md` for the shipping contract (issue 121) and `AGENTS.md`, which is installed into every project, for the upstream-filing rule. The `ready` stage already requires the local HEAD to equal the PR head, so the working tree is the right plan source and only the message was wrong. `.hooks/shipping.py` sits at the 700-line limit after this change.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix the open issues, test, push one PR and merge it, and chose message-only for issue 124, documentation plus a clearer error for issue 121, a nonzero exit for issue 123 and an ask-first `AGENTS.md` bullet for upstream filing.

## Acceptance + steps

- [x] Issue 124 → an empty `Evidence:` under `## Verification` reports the section and the same-line rule; a missing or duplicated field reports its count.
- [x] Issue 123 → a missing or unfinished required check raises `PendingCheck`; after a merge it reads as merged with base-branch CI unfinished and still exits nonzero; a concluded failure keeps the old wording.
- [x] Issue 121 → a `skipped` required check is still rejected, with a message naming the job-level condition; the contract states the rule.
- [x] Issue 122 → a plan absent from the checkout says to check out the PR's head branch; a path outside the repository has its own message.
- [x] `AGENTS.md` carries one bullet for filing reproduced Hard Eng defects upstream with approval and publication privacy.
- [ ] Full check passes and the PR merges with issues 121 to 124 closed.

## Baseline + execution

Result: Passed
Evidence: main at fcd7d8b, hard-eng workflow run 35326056821 success.
Execution: Single session on `feature/hard-eng-issues-review-d20fa3`, one commit per change.

## Risks + recovery

Anything matching the old message text would break; a repository search found no other consumer. `PendingCheck` subclasses `ShippingError`, so every existing handler still catches it. Recovery is reverting this branch.

## ux_reference

N/A — command-line messages and documentation only; no product appearance.

## Verification

Result: Pending
E2E: Required — run `ship --stage ready`, `merge` and `delivered` on this work's own PR; the merge step exercises the new unfinished-CI message against real GitHub.
Evidence: Pending

Delivery target: Merge
