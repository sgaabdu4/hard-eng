# Acceptance lines may name requirement IDs

Status: Complete

## Outcome + scope

An acceptance checkbox may name a registry requirement ID (HE- or REQ-) instead of a `path::test name`. At Complete the ID must be in the registry, not retired, and covered by at least one test. The skip check after the test gates also covers the ID's tests. Non-goals: new ID formats, registry changes, new files.

## Repository context

Owners: `.hooks/plans.py` (`acceptance_tests`, `plan_stage`, `plan_tests`), which reuses the registry's `REQUIREMENT_ID`, `registry_entries` and `requirement_tests`; he-plan template and SKILL.md proof rule.
Same cause: N/A — new rule, not a fault fix.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked for acceptance lines to reuse the registry IDs and to let the agent decide open choices. A guidance-only ID has no tests, so it fails as an acceptance proof; such lines use `N/A — reason`.

## Acceptance + steps

- [x] A line naming only a requirement ID passes Ready and Complete format checks → `tests/test_plan_acceptance.py::test_each_acceptance_line_names_its_test_or_why_none_applies`.
- [x] At Complete a tested ID passes; an untested, guidance, retired or unknown ID fails → `tests/test_plan_acceptance.py::test_complete_plan_resolves_a_requirement_id_to_its_tests`.
- [x] `check` fails when a test that covers a named ID was skipped → `tests/test_plan_acceptance.py::test_check_fails_when_an_acceptance_test_was_skipped`.
- [x] Template and he-plan rule name the ID option → N/A — instruction text, checked in diff review.

## Baseline + execution

Result: Passed
Evidence: Built on the registry branch 781a8e2 (develop e62b742 plus the registry); its suite had the same 8 Dart, Swift and pre-push snapshot failures as develop, from tools this container lacks.
Execution: Single session, stacked on the registry PR.

## Risks + recovery

If the registry PR changes its helper names, this change breaks at import time and its tests fail. Recovery: revert the commit.

## ux_reference

N/A — developer tooling, no visible interface.

## Verification

Result: Passed
Evidence: `pytest -n auto` → 1780 passed, 8 failed; the same 8 fail on develop. Ruff format/lint/complexity/annotations, pyrefly, vulture and jscpd pass. `check` passed plan and record validation, then could not install gitleaks, osv-scanner, shellcheck and actionlint here; CI ran those gates. Independent review not done: `challenge` needs the Codex CLI, which this container lacks.
E2E: Passed — `test_check_fails_when_an_acceptance_test_was_skipped[id-True]` runs the real `check` with a plan naming an ID, a real registry, a covering test and a JUnit report showing it skipped; only gate loading is faked.

Delivery target: Merge
Delivery: Pending — PR into develop with the hard-eng CI check green; CI runs gitleaks, osv-scanner, shellcheck and actionlint.
