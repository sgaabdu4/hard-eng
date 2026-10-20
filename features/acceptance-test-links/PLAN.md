# Acceptance lines name existing, non-skipped tests

Status: Complete

## Outcome + scope

Plan validation requires each checkbox in `## Acceptance + steps` of a changed Ready or Complete plan to name its test as `` `path::test name` ``, or to say `N/A — reason` when no test can prove the line, such as rule text. At Complete each named test must exist in a test file. After the test gates run, `check` fails when a named test was reported skipped. Non-goals: requirement IDs (owned by the requirement registry work, which will resolve an ID to tests through its own helper), new files or gates.

## Repository context

Owners: `.hooks/plans.py` (`validate_plan`, `plan_stage`, `validate_plans`), `.hooks/reports.py` (test report parsing beside `completed_tests`), `.hooks/hard-eng.py` `check`, the he-plan template and SKILL.md proof rule. Unchanged Complete plans keep their original rules, as for the E2E and UX fields.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Requested in the Hard Eng project; push and PR wait for Abid's approval. `N/A — reason` keeps rule-text lines valid without padding tests, which AGENTS.md forbids.

## Acceptance + steps

- [x] An acceptance line without a test reference or an N/A — reason fails Ready and Complete → `tests/test_plan_acceptance.py::test_each_acceptance_line_names_its_test_or_why_none_applies`.
- [x] A Complete plan naming a missing test, a non-test file or a path outside the repository fails; pytest ids, class tests and JS name strings resolve → `tests/test_plan_acceptance.py::test_complete_plan_cannot_name_a_missing_test`.
- [x] `check` fails when a named test is reported skipped, and passes when it ran → `tests/test_plan_acceptance.py::test_check_fails_when_an_acceptance_test_was_skipped`.
- [x] JUnit and Dart reports name their skipped tests → `tests/test_reports.py::test_report_names_its_skipped_tests`.
- [x] An unchanged Complete plan without references stays valid until edited → `tests/test_plans.py::test_unchanged_complete_plan_predates_newer_rules[acceptance]`.
- [x] Template and he-plan rule describe the reference format → N/A — instruction text, checked in diff review.

## Baseline + execution

Result: Passed
Evidence: `pytest -n auto` on fbbb031 with submodules initialized → 9 failed, all from tools this container lacks (Dart, Swift, release canary timing); the same 9 are the comparison set below.
Execution: Single session. Tests written beside each rule; the skip test was confirmed to fail with the skip check disabled.

## Risks + recovery

Active Ready plans in installed projects must add references or `N/A — reason` on their next check. Recovery: revert the commit.

## ux_reference

N/A — developer tooling, no visible interface.

## Verification

Result: Passed
Evidence: `pytest -n auto` → 1745 passed, 9 failed, all 9 also failing on fbbb031. Ruff format/lint/complexity/annotations, pyrefly, vulture and jscpd pass; plan, comment, suppression and ADR validation pass against origin/main. The full `check` could not provision gitleaks, osv-scanner, shellcheck and actionlint here (GitHub API 403), so CI runs those gates.
E2E: Passed — `test_check_fails_when_an_acceptance_test_was_skipped` runs the real `check` with a real plan, a tests gate writing a JUnit report and the real report parser; only gate loading is faked.
