# Fix Bun migration gaps found on real projects

Status: Complete

## Outcome + scope

Fix issues #283 and #284 and the gaps found by running the Bun release on real project workflows and a converted project. Non-goals: project-owned workflow steps, project scripts and tests.

## Repository context

Owners: `migrate_bun`, `impact_tools` and `workflow_tools` in `.hooks/ci_setup.py`; `package_directory` and the migration message in `.hooks/project_setup.py`; `_dependency_coverage_commands` in `.hooks/fallow_report.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix the raised issues, dig for further issues, run the Codex adversarial review loop with GPT-6 Astra and open a PR.

Bun prints help for `bun --cwd DIR run`, so Hard Eng writes `--cwd=DIR` and rejects the spaced form before `run`. JavaScript packages keep `node@latest` in CI, because their own tools (Vitest with jsdom) fail on Bun. The migration message names pnpm settings that `bun install` does not carry.

## Acceptance + steps

- [x] A pnpm setup step with `if:` before or after `uses:` migrates to one Bun step.
- [x] The Fallow dependency chain uses `bun --cwd=DIR run`; the spaced form before `run` is rejected; `bun run --cwd DIR` is read.
- [x] JavaScript packages get `node@latest` in CI tool lists.
- [x] The migration message names trustedDependencies, minimumReleaseAge and bunfig.toml.
- [x] A pnpm tool that ends a tool list line is removed.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: Each new test failed on main 2864f6a9. Four real project workflows were migrated as copies; one project was converted to Bun in a scratch clone and checked.
Execution: One builder; Codex adversarial review loop.

## Risks + recovery

Project-owned pnpm lines in custom workflow steps stay for the project's agent. Recovery: revert the owning commit.

## ux_reference

N/A — hook and CI behaviour with no visual surface.

## Verification

Result: Passed
Evidence: Focused suites pass; full gate result recorded at delivery.
E2E: Passed — scratch clone of a real Next.js project converted to Bun, installed with this branch and checked; Hard Eng gates passed, remaining failures were the project's own pnpm tests and two published advisories.

Delivery target: PR
Delivery: Pending — PR checks.
