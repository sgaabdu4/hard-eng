# Skip CI tool setup for docs-only changes and run tests in parallel

Status: Complete

## Outcome + scope

A docs-only pull request no longer restores the tool cache or installs uv, Python, Node and Dart before the check. A new `hard-eng.py impact --base` step, run with the runner's own Python, reports whether the check will run only the secret scan; if so, the workflow installs only uv and runs the same check. Every other change runs exactly as before. Existing installed workflows gain the same steps on update. This repository's `tests` gate runs in parallel with pytest-xdist, because the suite takes about 122 of the roughly 140 seconds CI spends on gates.

## Repository context

Owners: `.hooks/hard-eng.py` (CLI), `.github/workflows/hard-eng.yml` (the template copied into installed projects), `.hooks/ci_setup.py` `configure_ci` (updates existing generated workflows) and `hard-eng.gates.json` (this repository's gates). `impact` calls the check's own `changed_packages`, so the docs rule stays in `.hooks/plans.py` `is_documentation`; the workflow holds no copy of it. The CI log of run 35593136116 showed the fixed costs: tool-cache restore 13 s, runtime install about 8 s, gate tool preparation about 4 s.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to build the combined docs fast path and merge it, and to find other ways to avoid unnecessary or slow gate work. The job keeps no job-level condition: exactly one of the two check steps runs, so the required check always concludes (issue 121). If `impact` cannot run, for example on an older runner Python, the step prints `docs_only=false` and the full path runs, matching the existing rule that unknown impact checks everything. The migration only changes a workflow whose cache and check steps each appear once, without an existing `if:`; customised workflows are left alone. Parallel tests change only this repository's gate; generated gates for installed projects are unchanged.

## Acceptance + steps

- [x] `impact` reports `docs_only=true` only for a docs-only change in a project with packages → `test_impact_reports_docs_only_before_tools`.
- [x] Exactly one check step runs and the job has no condition → `test_generated_ci_timeout` asserts the complementary step conditions.
- [x] An installed workflow without the new steps gains them, and a second update changes nothing → `test_old_workflow_gains_docs_only_steps`.
- [x] The tests gate passes with `-n auto` and its coverage and JUnit reports are accepted.
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 2557d71, whose push CI run 35593136116 passed.
Execution: Single session on `feature/ci-docs-fast-path`.

## Risks + recovery

The docs-only path depends on `python3` on the runner and restores no tool cache, so uv and gitleaks download each time, which takes a few seconds. Tests that share state across processes would now fail under xdist; the whole suite passed in parallel. Recovery is reverting this branch.

## ux_reference

N/A — CI workflow and gate configuration only; no product appearance.

## Verification

Result: Passed
E2E: Passed — in a scratch worktree with a commit changing only README.md and a plan, the workflow's own commands ran locally: `impact` printed `docs_only=true`, then the docs-only step installed only uv, ran only `secrets-files` and passed in 8 seconds with an empty tool directory. The same `impact` under macOS's Python 3.9 failed and the step's fallback printed `docs_only=false`, which selects the full path. The GitHub run on a real docs-only pull request is not yet observed.
Evidence: Locally the suite took 170 seconds serially and 47.5 seconds with `-n auto`, all 783 tests passing in parallel. The new and updated tests pass; the full check result is recorded in the delivery line below.

Delivery target: Merge
Delivery: Pending — `hard-eng.py check --base origin/main` exit 0 in 71 seconds: all 17 checks, 787 tests and 4 performance checks passed; before this change the same check took about four minutes. A first run failed the types gate on an unannotated list in the new impact test; it was annotated and committed before the passing run. PR CI, merge, merged-main CI and a real docs-only pull request remain unverified.
