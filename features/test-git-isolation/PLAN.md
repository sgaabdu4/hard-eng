# Test git isolation

Status: Complete

## Outcome + scope

The test suite's git commands ignore the developer's global git config. Before, a global setting such as commit signing, a hooks path or a default branch name changed fixture repositories, and tests failed or slowed down. Non-goals: the system git config, which belongs to the machine's admin.

## Repository context

Owner: `tests/conftest.py`, which already clears the hosting workflow's environment at import. Fixture identity comes from `init`, which writes a local `user` section.
Same cause: one cause, fixtures read `~/.gitconfig`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, with every decision made by the agent.

## Acceptance + steps

- [x] Fixture git sees no global config → `tests/test_runner.py::test_fixture_git_ignores_the_developers_global_config`.

## Baseline + execution

Result: Passed
Evidence: `develop` 16fec2f: the new test failed there, because this machine's global config turns on commit signing. With a global config that sets signing, a missing hooks path and branch `trunk`, `tests/test_challenge.py` errored at its first fixture.
Execution: One builder; failing test, then the fix.

## Risks + recovery

A test that needed a global setting now fails; recovery is to set it in that fixture's local config.

## ux_reference

N/A — test setup with no visual surface.

## Verification

Result: Passed
Evidence: Full suite with that hostile global config: 1818 passed, the same 8 environment failures as `develop`, in 6 min 35 s instead of about 8 min 30 s, because fixture commits are no longer signed. Pyrefly 0 errors.
E2E: N/A — the full suite is the real consumer of the change.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
