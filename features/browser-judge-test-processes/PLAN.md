# Give the browser judge tests a fixed process list

Status: Complete

## Outcome + scope

No test in `tests/test_agent_browser.py` judges a run against the real process list of the machine, so a browser process that starts during the run cannot fail a test. Non-goals: the judge itself, the agent model checks that must read the real list.

## Sources + coverage

Sources: N/A — the request is a failed full suite on a branch that changed no code; no user source.

## Repository context

Owners: `tests/test_agent_browser.py` (the unit tests of the judge) and `tests/agent_browser.py::browser_processes` (the real list, for model checks).
Same cause: N/A — no earlier fix of this cause. Searched the tests for `browser_processes`, `leftover_failures` and `judge_browser`: only two tests of this file call the judge; one had the fixed list, one did not. `tests/agent_checks.py` passes the judge to model checks, which need the real list.
Single source: the fixed list has one owner now, the `judged_run` fixture, which both tests of the judge take. The two copies of its setup in the tests are merged into it.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — baseline repair. The failure blocks the Complete check of another change of the scheduled reference repository watch.

## Acceptance + steps

- [x] The image link test passes when a browser process starts on the machine during the run → `tests/test_agent_browser.py::test_judge_reads_images_the_answer_links`: 3 cases failed before the change and pass after it, while a stand-in process with the browser tool's name started six times during the run.
- [x] The judge still reports a leftover process from the list → `tests/test_agent_browser.py::test_browser_proof_judge_fails_each_missing_item` passes with its `leave_a_process` case.

## Baseline + execution

Result: Passed
Evidence: 2026-11-17, develop f0eba5ff: the `Hard Eng` and `Canary` workflows passed on the push. The failed baseline of this behavior: a full suite on a branch with no code change gave `3 failed, 5309 passed`; each failure began with "a browser process from the run is still running".
Execution: One builder, this session.

## Risks + recovery

N/A — one test file; a revert restores it.

## ux_reference

N/A — tests only; no visible UI.

## Verification

Result: Passed
Evidence: `tests/test_agent_browser.py` with the stand-in processes: 37 passed. Ruff, Pyrefly and Vulture report no finding. The Complete check passed on this branch.
Review: the Codex adversarial review approved 78f904ac with no findings. The independent review at 931fccce was clean; the fixture changed after it, so that review ran again.
Review declined: the map test still reads the real process list :: `test_a_map_run_adds_only_the_committed_feature_map` only prepares the app, which writes the list to the baseline file (`tests/agent_browser.py::prepare_browser_app`); that test never calls the judge and asserts nothing about processes, so no process list can change its result. The outcome line now says "judges".
E2E: N/A — no user journey changes.
Real service: N/A — the change calls no outside service.
Retro: (1) Escaped bug: a test on the base branch read the real process list and passed each gate, because no browser process started during those runs → no gate can catch it: a case for "this test reads the machine" would only repeat the fixture. Both tests of the judge get their run from the `judged_run` fixture, which sets the fixed list. (3) Ran too late: the dead-code gate refused an autouse fixture at the push, because no code names it → the focused checks of this plan's Evidence line now include the dead-code command; the fixture is taken by name. (2) The push refused the change without a plan, because it removes lines from a test file → None — the refusal named the step.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
