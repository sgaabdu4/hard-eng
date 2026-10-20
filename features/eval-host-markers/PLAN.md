# Eval host markers

Status: Complete

## Outcome + scope

Eval agents started by `tests/agent_checks.py` no longer inherit host markers such as `CLAUDECODE` or `CODEX_THREAD_ID`. Before, an eval run from inside a Claude or Codex session passed these markers to the agent under test, so Hard Eng's hooks could treat that agent as the host. Codex runs keep their fresh `CODEX_HOME`. Non-goals: other environment isolation.

## Repository context

Owners: `stream` in `tests/agent_checks.py` starts every eval agent; `challenge.py` already strips the same markers for the reviewer, so both now use its helper, renamed `without_host_markers`.
Same cause: one cause, eval agents got the host environment as it was.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, with every decision made by the agent.

## Acceptance + steps

- [x] An eval agent sees no host markers, keeps `PATH` and gets the given `CODEX_HOME` → `tests/test_agent_checks.py::test_an_eval_agent_does_not_inherit_host_markers`.

## Baseline + execution

Result: Passed
Evidence: `develop` 413d1d8: the new test failed there.
Execution: One builder; failing test, then the fix.

## Risks + recovery

A tool that an eval agent needs and that reads a `CODEX_*` variable other than `CODEX_HOME` loses it; recovery is to pass it in the overrides.

## ux_reference

N/A — test harness change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1818 passed, the same 8 environment failures as `develop`; `tests/test_agent_checks.py` and `tests/test_challenge.py` 61 passed. Ruff, Pyrefly (0 errors), Vulture and jscpd (0 clones) pass.
E2E: N/A — live eval runs need Codex and run on Abid's Mac through the release canary.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
