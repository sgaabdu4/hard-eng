# Clear React Doctor findings in installed Hard Eng hooks

Status: Complete

## Outcome + scope

Fix [#145](https://github.com/sgaabdu4/hard-eng/issues/145): in a React repository whose package is at the root, React Doctor's `command-execution-input-risk` rule flags installed Hard Eng hooks, so the project's gate fails on files it cannot change. Remove the f-string interpolation from every matching `subprocess.run` argument list without changing any command. Non-goals: excluding `.hooks/**` or `.agents/**` from the scan, which the [strict scanner gates](../../DECISION.md) decision forbids and the earlier [scaffold finding](../../DECISION.md) resolved the same way.

## Repository context

Owners: `erased_dart` in `.hooks/dart_coverage.py` (`--packages=` argument) and `fetch_sources`, the update commit and `preserved_instructions` in `.hooks/update.py` (clone URL, commit message, `git show` object). The rule matches any f-string within 220 characters after `subprocess.run(` and reports only the first match per file, so fixing the two reported lines exposed `update.py:452`; a local port of the rule found the fourth at `update.py:656`. React Doctor 0.9.14 on a root Next.js fixture with the full installed `.agents/skills` tree (including the Flutter and Appwrite skills) and `.hooks` flags no `.agents/**` file; the issue's `.agents/**` findings did not reproduce.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix open Hard Eng issues, cover edge cases, open a PR and merge it.

## Acceptance + steps

- [x] React Doctor 0.9.14 on the root React fixture reports no `.hooks/**` or `.agents/**` diagnostics → rerun the fixture scan.
- [x] All four commands keep identical argument arrays → existing `tests/test_dart_coverage.py` and `tests/test_updates.py` pass.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `4bd363d` + this plan → exit 0; 17/17 gates PASS, 800 tests.
Execution: One builder; hoist each interpolated argument into a local before the call.

## Risks + recovery

A later React Doctor rule may flag other installed files; repair them at their owner the same way. Revert the hoists if any command changes.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: Unfixed hooks → React Doctor 0.9.14 exits 1 with `command-execution-input-risk` at `.hooks/dart_coverage.py:75` and `.hooks/update.py:111`. Fixed hooks → the same root React fixture (full `.agents/skills` + `.hooks`) exits 0 and `reports.validate_react_doctor` accepts the report. `tests/test_dart_coverage.py` + `tests/test_updates.py` → 45 passed. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS.
E2E: N/A — hook refactor; the native React Doctor fixture scan exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
