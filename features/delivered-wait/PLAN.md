# Let delivered wait for the base branch checks

Status: Complete

## Outcome + scope

`ship --stage delivered` waits while a required check of the base branch's merge commit is missing, queued or running. It waits up to `shipping.ci_seconds` and asks again at a fixed interval. It fails only on a failed check or when the time limit ends, and it names which one. Non-goals: the ready stage, the check rules, the `ci_seconds` meaning for one check, and the delivery commands.

## Sources + coverage

Sources: N/A — a client report relayed in the task brief: delivered failed at once with "required check has not completed" and the client wrote a shell loop around it.
Deliverables: None

## Repository context

Owners:
- `.hooks/shipping.py` `verify` runs the delivered stage and `_checks` judges the required checks. The wait lives next to them.
- `.hooks/ship_actions.py` `merge` already turns an unfinished base check into "Merged; base-branch CI has not finished"; it now sees that text only after the wait ended.

Same cause: Searched for every caller of `_checks`: `verify` (ready and delivered) and `passed_branch_point`, which must not wait. Only the delivered call of `verify` waits.
Single source: The wait limit is `shipping.ci_seconds`; no new setting.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; the orchestrating agent asked for this item after a client wrote a shell loop around delivered.

## Acceptance + steps

- [x] A check that is queued or running at first, then passes, lets delivered pass after it waited → `tests/test_delivered_wait.py::test_delivered_waits_for_a_check_that_is_not_done_and_then_passes`.
- [x] A check with no run yet counts the same way → `tests/test_delivered_wait.py::test_delivered_waits_for_a_check_that_is_not_done_and_then_passes`.
- [x] A failed check fails at once, with no wait → `tests/test_delivered_wait.py::test_delivered_fails_at_once_on_a_failed_check_and_when_a_waited_check_fails`.
- [x] A check that is still not done at the limit fails and names the check and the limit → `tests/test_delivered_wait.py::test_delivered_names_the_check_and_the_limit_when_time_ends`.
- [x] A failed check fails at once even when a check listed before it has no run yet or is running → `tests/test_delivered_wait.py::test_delivered_fails_at_once_on_a_failed_check_listed_after_one_that_is_not_done`.
- [x] The ready stage still fails at once on a pending check → `tests/test_delivered_wait.py::test_ready_does_not_wait_for_a_pending_check`.

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` a125c746 the new tests fail: delivered raises "required check has not completed: build" (or "required check missing: build") at once, with no wait and no time limit text. The two near-miss tests (a failed check, and the ready stage) pass on that code.
Execution: One builder in a separate worktree of the repository: tests first, then `shipping.py`, then challenge and the Complete check.

## Risks + recovery

A project whose check never starts waits the full `ci_seconds` before delivered fails. That is the asked behavior. Recovery: revert the merge commit on `develop`.

## ux_reference

N/A — hook Python logic has no user interface.

## Verification

Result: Passed
Evidence: The new test file and its neighbors (shipping, delivered, CI usage, review bypass, ship actions, delivered design) passed: 271 tests. `check --static --plan-stage Ready` passed. The independent review found two faults in round one (a failed check waited behind an earlier unfinished one, and the real service line said not applicable); both are fixed, the first with a test that failed on the earlier code. Round two was clean at c777d835. The Complete check result is in the pull request.
E2E: N/A — the tests drive `verify` with a fake clock and a fake GitHub.
Real service: Passed — GitHub API: the changed wait ran one time, read-only, against the public repository's `develop` merge commit of PR 738. With its real two required checks it returned at once with no wait (1.0 s). With one check name that no run has, and a 20 second limit, it polled for 21.2 s and then refused with `required check missing: no-such-check; the time limit of 20 seconds (shipping ci_seconds) ended first`. Fields read from the real runs match the test reply: name, status and conclusion are text, id and the check suite id are numbers, the two times are text, the commit is 40 characters, and `output` is an object. No refusal that the code tells apart by its error was caused, because the wait only retries the one pending refusal, which this run caused. Nothing was written.
Retro: Delivered failed at once on a base check that was still queued or running, so a client wrapped it in a shell loop. `_stage_checks` is now the one owner of that wait, and `_checks` judges every required check before it reports one as pending. Escaped bug: found on the base branch; the red tests above are its repro.

Delivery target: Merge
Delivery: Pending — tests, checks, challenge, PR to `develop`, CI and merge.
