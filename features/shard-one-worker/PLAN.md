# The worker-count shard test starts one worker

Status: Complete

## Outcome + scope

The inner run of the worker-count shard test starts one worker, not two, and the test proves the same outcome. Non-goals: a change of shipped code; a change of another test.

## Sources + coverage

Sources: N/A — the request is the only source: the owner said in chat on 2026-11-14 to ship the one-line change that an old builder branch held.
Deliverables: None

## Repository context

Owners: `tests/test_shards.py::test_a_worker_count_in_the_pytest_settings_leaves_the_shard_files_exact`; the code that it protects is `.hooks/shards.py::collected`.
Same cause: N/A — no fault is repaired; the change removes one process start from a test.
Single source: N/A — the worker count is a value of this one test; a search of `tests/test_shards.py` for `addopts = "-n` found no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner approved this change in chat on 2026-11-14 ("Yes, ship it") and gave full authority for merge and release.
Decisions:

1. One worker keeps the proof. The test protects the file list of a shard when the pytest settings hold a worker count. With a count of 1 the inner run still goes through the worker path of the pytest worker plugin.
2. The change is the commit of the old builder branch, applied to the current base with no edit.
3. The fixture gives each inner run its own pytest temp root, and the test puts the folders of other runs under `TMPDIR`. The test proves that the inner run does not delete those folders. With the own temp root removed from the fixture for one trial, the test failed on that assertion with one worker and with two. So one worker keeps this proof too. The test does not prove what the inner run does inside its own temp root, and it never did. This plan accepts that limit and does not change the fixture or the assertion. An inner temp root that points at the shared folder would let pytest delete the old folders there. That is the normal behavior of pytest and the fault that the own temp root prevents.

## Acceptance + steps

- [x] With a worker count of 1 in the pytest settings, the shard runs only its own test file, the file list of the shard holds only that file, and the folders of other pytest runs under `TMPDIR` stay, because the inner run has its own temp root → `tests/test_shards.py::test_a_worker_count_in_the_pytest_settings_leaves_the_shard_files_exact`
- [x] The inner run still uses the worker path → N/A — no assertion reads the inner output; one run with the output shown printed "created: 1/1 worker"

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at 640fd343, and the Hard Eng check run of that commit passed.
Execution: one builder; the test with both values, then the whole shard test file and the static gates.

## Risks + recovery

- A fault that shows only with two or more workers is no longer in reach of this test. The test never claimed that: its name and its assertions are about a worker count in the settings.
- Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes; the change is one line of one test.

## Verification

Result: Passed
Evidence: the test passed with a worker count of 2 before the change and with a count of 1 after it. The inner run printed "created: 1/1 worker". One run each took 0.54 s with two workers and 0.45 s with one. With the own temp root removed from the fixture for one trial, the test failed with one worker and with two on the assertion that the folder of another run stays; the fixture was then put back. The whole shard test file passed with 101 tests, and the static gates passed.
E2E: N/A — no user journey changes; the test runs a real inner pytest run.
Retro: (1) The push check and the Stop check refused the change because it had no plan → None — the existing size rule worked as designed; a change that removes a line of a test file is big, and this plan is the answer.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
