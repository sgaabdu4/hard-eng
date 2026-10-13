# Fix the Bun follow-up issues

Status: Complete

## Outcome + scope

Fix issues #286, #287, #288 and #289 raised against the Bun release. Non-goals: project-owned migrations, Fallow upstream changes.

## Repository context

Owners: `provision_batch` and `export_tool_paths` in `.hooks/tool_setup.py`; `configure_javascript` in `setup.py` and `workflow_tools`/`bun_specification` in `.hooks/ci_setup.py`; `write_istanbul` in `.hooks/fallow_report.py`, called from `line_coverage` in `.hooks/reports.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to investigate and fix the raised issues, run the Codex adversarial review loop with GPT-6 Astra and open a PR.

npm tools carry the mise option `bun_args="--minimum-release-age=0"`, the only form Bun reads over a user bunfig. Tool PATH exports skip `node_modules/.bin`. Setup and updates land while a Bun migration is pending, printing the instruction, so the migration is committed on the update branch under the new gates; gate runs still reject pnpm. After a full run whose lcov has no function records (Bun), Hard Eng writes `coverage/coverage-final.json` with function spans from Fallow's own listing, matching what Vitest and Jest write.

## Acceptance + steps

- [x] With a user bunfig minimum age of 7 days, a 3-day-old tool installs from an empty cache.
- [x] Exported tool PATH holds each tool's `bin` but not its `node_modules/.bin`; React Doctor, Fallow and TypeScript still pass.
- [x] Setup on a pnpm project lands with "Bun migration pending"; the check still rejects pnpm; after a migration commit on top the Hard Eng gates run.
- [x] Fallow matches Bun coverage through the generated map and scores CRAP from it instead of estimating.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: Each regression test failed on main 125227e9; each issue was reproduced with real Bun, mise and Fallow before its fix.
Execution: One builder; Codex adversarial review loop.

## Risks + recovery

Line-level Bun coverage marks a one-line function covered when its line runs. Recovery: revert the owning commit.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Passed
Evidence: Focused suites, lint and pyrefly pass. Real runs: tools installed from an empty cache under a 7-day user bunfig; a website clone passed React Doctor, Fallow and types with tool dependencies off PATH; a pnpm clone landed setup with the migration pending and ran the Hard Eng gates after a migration commit; real Fallow matched the generated map and scored CRAP 7.1 instead of an estimated 56, including on a clean checkout with FALLOW_COVERAGE configured. Codex round 1 finding fixed.
E2E: Passed — real fixture and scratch project clone runs recorded per issue.

Delivery target: PR
Delivery: Pending — PR checks.
