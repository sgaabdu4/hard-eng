# Fix check and Stop-hook defects seen in project sessions

Status: Ready

## Outcome + scope

Hard Eng stops failing good work in five situations projects hit:
- a plan written before the `Status:` field breaks `check` and the Stop hook although no plan changed;
- committing screenshots inside a Draft plan's folder demands a Complete plan;
- a second `check` in the same checkout overwrites the first run's `coverage/` reports and both report false failures;
- `git push 2>&1 | tail` fails a passing gate with `[Errno 35] write could not complete without blocking`;
- the Stop hook of a read-only session demands a plan because files were already untracked or modified when the session started.

Non-goals: CI's docs-only decision for plan assets, report paths per run, and other gates.

## Repository context

Owners:
- `.hooks/plans.py`: `field(..., "Status")` raises for a legacy plan inside `validate_plans`, `planning_feedback` and `build_in_progress`, and `validate_plans` counts every non-Markdown file as implementation.
- `.hooks/hard-eng.py` `check`: runs gates that write fixed report paths with no lock, and `main` writes to whatever stdout it inherits; ssh under `git push` sets the shared pipe non-blocking, so a full pipe raises `BlockingIOError`.
- `.hooks/agent_hooks.py`: SessionStart saves only the Git base, so `completion` counts every untracked or modified file as session work.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix the Hard Eng issues found in their other sessions.

## Acceptance + steps

- [x] With no plan changed, a plan without `Status:` is skipped; editing it still fails with its path → `test_plan_without_status_predates_the_status_field`.
- [x] Files inside a plan's folder keep a Draft plan valid; other non-Markdown files still require Complete → `test_plan_screenshots_stay_planning_work`.
- [x] A second `check` in the same checkout waits for the first to finish → `test_second_check_waits_for_the_first_in_the_same_checkout`.
- [x] `check` output to a non-blocking pipe with a slow reader completes without `Errno 35` → `test_check_output_survives_a_non_blocking_pipe`.
- [x] A session that changes nothing stops without checks even when files were dirty at SessionStart; editing one of those files still runs the check → `test_work_from_before_the_session_is_not_session_work`.

## Baseline + execution

Result: Passed
Evidence: Main `da2b0c5`. Each new test failed on the code before its fix: the legacy plan raised "plan needs one 'Status:' field, found 0", and the screenshot raised "plan is Draft; this check requires Complete".
Execution: One commit per defect.

## Risks + recovery

A waiting `check` holds the Stop hook until the other run finishes; the hook's timeout still applies. Recovery: revert the individual commit.

## ux_reference

N/A — hook and gate behaviour with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — run a real `hard-eng.py check` twice at once and through a non-blocking pipe.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
