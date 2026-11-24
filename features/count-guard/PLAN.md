# Look review: a No clutter Fail with removals on some screens stands

Status: Ready

## Outcome + scope

The `look` review refuses a No clutter Fail line only when every removed count in the line is 0. A line such as `(kept 15 / 19 / 74, removed 0 / 0 / 5)` has one count for each of three screens and removed 5 items, so it stands. Non-goals: any other look rule; the count form in the prompt.

## Sources + coverage

Sources: N/A — the request is the only source: a reviewer line that `judge` refused with "its own count says 0 removed" although it removed 5 items on one screen.

## Repository context

Owners: `.hooks/look.py` (`nothing_removed`, used by `rule_refusal`) owns the check of removed counts.
Same cause: the old pattern matched `removed 0` or `0 removed` anywhere in the line, so the first zero of a list of counts refused the line. Searched `.hooks`, `setup.py`, `release_canary.py`, `tests` and the plan checks in `plans.py` for a matcher of removed counts. No other copy exists: the text in `PROMPT` and `ux.md` states the rule and matches nothing, and `plans.py` counts only the Pass units of other rules in `uncounted`.
Single source: `.hooks/look.py::nothing_removed` owns the reading of removed counts. No parser of removed counts existed: `split_rule_line` reads the rule, verdict and text only, and `COUNT_NOTE` only moves the note.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] A Fail line with removed counts `0 / 0 / 5`, in the note before or after the text, stands as a finding → `tests/test_look.py::test_a_fail_line_that_cannot_stand_is_refused`
- [x] A Fail line with removed counts `0 / 3` stands as a finding (a zero for one screen only) → `tests/test_look.py::test_a_fail_line_that_cannot_stand_is_refused`
- [x] A Fail line with `removed 0`, `removed: 0`, `0 removed`, `kept 34 removed 0`, `kept 34, 0 removed`, `removed 0, 3 badges repeat` or `removed 0 / 0 / 0` stays refused, and each row has a `Fix:` so only the count guard can refuse it → `tests/test_look.py::test_a_fail_line_that_cannot_stand_is_refused`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` the three rows with a non-zero count fail and the other rows pass.
Execution: One pattern and one function in `.hooks/look.py`, the test rows.

## Risks + recovery

A line with a count form that the pattern does not read, such as words instead of digits or a comma list (`removed 0, 0, 5`), is not read as a list and a lone first 0 can refuse it. Recovery: revert the commit.
Review declined: A Fail line with comma-separated removed counts per screen, such as `removed 0, 0, 5`, is still refused because only the first 0 is read :: The comma already separates `kept` from `removed` and a clause such as `removed 0, 3 badges repeat` follows it, so a comma list cannot be told from those; a first attempt to read comma lists made `kept 34, 0 removed` stand. The line that was reported used `/` between screens, which is read.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — the change is a check of reviewer text, proved by the tests above.
Real service: N/A — no service is called.
Retro: Pending.

Delivery target: PR
Delivery: Pending — required remote proof.
