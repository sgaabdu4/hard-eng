# Bun node shim runs piped scripts after flags

Status: Complete

## Outcome + scope

A `node` call with only flags and no script, such as `node --input-type=module <<EOF`, now runs the piped script on Bun and returns its exit code, as Node does. The earlier fix covered only `node` with no arguments; with flags, the shim still ran Bun with no script, which prints its help and exits 0.
Non-goals: no other flag translation; calls that name a script, `-e`, `-p`, `-`, `--check`, `--test`, help or version keep running Bun directly.

## Repository context

Owner: [tool_setup.py](../../.hooks/tool_setup.py) `bun_node`; the shim is rewritten on every tool setup, so installs get it at update.
Evidence: Bun 1.4.3: `echo 'process.exit(3)' | bun --input-type=module` prints help and exits 0, while `| bun --input-type=module -` runs the script and exits 3, for module and CommonJS code; Node exits 3 for both. Two projects' Vercel guard scripts used `node --input-type=module` with a heredoc and passed every rejection case under Hard Eng's checks.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to update every project to the latest Hard Eng with every check passing; a fault in Hard Eng's own shim that makes checks pass wrongly is Hard Eng's to fix. Codex adversarial review loop before the PR; merge when green.
Decisions: Treat a call as piped when every argument starts with `-` and none names its own program. A flag whose value is a separate word (for example `-r dotenv/config`) counts as naming a script, so it keeps the earlier behaviour instead of guessing.

## Acceptance + steps

- [x] `--input-type=module` with a piped script feeds it to `bun --input-type=module -`; `-e`, a script name and `-` pass through unchanged → `test_node_with_a_script_on_stdin_runs_it_on_bun`, red before.
- [x] Real Bun through the shim: piped scripts return their exit codes with no flags, `--input-type=module` and `--no-warnings`; empty stdin exits 0; `-e`, `-`, `--version` and `-r` with `-e` behave as before.
- [x] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, real Bun run, full check, Codex loop, PR, merge.

## Risks + recovery

A flag-only call with a terminal on stdin now waits for input instead of showing Bun's help; checks have no terminal. Recovery is reverting this branch.

## ux_reference

N/A — tool shim only; no product appearance.

## Verification

Result: Passed
Evidence: The extended test failed before the fix and passed after; real Bun 1.4.3 runs through the generated shim matched Node's exit codes in every case above.
E2E: Passed — real Bun through the generated shim.

Delivery target: Merge
Delivery: Pending — PR CI, merge.
