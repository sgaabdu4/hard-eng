# Documented commands

Status: Complete

## Outcome + scope

A test fails when `AGENTS.md`, `README.md` or a skill file names a `hard-eng.py` command or flag that the CLI lacks. Before, a renamed command or flag left docs that sent agents into a usage error. Non-goals: commands of other tools.

## Repository context

Owner: `tests/test_skill_links.py`, which keeps distributed skills loadable and their links resolvable. The CLI's own `--help` output is the source of truth for commands and flags. All 18 current mentions resolve.
Same cause: N/A — a missing drift check, not a present fault.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop` and to back skill rules with deterministic checks, with every decision made by the agent.

## Acceptance + steps

- [x] Every documented command and flag exists → `tests/test_skill_links.py::test_documented_commands_and_flags_exist`.
- [x] An unknown command or flag fails, and a flag that only prefixes a real one (`--merge` vs `--merge-method`) fails → `tests/test_skill_links.py::test_an_unknown_command_or_flag_in_docs_fails`.

## Baseline + execution

Result: Passed
Evidence: `develop` 77d1dc5: the full suite had only the 8 known environment failures.
Execution: One builder.

## Risks + recovery

A doc that shows a command in a non-code sentence is also checked; recovery is to name a real command.

## ux_reference

N/A — test change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1820 passed, the same 8 environment failures as `develop`; `tests/test_skill_links.py` 8 passed. Ruff, Pyrefly (0 errors), Vulture and jscpd (0 clones) pass.
E2E: N/A — the test runs the real CLI's help for each documented command.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
