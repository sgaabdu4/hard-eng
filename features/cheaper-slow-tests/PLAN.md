# Make the slowest tests cheaper

Status: Complete

## Outcome + scope

The test suite does less repeated setup work. The `release` fixture, which builds a source repository and an installed project, is built once per test process and copied for each test. The shared `init` helper writes the fixture Git identity into `.git/config` instead of starting two `git config` processes per repository. The updater's `fetch_sources` skips `git submodule update` for a fetched tree without `.gitmodules`, matching the guard its candidate step already has. No test is removed, skipped or weakened, and no new file other than this plan.

## Repository context

Owners: `tests/conftest.py` (`release`, `init`) and `.hooks/update.py` `fetch_sources`. Measured on main at dff68c2: `tests/test_updates.py` took 80 of about 184 seconds of test time, and fixture setup another 42. A subprocess trace of that file showed the fixture's own work (`git add .`, `setup.py`, commits) at about 25 seconds across 28 builds, and `git submodule update --init` at 7 seconds across 48 calls on trees with no submodules. The built fixture contains no absolute paths (checked with a recursive search and `git config --local --list`), so a copy behaves like a fresh build.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to make the slowest tests cheaper after the CI timing work in PR 133. The two Dart coverage tests stay as they are: each of their seven classifier calls proves a different outcome and costs about 4.2 seconds of real Dart analyzer start-up. The `delivered_worktree` fixture stays per-test because its worktree and remote hold absolute paths. `repository_files` is not cached, because the check's file listing must stay current. `uv run --project` in the updater is the behavior under test. After PR 134 passed CI, the user approved merging it.

## Acceptance + steps

- [x] Every existing test passes unchanged, serially and in parallel → 787 passed both ways.
- [x] Tests using `release` still get an isolated source and target → the 102 tests in its four user files pass, including those that commit to and mutate both repositories.
- [x] The pinned skill submodule is still fetched for each revision → existing `test_update_fetches_each_revisions_pinned_skill_submodule` passes with the new guard.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at dff68c2, whose push CI run 35610723782 passed.
Execution: Single session on `feature/cheaper-slow-tests`.

## Risks + recovery

A test that mutated the shared template instead of its copy would leak state to later tests in the same process; the template lives outside each test's `tmp_path` and only `release` reads it. Recovery is reverting this branch.

## ux_reference

N/A — test fixtures and one updater subprocess guard; no product appearance.

## Verification

Result: Passed
E2E: N/A — no runtime journey changes; the updater guard is exercised by the existing real-Git update tests.
Evidence: Alternating runs with four workers, twice each: main 71.8 and 73.7 seconds, this branch 65.3 and 65.2 seconds, 787 passed every time. In isolation `tests/test_updates.py` went from 82 to 62 seconds. The full check result is recorded in the delivery line below.

Delivery target: Merge
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0: all 17 checks, 787 tests and 4 performance checks passed. PR 134 CI passed at the pushed revision; merge, merged-main CI and cleanup remain unverified.
