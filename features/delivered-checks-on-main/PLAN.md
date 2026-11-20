# Ship delivered finds its checks on main

Status: Complete

## Outcome + scope

`ship --stage delivered` for a PR into `main` finds each shipping check on the merge commit, because the canary now also runs on a push to `main`; a boundary violation through a re-export names that file; the join route says how a join merge meets `develop`'s linear history rule. Non-goals: a change to `ship`'s check lookup, fewer shipping checks, a change of branch protection.

## Sources + coverage

Sources: N/A — the request is the only source: the hotfix of PR 667 could not reach `ship --stage delivered` (`PendingCheck: required check missing: canary`), and the review of join PR 668 found the missing `via_path`.
Deliverables: None

## Repository context

Owners: `.github/workflows/canary.yml` (push branches and the `targets` step), `hard-eng.gates.json` (`shipping.checks`: `hard-eng`, `canary`), `.hooks/shipping.py::_checks` (reads each shipping check on the merge commit; unchanged), `.hooks/fallow_report.py::own_place` (the place and target of a finding), `AGENTS.override.md` (the hotfix and join route).
Same cause: a shipping check whose workflow does not run on a push to a branch that ship delivers to. Searched every workflow in `.github/workflows/`: `hard-eng.yml` runs on a push to `main` and `develop`; `canary.yml` ran on `develop` only; `pr-text.yml` and `release-source.yml` are not shipping checks. Not checked: whether hotfixes 648 and 652 ran `ship --stage delivered`.
Single source: the list of shipping checks stays in `hard-eng.gates.json`; the new test reads it there and reads the push branches from the workflows. Searched `tests/` for another copy of the check names: none.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer assigned the release work and its baseline repairs. Merge: maintainer, standing instruction to push, watch CI and rebase-merge Hard Eng task PRs when green ("keep going and merge when green", in the Hard Eng repo since 2026-10-07); this PR merges into `develop` by rebase.
Decisions:

1. Add `main` to the canary's push branches. The `canary` job then reports on each main merge commit, so `ship delivered` finds it. Changing `ship` to skip a check that a branch never runs would let a missing check pass.
2. A push to `main` compares with `github.event.before`, the main tip that the push replaced. `origin/main` is the pushed commit on a main push, so the old base listed no files, and the job would pass with nothing checked. With the real file list, `push_outputs` reuses the passed new-project runs of the merged PR head on the same tree, or runs the new projects.
3. `own_place` adds ` via <via_path>` when Fallow names the re-export file. Fallow 3.43.0 writes the field.
4. The join route notes the linear history rule and the restore, with the maintainer's yes for each join merge.
5. A candidate on `main`'s first-parent line (a push, a manual run or a rerun on `main`) installs its first parent, the main tip that it replaced; `main` takes only merge commits, so that parent is the release users had, and a rerun of the same commit gets the same parent. A `develop` commit that reached `main` inside a release (a `develop` job rerun after its release) stops with the reason instead of guessing a release, because a guess from the current `main` can pick one newer than the candidate. The old form installed the candidate itself and failed with no reason. On this repository, the tip `00f75479` resolves to `b0194d77`.
6. Each main commit gets its own concurrency group per event, so a later main run cannot cancel the canary that `ship delivered` needs for an earlier merge. `develop` and PR runs keep one group per ref.
7. The two installed-release tests move to `tests/test_canary_installed_release.py`, so `tests/test_release_canary.py` stays under 1,000 lines.

## Acceptance + steps

- [x] Each shipping check runs on a push to `develop` and to `main` → `tests/test_canary_reuse.py::test_each_shipping_check_runs_on_a_push_to_each_branch_that_ship_delivers_to` (failed on `12a630e4`: `canary` ran on `develop` only)
- [x] A push to `main` lists the files since the main tip it replaced; a push to `develop` still compares with `origin/main` → `tests/test_canary_reuse.py::test_a_push_lists_the_files_since_the_tip_it_replaced_on_main` (2 cases; the `main` case failed on `12a630e4` with `origin/main...HEAD`)
- [x] A main commit installs the main tip that it replaced → `tests/test_canary_installed_release.py::test_a_main_commit_installs_the_main_tip_that_it_replaced` (the test adds a later main merge, so the current main tip is not the answer; a form that took `origin/main^1` failed it); a develop commit already released stops with the reason → `tests/test_canary_installed_release.py::test_a_develop_commit_already_released_fails_with_the_reason` (earlier forms installed the merge commit itself, guessed a release from the current `main`, or needed a value only a push event gives)
- [x] A main push run is not cancelled by a later main run → N/A — GitHub evaluates the concurrency expression; actionlint checks its syntax
- [x] Each shipping check's workflow names `develop` and `main` in a plain push branch list as a list of names, with no pattern and no other filter, so no filter can hide a branch → `tests/test_canary_reuse.py::test_the_push_reader_counts_only_branches_named_in_a_plain_list` and `tests/test_canary_reuse.py::test_each_shipping_check_runs_on_a_push_to_each_branch_that_ship_delivers_to`
- [x] A boundary violation through a re-export prints the re-export file → `tests/test_report_findings.py::test_a_boundary_violation_through_a_re_export_names_the_file_it_passes` (failed on `12a630e4`)
- [x] The join route names the linear history step → N/A — route text for the maintainer's agents; no code reads it

## Baseline + execution

Result: Passed
Evidence: base `12a630e4`; its push runs of "Hard Eng" and "Canary" passed on `develop`.
Execution: one builder (the coordinator); the independent review before the push.

## Risks + recovery

- A main push now starts the canary. When the merged PR head already passed the new projects on the same tree, the job reuses those runs; otherwise it runs them on hosted runners, which are free for this public repository.
- Recovery: revert the commits; no data step.

## ux_reference

N/A — no screen changes; the change is a workflow, a log line and route text.

## Verification

Result: Passed
Evidence: `tests/test_canary_reuse.py`, `tests/test_release_canary.py` and `tests/test_canary_installed_release.py` 83 passed; jscpd over the gate's Python scope found 0 copies; `tests/test_report_findings.py` 29 passed; actionlint on `canary.yml` clean; ruff format and check, pyrefly (0 diagnostics) and vulture passed on the touched files. Not checked: a real push to `main` with the new trigger; the next release merge is the first one.
E2E: N/A — no user journey changes.
Real service: N/A — no outside service is called; the GitHub event field is read by the workflow.
Retro: (1) Escaped bug: `ship delivered` for hotfix PR 667 stopped on a canary check that `main` never runs. The gate that should have caught it is a test that ties the shipping checks to the workflow push branches → `tests/test_canary_reuse.py::test_each_shipping_check_runs_on_a_push_to_each_branch_that_ship_delivers_to`. (2) The join review finding (`via_path`) was declined without a record → fixed here with `tests/test_report_findings.py::test_a_boundary_violation_through_a_re_export_names_the_file_it_passes`. (3) The independent review found that the main-push update target had nothing to update, that a later main run could cancel an earlier one, and that the new test crashed on short trigger forms → `tests/test_canary_installed_release.py::test_a_main_commit_installs_the_main_tip_that_it_replaced`, Decision 6, and the trigger normalising in the shipping check test. The second review found that a rerun of a released develop job picked an unreleased baseline, and that an unfiltered push did not count → `tests/test_canary_installed_release.py::test_a_develop_commit_already_released_fails_with_the_reason` and the unfiltered push branch rule in the shipping check test. The third review found that the guessed release could be newer than the candidate, that the new tests copied each other, and that a filtered push still counted → Decision 5 (pinned release, clear stop), the shared helper in `tests/test_canary_installed_release.py`, and `tests/test_canary_reuse.py::test_the_push_reader_counts_only_branches_named_in_a_plain_list`. The fourth review found that a manual run on `main` had no pinned release, that the test pinned the value itself instead of through the workflow, and that a wildcard `branches-ignore` still counted → Decision 5 (first parent on main's line, no pinned value) and the pattern cases of `tests/test_canary_reuse.py::test_the_push_reader_counts_only_branches_named_in_a_plain_list`. The fifth review found a branch pattern the reader missed (`main+`) and a main test that a current-tip form also passed → the test now requires a plain branch list with no pattern, and the main test adds a later merge. The sixth review found that a single text value passed as a list → the reader now requires a list of names. (4) Hard Eng fault: `main`'s `ship` has no hotfix route, so the hotfix used `develop`'s copy → None — release 658 brings the route to `main`; check it after the release.

Delivery target: Merge
Delivery: Pending — required remote proof.
