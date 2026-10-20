# Piped scripts reach Bun after a node flag's value

Status: Complete

## Outcome + scope

Issue 317: the Bun `node` shim from `bun_node` read the word after `-r`, `--require`, `--import` or `--loader` as a script name. It did not pass the piped script to Bun, so Bun printed its help and exited 0. A check that piped a script into `node -r <module>` passed without running. Make the shim skip that flag's value, so a call with only flags and piped input sends the script to Bun as `-`. Non-goals: other Node flags that take a separate value; the issue names only these four.

## Repository context

Owner: `.hooks/tool_setup.py` `bun_node`, which writes the shim's argument loop.
Test: `tests/test_tool_setup.py` `test_node_with_a_script_on_stdin_runs_it_on_bun` already proves piped input with other flags.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user approved the push, the PR and the remaining decisions.

## Acceptance + steps

- [x] A piped script that exits 3 after each of the four flags reaches Bun as `-` and the shim exits 3 → Verification.
- [x] Real Bun exits 1 for a piped `throw` after `-r node:fs` and `--require node:fs` → Verification.

## Baseline + execution

Result: Passed
Evidence: Base `fbbb0312` gives the same 9 test failures in the dev sandbox as this branch. They need Dart and Swift, which that sandbox lacks.
Execution: One builder on branch `claude/project-thread-q8uglj`.

## Risks + recovery

A call that passes a script name directly after one of the four flags now reads that name as the flag's value. Node reads it the same way. Recovery is reverting this branch.

## ux_reference

N/A — shim argument handling; no product appearance.

## Verification

Result: Passed
Evidence: The four new test cases failed before the fix and pass after it. With real Bun 1.4.2, a piped `throw` after `-r node:fs` and after `--require node:fs` exits 1 through the shim; before the fix both exited 0. Full suite: 1725 passed, 9 failed; the same 9 fail on the base. Ruff check and format pass on the changed files.
E2E: Passed — the real shim ran real Bun with piped input.
Not checked: full `hard-eng.py check` in the dev sandbox, because its proxy blocks GitHub release lookups for tool installs. PR CI runs it.

Delivery target: Merge
Delivery: Pending — PR 323 checks.
