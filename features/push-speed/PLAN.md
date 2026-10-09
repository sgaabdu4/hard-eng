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

- [ ] Secret, vulnerability, security, workflow and shell scans start right after dependency setup, beside the other gates, not after the test suite → gate-order test.
- [ ] A gate with a recorded passing time stops at 3 times that time (at least 600 s, at most the budget) → time-limit test with a hung gate.
- [ ] An unchanged turn end during a build reuses the last passing check for the same stage → Stop hook test.
- [ ] `impact` reports the fast path when a merged PR or a verified Hard Eng update already proved the change, so CI skips the SDK install; installed workflows gain the token the impact step needs → impact and workflow migration tests.
- [ ] Pre-push skips mutation for a verified Hard Eng update → pre-push test.
- [ ] Parallel `uvx` gates no longer race on uv's interpreter cache → warm-up before parallel gates; reproduction test.
- [ ] Guidance: one full check at the end of a build, not before each push; no CI polling when auto-merge is on.
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
