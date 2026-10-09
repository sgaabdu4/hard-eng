# Faster checks without losing detection

Status: Ready

## Outcome + scope

Cut repeated and wasted check time across turn-end, manual, pre-push and CI checks. Detection stays the same. Non-goals: removing tests from the turn-end check, reusing a local pass at pre-push, moving mutation out of pre-push, update cadence, mac-ci limits and affected-test tools. Those wait for separate user decisions.

## Repository context

Owners: `.hooks/hard-eng.py` (`check` gate order, `run_gate` time limit, `impact`); `.hooks/agent_hooks.py` (`completion` memo); `.hooks/ship_actions.py` (pre-push mutation); `.hooks/ci_setup.py` + `.github/workflows/hard-eng.yml` (impact step); `.agents/skills/he-build`, `he-ship` guidance. Evidence (14 days, all sessions): turn-end checks 676 min; manual checks 763 min, with 57 of 79 pushes preceded by a passing manual check; CI polling 530 min; shared scans waited about 28 s behind the test suite; a stuck test ran 1,387 s; CI installs SDKs before the reuse test; a CI run failed when two `uvx` gates raced on uv's interpreter cache.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user approved group 1 of the push-speed proposal on 2026-10-09. Shipping follows the standing merge-when-green instruction.

## Acceptance + steps

- [x] Secret, vulnerability, security, workflow and shell scans start right after dependency setup, beside the other gates, not after the test suite → `test_scans_start_beside_a_serial_suite_listed_before_them` failed before (suite waited 10 s for a scan that never started), passes after.
- [x] A gate with a recorded passing time stops at 3 times that time (at least 600 s, at most the budget) → `test_a_hung_gate_stops_at_three_times_its_last_passing_time`.
- [x] An unchanged turn end during a build reuses the last passing check for the same stage → `test_unchanged_turn_during_a_build_reuses_the_pass_for_that_stage` failed before (second turn reran), passes after.
- [x] `impact` reports the fast path when a merged PR or a verified Hard Eng update already proved the change, so CI skips the SDK install; installed workflows gain the token the impact step needs → `test_impact_takes_the_fast_path_when_the_change_is_already_proven`, `test_old_impact_step_gains_the_token_its_reuse_lookup_needs`.
- [x] Pre-push mutation for a verified Hard Eng update → not changed: `mutation.targets` selects only changed package production lines, so a scaffold-only update has no targets and ends at once.
- [x] uv interpreter-cache race → not changed: seen once in CI, not reproduced locally, and no matching uv report found; a guessed fix without a failing test is not shipped. A CI rerun clears it.
- [x] Guidance: one full check at the end of a build, not before each push; no CI polling when auto-merge is on → `he-build`, `he-ship`, `checks.md`, `gates.md`.
- [ ] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Branch base `61546af8` passed main CI (Hard Eng: success) after PR #268.
Execution: Single builder; one commit per item.

## Risks + recovery

A gate limit from a fast earlier run can stop a slow but healthy run under heavy load. Recovery: the 600 s floor, and a pass records the new time. A reused turn-end pass can miss tool drift from `@latest`. Recovery: pre-push and CI run fresh.

## ux_reference

N/A — check runner, hook and guidance changes with no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: Required — a real check run shows the new gate order and per-gate limits; pending.

Delivery target: Merge
Delivery: Pending — PR CI and merge.
