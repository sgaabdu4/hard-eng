# Canary speed

Status: Complete

## Outcome + scope

The release canary keeps every check, but finishes sooner and shows where its time goes. Installed projects run their update PR check and full check but no agent sessions; the scaffolds, greenfield and brownfield projects still get one Claude and one Codex session each. Claude and Codex work on the same target at the same time, on their own copies. New projects start first. On macOS the agent copy is an APFS clone. Each step logs its start time and duration, and the run ends with a time summary per stage. Non-goals: no dropped targets or checks; no change to the agent task, the 1-hour agent limit or the default of 3 jobs; no cloud runner.

## Repository context

Owners: [release_canary.py](../../release_canary.py); its tests in [tests/test_release_canary.py](../../tests/test_release_canary.py); the release rule in [AGENTS.override.md](../../AGENTS.override.md).
Evidence: the 2026-10-21 full run took 8 h 42 min for 108 runs: 36 targets, each prepared and then given one Claude and one Codex session. Three workers each ran a target from start to end, so the two agent sessions of a target ran one after the other. The 6 new-project targets, which always run both agents and often reach the 1-hour limit, were last in the list and formed the tail. Logs had no times. In the next run, an installed project that passed took about 36 minutes from start to end.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-21 why the canary takes 9 hours and to make it faster without dropped coverage. Standing approval to push, open PRs and decide.
Decisions: Agent sessions only on new projects (Abid approved, 2026-10-21): the deterministic checks on every installed project catch release regressions, and the 6 new projects (4 scaffolds, greenfield, brownfield) show that both agents follow the workflow. This removes up to 60 of 72 agent sessions, most of the run time; a full run is now 48 runs. The unit of work is one preparation or one agent session, not one target. Agent units of a prepared target go before targets that wait, so at most a few targets are on disk at once. The job limit stays 3 units, so the Mac carries the same number of concurrent sessions and test runs as before; raise `--jobs` only after the time summary shows room. Not a cloud split: Codex is not allowed in the cloud and installed projects are private, so only 6 of 108 runs could move. The earlier speed study already rejected parallel scanner pins; this change runs no new tools at the same time.

## Acceptance + steps

- [x] Installed projects get no agent sessions; every new-project kind gets both → `tests/test_release_canary.py::test_only_new_projects_get_agent_sessions`.
- [x] Each step's log line shows when it started and how long it took → `tests/test_release_canary.py::test_a_step_log_shows_when_each_command_started_and_how_long_it_took`.
- [x] A prepared target's agent units run before the next target is prepared → `tests/test_release_canary.py::test_agent_units_of_a_prepared_target_run_before_the_next_target_is_prepared`.
- [x] Claude and Codex on one target run at the same time → `tests/test_release_canary.py::test_agents_of_one_target_run_at_the_same_time`.
- [x] A canary fault still stops the run → `tests/test_release_canary.py::test_a_unit_that_crashes_stops_the_run`.
- [x] New projects start before installed ones → `tests/test_release_canary.py::test_new_projects_start_before_installed_ones`.
- [x] Each agent writes its own log, and the target is deleted only after its last agent ends and every run passed → `tests/test_release_canary.py::test_a_target_is_kept_until_its_last_agent_ends_and_only_when_one_failed`.
- [x] A clone keeps project lock files and drops Git's own lock files; a failed clone falls back to the full copy → `tests/test_release_canary.py::test_a_clone_drops_git_locks_and_keeps_project_lock_files`, `tests/test_release_canary.py::test_a_failed_clone_falls_back_to_a_full_copy_without_git_locks`.
- [x] The run ends with runs, total and longest time per stage → `tests/test_release_canary.py::test_the_time_summary_names_each_stage_with_its_runs_total_and_longest`.

## Baseline + execution

Result: Passed
Evidence: `develop` cd2f13f: `uv run pytest tests/test_release_canary.py` passed.
Execution: One builder; scheduler, copies and times in `release_canary.py`, each with its test.

## Risks + recovery

Claude and Codex now share a target's time window, so their project test runs can overlap where they used to follow each other; the total number of concurrent units is unchanged. The next Mac run's time summary shows the effect. Revert this PR to restore the old one-target-per-worker order.

## ux_reference

N/A — a maintainer script with no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_release_canary.py`: 28 passed. Full check: see PR. The APFS clone path runs only on macOS; the tests run it with a stand-in `cp`, and the next Mac canary run is the real proof.
E2E: N/A — the next full canary run on the Mac exercises the whole flow.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
