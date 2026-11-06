# Project security scans skip installed Hard Eng files

Status: Complete

## Outcome + scope

The Python, JavaScript and Dart templates scan the whole project with Semgrep, so a Python project also scans Hard Eng's installed `.hooks` with `p/python`. On slow macOS runners the taint analysis of one large installed file hit a fixpoint timeout, which fails the security gate (two canary failures on 2026-11-05 and 2026-11-06, both green on rerun). The templates now exclude `.agents` and `.hooks`, as basic mode already does. Hard Eng's own CI keeps scanning `.hooks` with `p/python`. Non-goals: changing existing projects' gate files, raising Semgrep time limits.

## Repository context

Owners: `.agents/skills/he/templates/hard-eng.{python,javascript,dart}.json` (security gate), `tests/test_basic_mode.py` (same rule as basic mode).
Same cause: `.hooks/basic_mode.py` already excludes both folders; Swift scans only its own folders.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-06 answered "you do all" to the open items, which included fixing this repeated scan timeout; merge after green checks.
Decision: exclude rather than raise limits; the installed files are Hard Eng's own code, scanned by Hard Eng's CI before release.

## Acceptance + steps

- [x] Every template security scan of the whole project excludes the installed `.agents` and `.hooks` → `tests/test_basic_mode.py::test_whole_project_security_scans_skip_installed_hard_eng`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI after PR 504 merged; the new test failed before the fix.
Execution: one session; failing test first.

## Risks + recovery

A project file under `.hooks` would no longer be scanned; that folder holds only installed Hard Eng files. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0, 2274 tests; 20 basic mode tests passed.
E2E: N/A — no user journey; the macOS canary runs the Python template on each PR.
Delivery target: PR
Delivery: Pending — PR into develop.
