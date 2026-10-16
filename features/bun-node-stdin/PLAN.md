# Bun node shim runs stdin scripts

Status: Complete

## Outcome + scope

A `node` call with no arguments, which Node uses to run a script piped on stdin, now runs that script on Bun and returns its exit code; empty stdin exits 0, as Node does. Before, the shim ran bare `bun`, which prints its help and exits 0, so a `node <<EOF` check in a project passed without running.
Non-goals: no other node flag mapping; no change to the wrangler and miniflare Node path.

## Repository context

Owner: [tool_setup.py](../../.hooks/tool_setup.py) `bun_node`, which writes the shim on every tool setup, so existing installs get the new line at their next update.
Evidence: Bun 1.4.3: `echo 'process.exit(3)' | bun` prints help and exits 0; `| bun -` runs the script and exits 3; `| node` exits 3. A project's guard script that fed checks to `node` on stdin passed every rejection case under Hard Eng's checks.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to update every project to the latest Hard Eng with every check passing; a fault in Hard Eng's own shim that makes checks pass wrongly is Hard Eng's to fix. Codex adversarial review loop before the PR; merge when green.
Decisions: Map only the no-argument call to `bun -`, the form Bun documents for stdin, and leave every other call unchanged. The shim reads stdin first because `bun -` fails on empty input where Node exits 0 (Codex round 1), and uses an `if` block because `exec` inside a pipe would fall through to bare `bun`.

## Acceptance + steps

- [x] The shim with no arguments feeds stdin to `bun -`, returns its exit code, and exits 0 on empty stdin → `test_node_with_a_script_on_stdin_runs_it_on_bun`, red before.
- [x] Real Bun through the shim: a piped script returns its exit code (3), empty stdin exits 0, a script with blank lines keeps them, and `-e` still works.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, real Bun run, full check, Codex loop, PR, merge.

## Risks + recovery

An interactive `node` call with no arguments now waits for stdin instead of showing Bun's help; checks have no terminal. Recovery is reverting this branch.

## ux_reference

N/A — tool shim only; no product appearance.

## Verification

Result: Passed
Evidence: The new test failed before the fix and passed after; a real Bun 1.4.3 run through the shim ran a piped script and returned exit code 3.
E2E: Passed — real Bun through the generated shim.

Delivery target: Merge
Delivery: Pending — PR CI, merge.
