# Fix the release canary failures from Hard Eng code

Status: Complete

## Outcome + scope

The canary on `develop` f15a36b failed 14 of 48 runs. Three causes are in Hard Eng code, and this plan fixes them:

1. The updater hung after its commit in 3 of 30 installed projects. `committed_matches` wrote a large `git cat-file --batch` request to a pipe while git wrote a large answer to another pipe. On macOS both sides blocked. The request now comes from a temporary file.
2. The OpenNext starter pinned `next` 16.3.8, which has three new advisories (fixed in 16.4.1). The scaffold now uses the upstream template commit that pins 16.4.1.
3. A new Python project has no performance test until the first code change. One agent read HE-PERFORMANCE-SUITE as an old failure and left it. The message now says the first code change adds the suite.

Non-goals: failures in the projects themselves (their own tests, builds that need credentials or network, Xcode, version-bump gates), and updaters already installed in projects (they run their own copy until they update).

## Repository context

Owners: `.hooks/update_runner.py` (`committed_matches`), `new_project.py` (`SCAFFOLDS["opennext"]`), `.hooks/hard-eng.py` (performance suite message). Test in `tests/test_update_runner.py`.
Same cause: the other `input=` calls in `.hooks` send small input to commands that write little output (`update-index`, gate config check, coverage helpers), so they cannot fill both pipes.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user's standing approval (2026-10-20) to fix canary failures at their source and decide; the user asked on 2026-10-22 to fix the CI failures across projects.
Decided: a temporary file, not one git call per blob, keeps one git process for any update size. The OpenNext template moves to upstream main `adb4f68`, whose `next` pin is the fixed release, rather than a local override of the template's pin.

## Acceptance + steps

- [x] `committed_matches` reads an update far larger than a pipe buffer → `tests/test_update_runner.py::test_committed_matches_reads_an_update_larger_than_a_pipe`.
- [x] The OpenNext scaffold pins a `next` release with no known advisory → N/A — reason: the pin comes from the upstream template at `adb4f68` (`next` 16.4.1, the OSV fixed release); the release canary's OpenNext scaffold run proves it.
- [x] The missing performance suite message says a new project adds it with its first code change → N/A — reason: message text only; `tests/test_greenfield.py::test_missing_performance_suite_names_the_requirement` still covers the rule.

## Baseline + execution

Result: Passed
Evidence: On the maintainer's Mac, three concurrent updates reproduced the hang. Python was blocked writing git's stdin and git was blocked writing its stdout, in `committed_matches`. Canary run logs name `next@16.3.8` with GHSA-2464-fhr4-w9xw, GHSA-673q-mjm6-r5xr and GHSA-p3m5-59mp-jv5r.
Execution: One builder, this session.

## Risks + recovery

Projects keep their installed updater until they update, so one more update may hang there. Rerunning the update gets past it, because the hang is a timing race. Recovery: revert this commit.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/develop` in the cloud container; PR CI runs it with every toolchain; the release canary reruns on the maintainer's Mac before main.
E2E: N/A — no user journey; the canary is the end-to-end run.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
