# Rollout findings: the scaffold replay, React Doctor reasons and the Bun download

Status: Complete

## Outcome + scope

Four faults found while rolling Hard Eng out to many projects, in one pull request. (1) The scaffold-only update check raised "setup refused the update: ... already differs" when the base commit held a project's own copy of a shipped skill file, even though the update tree held the release's exact copy; it now proves the update from its tree. The shipped video skills pin Playwright 1.64.1, the newest release at least 2 days old, so projects need not diverge. (2) A React Doctor project report that is incomplete now fails with each skipped check and the reason react-doctor recorded. (3) The generated workflow asks setup-bun for an exact Bun version, so a runner's installed or cached Bun serves it. (4) `MISE_FETCH_REMOTE_VERSIONS_CACHE` stays `0s` for installs. Non-goals: the refusal of a real update over an edited scaffold file, the version mise installs for the project's own Bun.

## Repository context

Owners: `release_installed`, `update_plan` and `setup_written` (`.hooks/update.py`, `.hooks/ci_setup.py`) and `scaffold_changes` (`setup.py`); `validate_react_project` (`.hooks/reports.py`) and `.hooks/react_report.py`; `.hooks/ci_jobs.py` and the setup-bun step of `.github/workflows/hard-eng.yml`.
Same cause: (1) `check_scaffold_update` proves an update at its tree, then `setup_written` replays setup on a worktree of the base commit to learn what the release writes to the workflow and hook files. Setup refuses to replace a scaffold file that differs from both releases, so an edited file in the base aborted the replay, and the `ValueError` escaped the check. Only the workflow and hook files are read from that replay, and the update tree is already proven file by file, so the replay plans with `--replace-scaffold`. `installed_update_paths` already treats a refusal as "not proven"; no other caller of `update_plan` replays a base. (2) The one fixed sentence in `validate_react_project` dropped the `skippedChecks` and `skippedCheckReasons` the report already holds; no other validator in `reports.py` lists skipped checks. (3) `isVersionMatch` in setup-bun (pinned revision `0c5077e`) never matches `latest`, `canary` or an empty version against an installed Bun, and `isCacheEnabled` is false for them; an exact version does both. Searched `bun-version` in this repository: the template and the Canary workflow; Canary runs only here on hosted runners and is left as it is.
(4) `tool_setup.py` installs with `0s` on purpose and `test_native_tools_install_before_reading_environment` asserts it: a cached list up to an hour old can make "latest" resolve to a version that is not the newest one at least 2 days old. I could not show the 2-day rule stays exact, so it is unchanged.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer asked on 2026-10-30 for these fixes as one pull request into `develop`, merged when green, then one more release to `main`. Decided: the replay accepts differing scaffold files only in `setup_written`; a real update still refuses; the Bun version comes from the project's exact `packageManager` pin, else the newest stable release at least 2 days old from the GitHub releases API (only when `GITHUB_ACTIONS` is true, five releases, ten second limit), else `latest`.

## Acceptance + steps

- [x] An update that restores the shipped skill files is proven although the base held edited copies → `tests/test_scaffold_replay.py::test_update_that_restores_edited_skill_files_is_proven`.
- [x] A real update still refuses an edited skill file → `tests/test_scaffold_replay.py::test_update_still_refuses_an_edited_skill_file`.
- [x] The shipped video skills pin Playwright 1.64.1 → N/A — package pins, read in the diff; the lockfiles were regenerated with `bun install --lockfile-only --minimum-release-age=172800`.
- [x] An incomplete React Doctor scan names each skipped check, its reason, the diagnostic count or the missing completion → `tests/test_react_report.py::test_incomplete_react_scan_says_why` and `tests/test_react_report.py::test_long_reason_is_cut`.
- [x] A complete scan still passes → `tests/test_react_report.py::test_complete_react_scan_passes`.
- [x] `bootstrap_bun` returns the pin, else the newest stable release at least 2 days old, else nothing → `tests/test_bootstrap_bun.py::test_a_pinned_bun_needs_no_lookup`, `tests/test_bootstrap_bun.py::test_the_newest_release_two_days_old_is_chosen` and `tests/test_bootstrap_bun.py::test_only_releases_under_two_days_old_leave_latest`.
- [x] A failed lookup or a run outside Actions prints no version → `tests/test_bootstrap_bun.py::test_a_failed_lookup_leaves_latest` and `tests/test_bootstrap_bun.py::test_outside_actions_the_version_is_left_to_setup_bun`.
- [x] `impact` prints the version, also on the already-proven path → `tests/test_bootstrap_bun.py::test_impact_prints_the_version`.
- [x] Generated workflows ask for the resolved version, older ones move over once, and a chosen version stays → `tests/test_bootstrap_bun.py::test_generated_workflows_ask_for_the_resolved_version`, `tests/test_bootstrap_bun.py::test_older_workflows_move_to_the_resolved_version_once` and `tests/test_bootstrap_bun.py::test_a_chosen_version_stays`.
- [x] The install cache setting is unchanged → N/A — no change; `tests/test_tool_execution.py::test_native_tools_install_before_reading_environment` keeps asserting `0s`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` e375003: the full check passed in the pull request that released it. The refusal reproduced against a rollout checkout with `update.check_scaffold_update`; `tests/test_scaffold_replay.py` fails with the same "already differs" error when `setup_written` does not pass `replace=True`.
Execution: One builder; one commit per fault, tests with each.

## Risks + recovery

The Bun lookup adds one request of about 300 KB to the impact step of a GitHub Actions run; it fails closed to `latest`. An exact Bun version makes a hosted runner restore it from the Actions cache after the first run. Recovery: revert the commit for the fault.

## ux_reference

N/A — hooks, workflow and package pins with no visual surface.

## Verification

Result: Passed
Evidence: `check --plan-stage Draft --base origin/develop` on the branch: all 20 gates passed, 2080 tests passed, line coverage 91.30%. An earlier run failed the `types` gate on untyped lambdas in the new Bun tests; the last commit before this record fixes it and the rerun passed.
E2E: N/A — the tests run the real update flow on a Git fixture, the real report validator and the generated workflow steps; a hosted run's cache restore is not provable here.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
