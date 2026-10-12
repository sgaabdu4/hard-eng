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

Bun prints help for `bun --cwd DIR run`, so Hard Eng writes `--cwd=DIR` and rejects the spaced form before `run`. The user asked for Bun as the runtime too: during checks `node` always resolves to Bun, CI provides no Node, and projects move to `bun test` (Vitest with jsdom fails on Bun). The migration message names pnpm settings that `bun install` does not carry and the move to `bun test`.

## Acceptance + steps

- [x] A pnpm setup step with `if:` before or after `uses:` migrates to one Bun step.
- [x] The Fallow dependency chain uses `bun --cwd=DIR run`; the spaced form before `run` is rejected; `bun run --cwd DIR` is read.
- [x] `node` resolves to Bun during checks even when Node is installed; CI tool lists carry no Node.
- [x] Lighthouse CI, Stryker, TypeScript, Fallow, jscpd and React Doctor run on Bun.
- [x] The migration message names trustedDependencies, minimumReleaseAge, bunfig.toml and `bun test`.
- [x] A pnpm tool that ends a tool list line is removed.
- [x] A missing Bun stops tool setup with how to install it; setup reports CI workflows that run Hard Eng without Bun.
- [x] An empty OSV result in a directory without package.json fails as a normal OSV failure.
- [x] All ten local Hard Eng projects, cloned and converted to Bun, install this branch and run the full check without a Hard Eng error.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: Each new test failed on main 2864f6a9. Ten local projects were cloned, converted to Bun and checked: three passed every gate; the other failures were project-owned (`node --test`, Jest, Vitest with jsdom, project version rules, published advisories, pnpm-style overrides) apart from the OSV crash and missing-Bun failure fixed here.
Execution: One builder; Codex adversarial review loop.

## Risks + recovery

Project-owned pnpm lines in custom workflow steps stay for the project's agent. Recovery: revert the owning commit.

## ux_reference

N/A — hook and CI behaviour with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main` → exit 0; 18 checks passed, 91.34% line coverage. Codex adversarial review (GPT-6 Astra) round 3 approved; the round 2 finding (spaced `--cwd` before a file or `-e`) is fixed. Startup medians on this Mac: `bun run` 37 ms vs `pnpm run` 63 ms; `bun -e` 17 ms vs `node -e` 172 ms. A Bun fixture passed all 13 gates with Node installed while `node` resolved to Bun; Lighthouse CI collected a report on Bun.
E2E: Passed — scratch clone of a real Next.js project converted to Bun, installed with this branch and checked; Hard Eng gates passed, remaining failures were the project's own pnpm tests and two published advisories.

Delivery target: PR
Delivery: Pending — PR checks.
