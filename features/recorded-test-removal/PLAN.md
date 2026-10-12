# Allow recorded removal of unneeded tests

Status: Complete

## Outcome + scope

The assertion-loss check accepts deleting a test whose code remains when the change's plan records `Removed test: <path> :: <test name> :: <reason>`. Only the named test in the named file is exempt, and the name must appear in that deleted test. Unrecorded or reasonless deletions still fail. Non-goals: other switch-off rules, retired-code handling from #250.

## Repository context

Owner: `validate_suppressions` and `lost_assertions` in `.hooks/comments.py`; tests in `tests/test_comments.py`; guidance in `.agents/skills/he/references/testing.md`. AGENTS.md already allows deleting a test when its protection and replacement proof or redundancy are stated; the check had no way to read that statement (issue #277).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix #277, run an adversarial review loop, then open and merge the PR.

## Acceptance + steps

- [x] A plan line with path, name and reason lets that deleted test pass the check.
- [x] A missing reason, a different test name or a different file still fails.
- [x] The failure message shows the accepted form.
- [x] A shared name prefix, a name only in a test body, and a body line quoting the name do not exempt a test.
- [x] Multi-line and `test.each` declarations can be recorded.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: Five parameterised cases in `tests/test_comments.py`; the two allowed cases failed before the change and pass after; all 129 comment-check tests pass.
Execution: One builder; one owner change.

## Risks + recovery

A broad test name could match more than intended in the same file; the entry is reviewable in the plan diff. Recovery: tighten the name in the entry.

## ux_reference

N/A — check behaviour with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` → exit 0; 1,503 tests passed. Four Codex adversarial review rounds on gpt-6-astra: rounds 1-3 findings fixed (exact names, declaration-only names, multi-line and `test.each` declarations); escaped quotes in names and assertions inside a deleted `afterEach` hook skipped as rare, with the check failing safe.
E2E: N/A — hook logic covered by fixture repositories in the test suite.

Delivery target: Merge
Delivery: Pending — PR checks, rebase merge, main CI.
