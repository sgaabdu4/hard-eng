# Read the Bun threshold where the tests run

Status: Complete

## Outcome + scope

Fix issue #291: a test script that changes folder with `bun --cwd=DIR test` keeps the full suite before push when that folder's `bunfig.toml` sets a coverage threshold. Non-goals: other related-test rules.

## Repository context

Owners: `related_test_flags` in `.hooks/reports.py`, which now takes the working folder from `package_script_invocation` in `.hooks/project_setup.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to address or close the daily audit issues.

The threshold stays; only the related-test selection reads the right folder.

## Acceptance + steps

- [x] A root script `bun --cwd=sub test --coverage` with a threshold in `sub/bunfig.toml` gets no related-test flags.
- [x] A threshold in the package folder still keeps the full suite.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: The new test case failed on main 51704766 and passes with the fix.
Execution: One builder; Codex adversarial review loop.

## Risks + recovery

None beyond the changed selection. Recovery: revert the owning commit.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` → exit 0; 18 checks passed, 91.30% line coverage. Codex adversarial review (GPT-6 Astra) round 1 approved; on the issue's scenario with real Bun 1.4.3, Hard Eng returned no related flags and the full suite passed.
E2E: N/A — the selection is covered by the scenario run above.

Delivery target: PR
Delivery: Pending — PR checks.
