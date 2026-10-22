# Record failed checks and name a repeat

Status: Complete

## Outcome + scope

When the Stop hook's check fails, it counts that failure in `.hard-eng/failures.json` and tells the agent when the same failure was seen before in this checkout. Non-goals: blocking beyond the existing failed-check block, sharing records across checkouts or projects, a hook for Codex tool failures (Codex has no such event).

## Repository context

Owner: `.hooks/agent_hooks.py` (`completion` failure path, new `repeat_note`); guidance in `.agents/skills/he-learn/SKILL.md`; tests in `tests/test_stop_checks.py`.
Same cause: N/A — new behavior. Before this, nothing in Hard Eng remembered a failure between Stop runs; the HE Learn line was the same on every failure.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-22 to record repeated failures, fast and with no slowdown, and to merge it.
Decided: key = hash of the failing lines (lines with "fail" or "error", numbers masked), so timings and line numbers do not hide a repeat and a different failing test is a new failure. Keep the latest 100 keys. Write only on a failed check.

## Acceptance + steps

- [x] A failure seen again in a new session is named as a repeat with its count; a different failing test is not → `tests/test_stop_checks.py::test_a_failure_seen_before_in_this_checkout_is_named_as_a_repeat`.
- [x] A failed check still blocks and is rerun on the next turn → `tests/test_stop_checks.py::test_failed_check_is_rerun_on_the_next_turn`.

## Baseline + execution

Result: Passed
Evidence: `uv run pytest -q tests/test_stop_checks.py` on `8d7e22f3` → 16 passed; the new test failed before `repeat_note` existed.
Execution: One builder, this session.

## Risks + recovery

- A failing line that holds a random temporary path changes the key, so that repeat is missed. Recovery: mask such paths if real reports show it.
- Cost: about 1.4 ms per failed Stop with a 4000-line failure log and a full 100-key file (2.3 KB). A passing Stop does no extra work.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` in the cloud container: 18 gates pass; tests 1892 passed, 6 failed. The same 6 fail on the base here (no Dart or Swift toolchain). CI runs them with the toolchains.
E2E: N/A — no user journey; the Stop hook runs this path in every agent session, and the test drives the real `completion` with a real check script.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
