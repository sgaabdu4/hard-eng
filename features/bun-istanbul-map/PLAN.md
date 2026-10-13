# Keep a same-run coverage map and match Fallow spans in one pass

Status: Draft

## Outcome + scope

Fix issue #293: without `fallow` on PATH, `write_istanbul` no longer deletes the `coverage-final.json` the test command just wrote, and with `fallow` it matches function spans to files in one pass. Non-goals: how the map is built or when Hard Eng writes it.

## Repository context

Owners: `write_istanbul` in `.hooks/fallow_report.py`, called from `line_coverage` in `.hooks/reports.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user approved filing #293 and asked for the fix in a PR after a Codex adversarial review loop.

A map older than the lcov is still removed as stale; only a map written after it is kept.

## Acceptance + steps

- [x] A map written after the lcov stays when `fallow` is missing.
- [x] A map from an earlier run is still removed when the listing fails.
- [ ] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: The new test failed on main c1e607dc (`FileNotFoundError` on the kept map) and passes with the fix.
Execution: One builder; Codex adversarial review loop.

## Risks + recovery

None beyond the changed removal rule. Recovery: revert the owning commit.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Pending
Evidence: `tests/test_reports.py` 183 passed. On a real Bun suite of 1,744 covered files with `fallow` on PATH, the conversion took 14.7 seconds; before the fix a gate sat in it for over 20 minutes.
E2E: N/A — the hook behaviour is covered by the scenario run above.

Delivery target: PR
Delivery: Pending — PR checks.
