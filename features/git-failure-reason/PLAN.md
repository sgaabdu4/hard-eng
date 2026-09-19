# Show why a shipping command failed

Status: Complete

## Outcome + scope

When `git` or `gh` exits nonzero during shipping, the error keeps its `<tool> query failed` prefix and appends the last line of the command's own stderr. With no stderr the message is unchanged. Nothing else changes: same exception types, same exit codes. No new file other than this plan.

## Repository context

Owner: `.hooks/shipping.py` `_run`, shared by `git`, `gh` and the delivery commands. It captured stderr and discarded it, so issue 126 surfaced only as `git query failed`. Callers that tolerate a failure catch `ShippingError` by type, and the one test that matches text matches the kept prefix. Delivery command failures are re-raised by `_delivery` with their own message, so project command output is still not echoed. The file was at its 700-line limit; one blank line between two adjacent type declarations was removed to stay within it.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for this message fix after PR 127 listed it as a remaining gap. Commit, PR and merge follow the go-ahead used for PRs 125 and 127.

## Acceptance + steps

- [x] A failing git command reports its reason after the prefix; a silent failure keeps the bare prefix → `test_failed_git_command_reports_its_own_reason` red before, green after.
- [x] Existing shipping and ship-action tests pass unchanged.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at b9aa5b0, hard-eng workflow run 35431449620 success.
Execution: Single session on `feature/git-failure-reason`.

## Risks + recovery

The appended line is whatever the tool wrote last to stderr, shown in the same terminal the tool would have written to. Git anonymizes credentials in remote URLs in its transport errors, but an agent copying the line elsewhere must still apply publication privacy. Only the last line is kept, so a multi-line explanation is shortened. Recovery is reverting this branch.

## ux_reference

N/A — command-line error text only; no product appearance.

## Verification

Result: Passed
E2E: Passed — the real runner in this checkout, outside pytest, printed `Hard Eng: git query failed: error: No such remote 'no-such-remote'` for `git remote get-url no-such-remote` and the unchanged `Hard Eng: git query failed` for a quiet `rev-parse --verify --quiet missing`.
Evidence: The new test failed before the change and passes after; `tests/test_shipping.py` and `tests/test_ship_actions.py` 89 passed. The full check result is recorded in the delivery line below.

Delivery target: Merge
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks passed, 776 tests and 4 performance checks. PR CI, merge, merged-main CI and cleanup remain unverified.
