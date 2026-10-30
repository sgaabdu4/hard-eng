# A Complete plan finds the Swift tests it names

Status: Complete

## Outcome + scope

The Complete plan check accepts `` `Tests/<Target>/<Name>Tests.swift::<function>` `` when that file declares `func <function>(`, as Swift Testing (`@Test func name()`) and XCTest (`func testName()`) do. Python keeps `def <name>(`; other files keep the quoted name. Non-goals: other languages that declare tests as plain functions, the test-file rules in `_is_test`, shell scripts named as tests.

## Repository context

Owners: `missing_tests` in `.hooks/plans.py`; its tests in `tests/test_plan_acceptance.py`.
Same cause: issue #440. A Swift project's Complete plan named real, passing Swift tests and the check reported every one as missing, because a non-Python file matched only a name in quotes or backticks. `_is_test` already counts `*Tests.swift` files as tests; only the name match was missing. A search of `.hooks` for the quoted-name pattern found no other caller.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved this fix on 2026-10-30 ("yes pls"): file the issue, fix the check, and deliver it through a pull request into `develop`.

## Acceptance + steps

- [x] A Complete plan that names a Swift Testing test or an XCTest test in a `*Tests.swift` file passes, and one that names a function the file does not declare fails → `tests/test_plan_acceptance.py::test_complete_plan_cannot_name_a_missing_test`.

## Baseline + execution

Result: Passed
Evidence: `origin/develop` 251f265: `tests/test_plan_acceptance.py` passed before the change. With the new cases and the old `missing_tests`, the Swift Testing and XCTest cases failed as missing.
Execution: One builder; the failing cases first, then the fix.

## Risks + recovery

A Swift file that names a non-test helper `func <name>(` also matches; the path must still be a test file, so the plan can only point at test code. Recovery: revert the commit.

## ux_reference

N/A — plan check change with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_plan_acceptance.py` passed (31 tests). `check` on the branch: all 20 gates passed, 2012 tests passed, line coverage 91.24%.
E2E: N/A — the check runs on written plan and test files in the tests; no user journey.

Delivery target: PR
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
