# Run Stryker on TypeScript packages that have a tsconfig.json

Status: Draft

## Outcome + scope

Pre-push and `mutation` report Stryker mutants for TypeScript packages with a `tsconfig.json`. A tool failure now shows its error line, not just the last Node stack frames. Fixes [#226](https://github.com/sgaabdu4/hard-eng/issues/226).

Non-goals: provisioning `typescript` next to Stryker, and changing the Python or Dart adapters.

## Repository context

Owners: `.hooks/mutation.py` `javascript` builds the Stryker config. Stryker 10's sandbox preprocessor rewrites `tsconfig.json` with `import('typescript')`, which the isolated mise install cannot resolve. The same preprocessor returns early when `inPlace` is set. Mutation already runs only in a disposable checkout (`--in-place`: "must be disposable"; `pre_push` and `mutate` both remove the snapshot afterwards), and mutation_test already edits source in place. `failed` kept the last 15 lines, which for Node are stack frames.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open issues, test, run adversarial review and open a PR.

## Acceptance + steps

- [ ] Stryker runs in place, which skips its tsconfig rewrite → `test_stryker_patterns_match_route_files_literally` asserts `inPlace`; a real pnpm TypeScript package with `tsconfig.json` lists the survivors on its changed line.
- [ ] A Node failure keeps its error line and `code:` above the frames → `test_node_failure_keeps_its_error_above_the_stack_frames`.
- [ ] In-place backups go to the external work directory, so Vitest's dot-directory discovery cannot run a backed-up test whose relative fixture is missing → the same config test asserts `tempDirName` is outside the package; a real Vitest suite importing a JSON fixture mutates.
- [ ] The sandbox-only pnpm `verify_deps_before_run` override is removed; in place, a package with `verifyDepsBeforeRun: error` still mutates → real pnpm fixture.

## Baseline + execution

Result: Passed
Evidence: main `9b243753` passed the Hard Eng workflow on push (run 36687195836). On that revision a TypeScript fixture with `tsconfig.json` reproduced "Cannot find package 'typescript'", and the new failure test fails.
Execution: One builder on branch `fix/stryker-typescript`.

## Risks + recovery

If the time limit kills Stryker, the snapshot keeps its instrumented files; both callers delete the snapshot. Recovery is reverting the commit.

## ux_reference

N/A — terminal report text; no product appearance.

## Verification

Result: Pending
Evidence: Pending — full `check --base origin/main` and the real Stryker runs.
E2E: Required — real Stryker 10.0.0 on a pnpm TypeScript package, installed in a snapshot worktree, lists survivors and leaves the snapshot clean.

Delivery target: Merge
Delivery: Pending — PR checks and squash merge.
