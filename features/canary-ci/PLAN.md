# Canary CI

Status: Complete

## Outcome + scope

The public new projects of the release canary (4 scaffolds, greenfield, brownfield) are set up and fully checked in hard-eng's own GitHub Actions, on Linux and macOS, for every PR and every develop push that changes an installed file. The Mac canary needs those jobs green on the revision before it starts, and it no longer runs the new projects' first full check itself. A broken scaffold now fails in minutes on a PR, not hours into a Mac run. Non-goals: installed projects and agent sessions stay on the Mac; no new secrets; no change to the agent task or the installed-project checks.

## Repository context

Owners: [release_canary.py](../../release_canary.py), [.github/workflows/canary.yml](../../.github/workflows/canary.yml), the release rule in [AGENTS.override.md](../../AGENTS.override.md); tests in [tests/test_release_canary.py](../../tests/test_release_canary.py).
Evidence: the Mac run of 2026-10-23 (4 h 02 min wall) logged about 9 h of step time. The 30 installed projects took about 8 h 54 min of it with 4 one-hour timeouts; the 6 new projects took 33 min to prepare (28 min of scaffold checks) and 2 h 34 min of agent sessions. Earlier canaries found new-project faults only on the Mac: the Python starter "No module named main" (macOS only) and broken Biome binaries.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-23 why the canary uses his Mac and not GitHub Actions. Standing approval to push, open PRs, decide and merge green PRs.
Decisions: Only public targets move. Installed projects stay on the Mac: hard-eng is public, so their logs cannot go in its Actions, and running them in each private repository's Actions would spend about 10 h or more of private Actions minutes per release, which a normal plan cannot carry and which the projects' own PR checks need. Agent sessions stay on the Mac: they need Abid's logins, and Codex never runs in the cloud. Public repositories get standard Linux and macOS runners free, so the new projects run on both; macOS catches Mac-only faults. The target list lives once in `NEW_TARGETS`: the workflow reads it, and the Mac reads the job names back through `CI_JOB`. A first job skips the matrix when only source files changed (same `needs_canary` rule as the Mac). On a develop push it compares with main, as the Mac does.

## Acceptance + steps

- [x] The workflow file is source-only and never needs a canary run → `tests/test_release_canary.py::test_the_public_canary_workflow_needs_no_canary_run`.
- [x] The Mac reads the newest CI result per new project and names each one without a pass → `tests/test_release_canary.py::test_ci_names_every_new_project_without_a_newest_passing_job`.
- [x] The workflow's job names match what the Mac reads → `tests/test_release_canary.py::test_the_workflow_job_names_are_the_ones_the_mac_canary_reads`.
- [x] A new project gets its full check in CI, not on the Mac → `tests/test_release_canary.py::test_a_new_project_gets_its_full_check_only_in_ci`.
- [x] `--ci` and `--target` pick only the named new projects → `tests/test_release_canary.py::test_ci_and_reruns_pick_only_the_named_new_projects`.
- [x] A revision whose new projects failed CI stops the Mac run before any agent → `tests/test_release_canary.py::test_new_projects_that_failed_ci_stop_the_run_before_any_agent`.

## Baseline + execution

Result: Passed
Evidence: `uv run pytest tests/test_release_canary.py`: 35 passed. Local `--ci` runs on Linux: greenfield, brownfield, vite and nextjs passed; opennext could not clone its template through the cloud proxy, so Actions is its proof.
Execution: One builder.

## Risks + recovery

A new project that fails in CI blocks the Mac canary until it is fixed or the job is rerun green. A runner fault can be retried from the Actions page; the newest try counts. Revert this PR to restore the Mac-only flow.

## ux_reference

N/A — maintainer CI with no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_release_canary.py`: 35 passed; local Linux `--ci` runs above. The `Canary` workflow on the PR proves all 12 jobs on Linux and macOS before merge.
E2E: N/A — the next Mac canary run is the full proof.

Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `Canary` green.
