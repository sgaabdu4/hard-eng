# Check a force-pushed branch against its parent

Status: Complete

## Outcome + scope

When a push rewrites a branch, GitHub gives the old branch tip as the comparison base. That commit is not in the new history, so the check stopped with "Cannot verify plan scope" and recorded a red result. Now a push check whose base is outside the history compares with HEAD's parent and says so. Pull request checks keep the old strict failure. Non-goals: fetching the old tip, changing the shipped workflow.

## Repository context

Owner: `.hooks/ci_setup.py` (`push_base`, next to `require_ci_base`); callers `check` and `impact` in `.hooks/hard-eng.py`; test in `tests/test_affected_selection.py`.
Same cause: the main push run after the history rewrite failed this way. Installed projects then refused the marker update, because the new Hard Eng commit had no green check.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-22 to fix the CI failures across projects at their source in Hard Eng.
Decided: use HEAD's parent, because the rewritten tip came from a checked PR and its own changes are what the push adds. Only `push` events in GitHub Actions take this path.

## Acceptance + steps

- [x] A push check whose base is outside the history passes and compares with HEAD's parent; a PR check with the same base still fails → `tests/test_affected_selection.py::test_force_push_base_outside_history_compares_with_parent`.

## Baseline + execution

Result: Passed
Evidence: `uv run pytest -q tests/test_ci_setup.py tests/test_affected_selection.py` on `16c48a0a` passed; the push case failed with "Cannot verify plan scope" before `push_base` existed.
Execution: One builder, this session.

## Risks + recovery

A multi-commit force push checks only the last commit's changes. Force pushes to protected branches need an admin, and each commit came through a checked PR. Recovery: revert this commit.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/develop` in the cloud container: every other gate passes; tests 1894 passed, 6 failed. The same 6 fail on the base here (no Dart or Swift toolchain). CI runs them with the toolchains.
E2E: N/A — no user journey; the test drives the real `check` and `impact` in a Git repository with a missing push base.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
