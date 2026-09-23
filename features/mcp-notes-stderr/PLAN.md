# Keep MCP setup notes out of the update plan

Status: Complete

## Outcome + scope

Setup's four "MCP setup pending" notes (Appwrite without an endpoint or launcher, Sentry without a target) go to stderr, like the CI setup notes, so `setup.py --plan` stdout stays pure JSON and the updater can read it. Non-goals: changing note wording or MCP detection.

## Repository context

Owners: `.hooks/mcp_setup.py` (`appwrite_server`, `sentry_server`); `tests/test_mcp_setup.py`. Evidence: a sandbox update of a project importing Appwrite with no `APPWRITE_ENDPOINT` crashed in `update_plan` with `JSONDecodeError`, because the pending note preceded the plan JSON on stdout. Every such Appwrite or Sentry project hit this on update.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Found while sandbox-testing the requested stack-skill change; commit and delivery need user approval.

## Acceptance + steps

- [x] Pending notes are written to stderr → the four existing note assertions in `tests/test_mcp_setup.py` read stderr and pass.
- [x] Sandbox update of an Appwrite-importing project without an endpoint → completes with a local update commit instead of `JSONDecodeError`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Same baseline as `features/stack-skill-selection`: 16/17 gates PASS on unchanged `dcda0bb`; only the load-sensitive Dart parser test failed.
Execution: One builder.

## Risks + recovery

Callers reading these notes from stdout would miss them; the installer's own output and the agent hooks show stderr, as they already do for CI notes.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_mcp_setup.py` → 38 passed. Sandbox: before the fix the update crashed parsing the plan; after it, the update committed the Appwrite skill and link.
Gate: `python3 .hooks/hard-eng.py check --plan-stage Complete` at host load ~18 → exit 0, 17/17 PASS, 800 tests passed (including the Dart parser test that timed out under load).
E2E: N/A — installer output channel; proof is the tests and the sandbox update.

Delivery target: Merge
Delivery: Pending — needs user approval.
