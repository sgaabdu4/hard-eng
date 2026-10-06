# Provision native tools outside the project

Status: Complete

## Outcome + scope

Hard Eng installs its native tools (`mise install` / `mise env`) from its own tool storage directory, not from the project root, so a project's pinned package manager can no longer break tool provisioning. Non-goals: tool versions, the mise launcher, storage locations and the CI workflow.

## Repository context

Owner: `.hooks/tool_setup.py` `provision_batch`, called by `provision_tools` and by `.hooks/mutation.py` for Stryker. It ran mise with `cwd=root`. mise installs `npm:` tools with pnpm (`MISE_NPM_PACKAGE_MANAGER=pnpm`), and pnpm 12 honours the project's `packageManager` pin. In a project pinned to `pnpm@11.8.0`, mise 2026.10.3 passed `--global-bin-dir` to pnpm 11, which rejects it, so CI failed while installing `npm:react-doctor` before any gate ran. The same install succeeds from an empty directory. Tools are installed globally into Hard Eng's storage, and `--no-config` already ignores project mise config, so nothing needs the project directory.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. On 2026-10-06 the owner gave full autonomy to fix everything found while rolling out 02f02959; this defect blocked a consumer's CI.

## Acceptance + steps

- [x] Provisioning runs mise from the tool storage directory, never from inside the project, even when the project pins an older pnpm → `test_tools_are_provisioned_outside_a_project_that_pins_pnpm`, which fails on the old `cwd=root`.
- [x] Existing provisioning behaviour (batches, environment, PATH) is unchanged → 94 tool setup, runner, CI setup, execution and mutation tests pass.

## Baseline + execution

Result: Passed
Evidence: Main `02f02959` passed CI and pre-push (18/18 gates) when it merged as #232.
Execution: One builder.

## Risks + recovery

A tool that relied on the project directory during installation would now install without it. None of the provisioned tools do: they are global installs into Hard Eng's storage. Recovery: revert the commit.

## ux_reference

N/A — tool provisioning has no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` on this branch passes every gate.
E2E: N/A — needs a networked mise and pnpm install; the focused test pins the working directory, and the consumer's CI is the runtime proof once updated.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
