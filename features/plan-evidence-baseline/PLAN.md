# Skip package checks for plan evidence images

Status: Complete

## Outcome + scope

A plan-stage baseline on a branch that only adds a feature plan and its evidence captures (screenshots, videos, PDFs in that plan's folder) runs no package checks when the branch point passed CI. Captures elsewhere still select their owning package. Fixes issue 260.

Non-goals: changing the secret scan, `--base` behaviour, CI or pre-push.

## Repository context

Owners:
- `.hooks/plans.py` `planning_only`: already treats captures in a feature plan's folder as planning files for the Stop hook and the plan stage.
- `.hooks/gate_config.py` `packages_for`: skips plans and Markdown but not captures, so a PNG under `features/<slug>/evidence/` selected the root package and its dependents.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked on 2026-10-09 to fix all open issues, review with Codex adversarial review in a loop, and merge when done.

## Acceptance + steps

- [x] Plan plus evidence capture in a feature folder → only the secret scan runs → `test_docs_only_change_runs_only_the_secret_scan`.
- [x] Plan-stage check with a passed branch point and only a feature plan plus capture → the failing package check does not run → `test_plan_stage_check_skips_packages_unchanged_since_a_passed_branch_point`.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: both tests failed on the unfixed code: the capture selected a package and the package check ran.
Execution: Single session on branch `plan-evidence-baseline`.

## Risks + recovery

A package that reads images from a feature plan folder without declaring it as an input would be skipped. Declared inputs still select their consumers. Recovery is reverting this branch.

## ux_reference

N/A — check behaviour; no visual surface.

## Verification

Result: Passed
Evidence: Both tests above fail without the `packages_for` change (the capture selected a package; the failing package check ran) and pass with it. Codex adversarial review (gpt-6-astra) round 1 found no code issues, only this section still Pending.
Gate: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0 (1459 tests, 91.08% line coverage).
E2E: N/A — command-line check behaviour proven through the runner in tests.

Delivery target: Merge
Delivery: Pending
