# Fix the remaining plan, CI and Stop defects seen in project sessions

Status: Ready

## Outcome + scope

Hard Eng stops blocking valid work in seven more situations:
- `Blockers: None. <note>` counts as resolved;
- a plan may give its slices their own `Status:` lines below the header;
- a Draft plan for later work may be pushed with a finished plan;
- the existing-CI reminder stops once a workflow runs the Hard Eng check;
- a stale install only warns at Stop when the session changed nothing in that checkout;
- zizmor's `self-repository` audit, whose only fix (`$/`) actionlint rejects, is off;
- a Flutter package whose tests are all browser tests no longer fails its VM run before the Chrome run.

Non-goals: project-authored gates that rewrite tracked files, and flutter_test browser tests (these must use package:test).

## Repository context

Owners:
- `.hooks/plans.py`: the exact `!= "None"` Blockers check, `field(content, "Status")` counting every line, and `validate_plans` requiring every applicable plan to reach the stage.
- `.hooks/ci_setup.py` `configure_ci`: prints the reminder whenever a non-maintenance workflow exists.
- `.hooks/agent_hooks.py` `completion`: runs `require_current` on the unchanged path.
- `.hooks/gitleaks_scan.py` `run_gate_command`: runs `zizmor@latest` with the project's config only.
- `.hooks/project_setup.py` `browser_test_coverage`: runs `flutter test` first under `set -e`, which exits 1 with "No tests were found" when every test is browser-only.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all the reported items.

## Acceptance + steps

- [x] `Blockers: None. <note>` and `None — <note>` pass; `None of …` and `None yet` still fail → `test_blockers_none_may_carry_a_note`.
- [x] A slice `Status:` below the header is allowed; a missing header Status still fails → `test_slices_may_carry_their_own_status`.
- [x] A Draft plan with code fails alone and passes beside a Complete plan → `test_draft_plan_for_later_work_rides_along_with_finished_work`.
- [x] The reminder prints for unintegrated CI and stops once a workflow runs the check → `test_integration_reminder_stops_once_existing_ci_runs_the_check`.
- [x] With no session changes, a newer verified revision warns without blocking; with changes it still blocks → `test_completion_checks_freshness_without_mutating_installation`.
- [x] The ci-security gate's zizmor config disables `self-repository` and keeps project rules → `test_ci_security_gate_turns_off_only_the_self_repository_audit`.
- [x] A package with only browser tests passes when `flutter test` finds none → `test_flutter_browser_library_coverage_comes_from_browser_tests`.

## Baseline + execution

Result: Passed
Evidence: Main `a939d50`. Each new or changed test failed on the code before its fix. Reproductions: zizmor 1.30.1 flags `uses: ./…` and actionlint 1.7.12 (latest) rejects `$/…`; `flutter test --machine --coverage` in a browser-only package exits 1 with "No tests were found".
Execution: One commit per defect.

## Risks + recovery

With `self-repository` off, zizmor no longer suggests `$/`; turn it back on once actionlint accepts `$/`. Recovery: revert the individual commit.

## ux_reference

N/A — hook and gate behaviour with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — real zizmor through the ci-security gate, and the generated browser gate on a real browser-only Flutter package with Chrome.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
