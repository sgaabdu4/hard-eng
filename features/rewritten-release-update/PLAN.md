# Run full checks when the old release left upstream history

Status: Complete

## Outcome + scope

A project's Hard Eng update names the old and new release. After an upstream history rewrite, the old release is not in the upstream history. The scaffold-only check stopped with a Git traceback, so the project's CI failed. Now that check returns "not proven", and the project's full checks run. Non-goals: proving the update some other way, changing which releases count as verified.

## Repository context

Owner: `.hooks/update.py` (`check_scaffold_update`); test in `tests/test_updates.py`.
Same cause: after the rewrite, marker-only commits in installed projects failed with `git merge-base --is-ancestor <old> <new>` in `fetch_sources`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-22 to fix the CI failures across projects at their source in Hard Eng.
Decided: an unproven update gets the full checks, the same as any other change. The verified-release rule still raises.

## Acceptance + steps

- [x] An update whose old release cannot be fetched or is not an ancestor returns False instead of raising → `tests/test_updates.py::test_unproven_scaffold_update_is_not_trusted`.

## Baseline + execution

Result: Passed
Evidence: the new test failed with `CalledProcessError` before the change; it passes after it, beside the unverified-release case.
Execution: One builder, this session.

## Risks + recovery

A network failure while cloning upstream also falls back to the full checks. That is stricter, not weaker. Recovery: revert this commit.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/develop` in the cloud container; PR CI runs it with every toolchain.
E2E: N/A — no user journey; the test drives the real `check_scaffold_update` after a real update.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
