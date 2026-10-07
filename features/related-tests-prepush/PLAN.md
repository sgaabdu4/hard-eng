# Run only related JavaScript tests before push

Status: Complete

## Outcome + scope

Pre-push runs only the tests related to the pushed change for JavaScript packages whose test script runs Vitest or Jest, without the coverage threshold. CI keeps the full suite and the 70% coverage rule. Python and Dart test gates stay full before push: pytest and `flutter test` have no native related-test selection. Any setup that reuses a test gate's coverage in a later Fallow gate, a chained test script or an unknown runner also stays full.

Non-goals: related tests in CI, the Stop hook or `impact`; plugins that track test dependencies; changing configured gate commands.

## Repository context

Owners:
- `.hooks/hard-eng.py` `run_gate`, `prepare_reports`, `reject_test_filters`, `check`, CLI.
- `.hooks/reports.py`: report helpers; holds the new flag selection.
- `.hooks/ship_actions.py` `pre_push`: passes pre-push options the pushed runner supports.
- `.hooks/fallow_report.py` `owns_package_fallow`: a `pnpm run` Fallow gate may reuse earlier test coverage.
- Evidence: scratch projects with Vitest 5.0.3 and Jest 30.5.2. `pnpm run test:coverage --changed <base> --coverage.enabled=false --passWithNoTests` ran only the related Vitest file, wrote junit and no coverage, and exited 0 when nothing was related. `--changedSince=<base> --coverage=false --passWithNoTests` did the same for Jest.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked on 2026-10-07 for related tests before push with the coverage rule left to CI, and earlier approved merge when green.

## Acceptance + steps

- [x] A Vitest or Jest test gate gets the related-test flags only in related mode; chained scripts, other runners, non-JavaScript packages and coverage-reusing Fallow setups get none → `tests/test_reports.py`.
- [x] In related mode a passing gate with zero related tests passes, a failing test still fails, and coverage is not checked; the configured command still rejects these flags → runner tests.
- [x] Pre-push passes `--related-tests` only when the pushed runner supports it → `tests/test_ship_actions.py`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: main `ee124f85` passed `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` (1226 tests, 90.24% line coverage) and its push run; this branch starts from it unchanged.
Execution: One builder in this worktree.

## Risks + recovery

Tests outside the module graph (end-to-end, snapshot or config-driven tests) are not selected before push; CI runs them. A package whose coverage falls below 70% is caught in CI, not before push. Recovery is reverting this branch.

## ux_reference

N/A — check behaviour; no visual surface.

## Verification

Result: Passed
Evidence: `test_related_test_flags_follow_the_native_runner` covers Vitest, Jest, a chained script, another runner, a non-JavaScript report and a coverage-reusing Fallow gate. `test_related_tests_skip_coverage_but_keep_failures` runs a test gate through `run_gate`: related mode passes with zero tests and no coverage, a failing run still fails, and full mode still fails without tests or coverage. The pre-push test covers runners with both options, only the older one, and neither. Codex adversarial review (gpt-6-astra) round 1 approved with no findings.
Gate: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0.
E2E: N/A — the pre-push journey runs through the real hook in `test_pre_push_tests_committed_code`; the Vitest and Jest behaviour was proven in scratch projects with the real tools.

Delivery target: Merge
Delivery: Pending
