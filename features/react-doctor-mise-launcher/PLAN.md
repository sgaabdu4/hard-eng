# Clear the React Doctor finding in the mise launcher

Status: Complete

## Outcome + scope

Fix [#188](https://github.com/sgaabdu4/hard-eng/issues/188): React Doctor 0.9.14's `command-execution-input-risk` rule flags the `pnpm view` call that #187 added to `mise_launcher` in `.hooks/tool_setup.py`, so root-package React projects that install Hard Eng fail their `react-doctor` gate on a file they cannot change. Pass the latest mise package spec through a module constant without changing the command, and add a test that fails when any installed hook matches the rule's subprocess pattern. Non-goals: excluding `.hooks/**` from consumer scans, which the [strict scanner gates](../../DECISION.md) decision forbids, and running React Doctor itself in this repository's checks.

## Repository context

Owner: `mise_launcher` in `.hooks/tool_setup.py` (argv `["pnpm", "view", f"{MISE_PACKAGE}@latest", ...]`). The rule matches an f-string with `{` within 220 characters after `subprocess.run(` when no `)` comes first. The two f-strings in `install_launcher` (`--allow-build=` and the versioned spec) follow `str(staging)`, whose `)` ends the window, so the rule does not flag them. A port of the pattern that reports every match, not only React Doctor's first per file, finds only this call across `.hooks/`. Prior fix of the same kind: [react-doctor-hook-findings](../react-doctor-hook-findings/PLAN.md).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix #188 in one PR with a regression proof, merge when green and verify main CI.

## Acceptance + steps

- [x] React Doctor 0.9.14 on a root React fixture containing the installed `.hooks` reports no `.hooks/**` diagnostic → rerun the fixture scan.
- [x] `mise_launcher` runs the same `pnpm view @jdxcode/mise@latest version --json` command → existing `tests/test_tool_setup.py` passes.
- [x] A hook that interpolates an f-string into a subprocess argv within the rule's window fails a test → new test in `tests/test_updates.py`, red on the unfixed hook.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Draft` on unchanged `649b6da` + this plan → exit 0 (plan-only change: secret scan PASS); main CI on `649b6da` green.
Execution: One builder; module constant for the package spec, one pattern test.

## Risks + recovery

The test pins React Doctor 0.9.14's pattern, so a later rule change can flag hooks without this test failing; repair such findings at their owner the same way. A gate that runs React Doctor here would need a React fixture, network access and a moving tool version for one rule, so the pinned pattern is the smallest deterministic proof.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: Root React fixture (`package.json` with React, one `.tsx` component, installed `.hooks`) under React Doctor 0.9.14 with the gate's arguments → unfixed hooks exit 1 with `.hooks/tool_setup.py:205:9 command-execution-input-risk (error)`, the only diagnostic; fixed hooks exit 0 with 0 diagnostics, also with the installed `.agents/skills` tree added. New test fails on the unfixed hook with `['.hooks/tool_setup.py:205']` and passes after the fix. `python3 .hooks/hard-eng.py check --base origin/main` → 17/17 gates PASS, 944 tests, 0 failures.
E2E: N/A — hook refactor; the native React Doctor fixture scan exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
