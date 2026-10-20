# Piped scripts reach Bun after a node flag's value

Status: Complete

## Outcome + scope

Issue 317: the Bun `node` shim from `bun_node` read the word after `-r`, `--require`, `--import` or `--loader` as a script name. It did not pass the piped script to Bun, so Bun printed its help and exited 0. A check that piped a script into `node -r <module>` passed without running. Make the shim skip that flag's value, so a call with only flags and piped input sends the script to Bun as `-`. Non-goals: other Node flags that take a separate value; the issue names only these four.

## Repository context

Owner: `.hooks/tool_setup.py` `bun_node`, which writes the shim's argument loop.
Test: `tests/test_tool_setup.py::test_node_with_a_script_on_stdin_runs_it_on_bun` already proves piped input with other flags.
Same cause: the shim's reading of node arguments; earlier fixes PR 310 (piped script) and PR 311 (flag-only calls) helped; a flag with a value was the last case, fixed here.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user approved the push, the PR and the remaining decisions.

## Acceptance + steps

- [x] A piped script that exits 3 after each of `-r`, `--require`, `--import` and `--loader` reaches Bun as `-`, and the shim exits 3 → `tests/test_tool_setup.py::test_node_with_a_script_on_stdin_runs_it_on_bun`.
- [x] Real Bun exits 1 for a piped `throw` after `-r node:fs` and `--require node:fs` → N/A — real Bun is not in the test run; the manual run in Verification proves it.

## Baseline + execution

Result: Passed
Evidence: develop `cf7f1a5f` passed the Hard Eng workflow (run 39397814511).
Execution: One builder.

## Risks + recovery

A call that passes a script name directly after one of the four flags now reads that name as the flag's value. Node reads it the same way. Recovery is reverting this branch.

## ux_reference

N/A — shim argument handling; no product appearance.

## Verification

Result: Passed
Evidence: The four new test cases failed before the fix and pass after it. With real Bun 1.4.2, a piped `throw` after `-r node:fs` and after `--require node:fs` exits 1 through the shim; before the fix both exited 0. Local gates: format, lint, complexity, annotations, types, dead-code and duplicates pass; the full test suite has only failures that also occur on the base in the cloud sandbox, which lacks Dart, Swift and stable signal timing.
E2E: Passed — the real shim ran real Bun with piped input.
Not checked locally: gitleaks, osv-scanner, shellcheck and actionlint, because the cloud sandbox cannot install them. CI covers these.
Independent review not done: Codex is not installed in the cloud sandbox, so `challenge` cannot run.

Delivery target: Merge
Delivery: Pending — PR checks into develop.
