# Ship names the repository setting that forbids rebase merges

Status: Complete

## Outcome + scope

In a repository whose settings forbid rebase merges, `ship` stops at the ready check and at a failed merge with the "Rebase the branch on origin/main" step, which cannot help because the branch is current and the cause is the setting. Now both stops name the setting when GitHub reports no rebase and the setting is off.

Non-goals: merging by squash or merge commit, any new option, a setting read on a pull request that GitHub can rebase.

## Repository context

Owners: `.hooks/shipping.py` (`rebase_step`, new `rebase_problem`, new `merge_settings`), `.hooks/ship_actions.py` (`merge`), `.hooks/update_pr.py` (`merge_method`), `.agents/skills/he-ship/references/checks.md`.
Same cause: the other printed steps in `.hooks/shipping.py`, `.hooks/ship_actions.py` and `.hooks/review_bypass.py` were read for a step that a repository setting makes impossible. The review bypass already names its blockers ("branch protection has another merge requirement"); the commit cap and the behind-base step do not depend on a setting. No other step has this fault: none repaired.
Single source: the `gh repo view --json` reader had one copy in `merge_method`; it moved to `merge_settings` in `shipping.py` and both callers use it.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The coordinator set the change and its message; the coordinator reviews the commits before any push.

## Acceptance + steps

- [x] The ready check names the setting and prints no "Rebase the branch" step → `tests/test_ship_commits.py::test_a_repository_that_forbids_rebase_merges_is_named_as_the_cause`.
- [x] A failed merge names the setting → `tests/test_ship_commits.py::test_a_failed_merge_in_a_repository_that_forbids_rebase_merges_names_it`.
- [x] With the setting on, absent or unreadable, the present step stays → `tests/test_ship_commits.py::test_a_pr_github_cannot_rebase_keeps_the_rebase_step_unless_the_setting_is_false` and `::test_an_unreadable_setting_keeps_the_rebase_step`.
- [x] A pull request that GitHub can rebase makes no setting call → `tests/test_ship_commits.py::test_a_pr_github_can_rebase_never_reads_the_repository_setting`.

## Baseline + execution

Result: Passed
Evidence: before the change the first two tests failed with the "GitHub cannot rebase this PR onto main" text; the guards passed.
Execution: one builder session; tests first, one commit for the repair, one for the docs line, one for this plan.

## Risks + recovery

A setting read that fails keeps the old text, so the first cause is never hidden. Recovery: revert the repair commit.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `tests/test_ship_commits.py`, `tests/test_update_pr.py`, `tests/test_shipping.py`, `tests/test_ship_actions.py`, `tests/test_gate_speed.py` and `tests/test_skill_links.py` passed; the static gates and `hot-paths` on the three touched hooks passed. The Complete check is run by the coordinator.
Review: a reader that did not write the text compared the old and the new sentence of `checks.md` with its paragraph. It read the sentence one time, found the same meaning as the code, and found no conflict with "each refusal names its fix" or "squash and merge commits are refused".
E2E: N/A — no user journey; the tests drive `verify` and `merge` with the fake GitHub of the ship tests.
Retro: (1) Hard Eng fault that a project showed: a printed step that a repository setting makes useless → `tests/test_ship_commits.py::test_a_repository_that_forbids_rebase_merges_is_named_as_the_cause`. (2) The size rule limits a test file to 1000 lines, so the shared reader is patched in the update tests by its module name, one line.

Delivery target: Merge
Delivery: Pending — the coordinator reviews the commits, then ships.
