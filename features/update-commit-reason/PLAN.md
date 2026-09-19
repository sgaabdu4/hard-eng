# Show why the update commit was rejected

Status: Complete

## Outcome + scope

When the updater's `git commit` exits nonzero, the raised error carries the last five lines of the commit's own output, so the SessionStart message and a manual updater run both show the project hook's reason (issue 129). The full output still goes to stderr as before, and the rollback is unchanged. No new file other than this plan.

## Repository context

Owner: `.hooks/update.py` `commit_update`. It sent the commit's stdout to the hook process's stderr and raised `CalledProcessError`, whose text holds only the command and exit status. Agent harnesses do not pass SessionStart stderr into context, and the rollback restores the files, so the reason was lost. `session_context` in `.hooks/agent_hooks.py` and `setup.py` already format `str(error)` for any `SubprocessError`, so placing the reason in the error reaches both callers without changing them. A timeout keeps its own `TimeoutExpired` text.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open Hard Eng issues; 129 was the only one open. The error type becomes the base `SubprocessError` because `CalledProcessError` cannot carry the reason in its text; every caller already catches the base type. Commit, push and PR await the user's go-ahead.

## Acceptance + steps

- [x] A commit rejected by a project hook reports the hook's message in the raised error, and the scaffold is still rolled back → `test_failed_commit_rolls_back_scaffold` extended; red before, green after.
- [x] The Husky rejected-commit path still rolls back → existing test, expecting `SubprocessError`.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 46b270c, hard-eng workflow run 35432202670 success.
Execution: Single session on `feature/github-hard-eng-issues-f939b3`.

## Risks + recovery

The appended lines are whatever the project's hooks printed, now placed in the agent's context as well as stderr; an agent copying them elsewhere must still apply publication privacy. Only the last five lines are kept, so a longer explanation is shortened; the full output remains on stderr. Recovery is reverting this branch.

## ux_reference

N/A — command-line error text only; no product appearance.

## Verification

Result: Passed
E2E: Passed — outside pytest, a scratch project installed at b9aa5b0 with a rejecting pre-commit hook ran the real `session_context` against upstream 46b270c with stderr discarded. Main's code printed only `returned non-zero exit status 1`; this branch printed `Hard Eng update failed: git commit exited 1: budget check: AGENTS.md is 1200 tokens over its budget`. The project stayed at b9aa5b0 with a clean tree both times.
Evidence: The extended test failed before the change and passes after; `tests/test_updates.py` and `tests/test_agent_hooks.py` 108 passed. The full check result is recorded in the delivery line below.

Delivery target: Merge
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks passed, 776 tests and 4 performance checks. A first run failed format and lint on this change (line wrap, explicit `check=False`); both were fixed before the passing run. Commit, PR CI, merge, merged-main CI and cleanup remain unverified.
