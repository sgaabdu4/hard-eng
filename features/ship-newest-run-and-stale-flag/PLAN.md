# Ship judges the newest run of each check and names a stale rebase report

Status: Complete

## Outcome + scope

Two correct pull requests were refused at the ready check. An older cancelled or failed run of a check blocked the review bypass although the newer run of that check passed. GitHub kept the "cannot rebase" flag for more than 30 minutes after a force-push, so the printed step could not help. Now the bypass judges each check by its newest run, and a stale rebase report on a current branch says to close the pull request and open it again.

Non-goals: any other change to what the bypass allows, merging by squash or merge commit, a change to the update command.

## Repository context

Owners: `.hooks/review_bypass.py` (`bypass_problem`, `_REVIEW_QUERY`), `.hooks/shipping.py` (`_run_sort_key`, `_checks`, `_current_with_base`, `rebase_problem`), `.hooks/ship_actions.py` (`merge`), `.agents/skills/he-ship/references/checks.md`.
Same cause: the update command got its cancelled-run rule in an earlier change (`judged_runs` in `.hooks/update_pr.py`), and ship got the repository setting message in `features/ship-names-rebase-setting/PLAN.md`; both helped and are kept. Searched `.hooks/` for `statusCheckRollup`, a rollup `state` and `rebaseable`: `.hooks/update_pr.py` reads `statusCheckRollup` from `gh pr view` (own rule, see below); `.hooks/ship_actions.py` reads `rebaseable` on a failed merge (gets the same hint in this change); `.hooks/shipping.py` reads `rebaseable` once at the ready check (changed). No other place reads them.
Single source: the rule "the newest run of a check decides" had one owner, `_run_sort_key` in `.hooks/shipping.py`, used by `_checks`; it becomes `newest_run`, and the bypass uses it too. The compare call had two copies, in `_current_with_base` and in `_pull_request_head` of `.hooks/ci_usage.py`; it becomes `_compare`, and both callers and the stale-flag reader use it. `judged_runs` in `.hooks/update_pr.py` stays apart: it reads the JSON of `gh pr view`, which has no run id, and sets aside only a cancelled run. Searched `.hooks/` for other copies of the order and of the compare call: none stays.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer reported both faults; the coordinator set the changes and reviews the commits before any push.

## Acceptance + steps

- [x] The bypass allows a check whose older run was cancelled or failed and whose newer run passed → `tests/test_review_bypass.py::test_the_bypass_judges_each_check_by_its_newest_run` rows `older-cancelled-newer-passed` and `older-failed-newer-passed`.
- [x] The bypass refuses a newest run that failed, was cancelled, is not completed or has no valid id, the newest failed run of two same-named checks in different workflows, a status context that is not SUCCESS, and an incomplete context list → `tests/test_review_bypass.py::test_the_bypass_judges_each_check_by_its_newest_run` (the other rows).
- [x] A stale "cannot rebase" report on a current branch with no merge commit says to close and open the pull request → `tests/test_ship_commits.py::test_a_stale_cannot_rebase_report_says_to_close_and_open_the_pull_request`.
- [x] A branch that is behind, has a merge commit, has an unreadable or incomplete comparison keeps the present step → `tests/test_ship_commits.py::test_a_cannot_rebase_report_keeps_the_rebase_step_unless_the_branch_is_current`.
- [x] The repository setting message makes no comparison call, and a pull request that GitHub can rebase makes no new call → `tests/test_ship_commits.py::test_the_setting_message_and_a_rebaseable_pr_add_no_comparison_call`.
- [x] A failed merge gives the same hint → `tests/test_ship_commits.py::test_a_failed_merge_on_a_current_branch_gives_the_stale_report_hint`.

## Baseline + execution

Result: Passed
Evidence: before the change the rows `cancelled-then-passed`, `failed-then-passed`, `newest-listed-first` and `no-database-id` of the bypass test failed (the old code read the rollup state and let a run with no id pass), the check-naming test failed, and the stale-report and failed-merge tests failed with the old "GitHub cannot rebase this PR onto main" text; the refused rows and the guards passed.
Execution: one builder session; tests first, one commit for each fault, one for the docs lines, one for this plan.

## Risks + recovery

A comparison that fails or lists too few commits keeps the old text, so no new refusal appears. The bypass is stricter on a check run without a run id; it refuses, as the required-check order does. Recovery: revert the repair commit.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `tests/test_review_bypass.py`, `tests/test_ship_commits.py`, `tests/test_shipping.py`, `tests/test_ship_actions.py`, `tests/test_gate_speed.py`, `tests/test_update_pr_checks.py`, `tests/test_ci_usage.py` and `tests/test_skill_links.py` passed (321 tests); format, lint, complexity, annotations, types, dead-code, duplicates, declarations, shipped-format and shipped-focused-tests passed; `hot-paths` on the three touched hooks found 0. The Complete check is run by the coordinator.
E2E: N/A — no user journey; the tests drive `verify`, `bypass_problem` and `merge` with the fake GitHub of the ship tests.
Retro: (1) Hard Eng fault that a project showed: ship judged a check by every run of the head commit and trusted a rebase flag that GitHub can leave stale → `tests/test_review_bypass.py::test_the_bypass_judges_each_check_by_its_newest_run` and `tests/test_ship_commits.py::test_a_stale_cannot_rebase_report_says_to_close_and_open_the_pull_request`. (2) `.hooks/shipping.py` reached the 1000 line limit, so the rebase messages moved to `.hooks/ship_actions.py`, which owns the merge stage. (3) The tests repeated one set-up three times; the duplicates gate caught it → the set-ups are shared helpers.

Delivery target: Merge
Delivery: Pending — the coordinator reviews the commits, then ships.
