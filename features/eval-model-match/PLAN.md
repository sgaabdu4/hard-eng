# Eval model match

Status: Complete

## Outcome + scope

An eval run that the client served on a model other than the requested one is blocked, not graded. Before, a fallback or a wrong alias let a run on another model pass as a run on the requested model. Non-goals: effort level checks.

## Repository context

Owner: `execute` in `tests/agent_checks.py`. Each client already records the model it used in `settings["model"]`: Codex from its session record, Claude from its init event. Claude reports full IDs for aliases (`opus` → `claude-opus-…`), so the match is "requested name inside the used name".
Same cause: one cause, the recorded model was saved but never compared.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, with every decision made by the agent.

## Acceptance + steps

- [x] A run on another model is blocked; a run on the requested model's full ID is graded → `tests/test_agent_checks.py::test_a_run_on_another_model_than_requested_is_not_graded`.

## Baseline + execution

Result: Passed
Evidence: `develop` 376e9de: the blocked row failed there; the run passed.
Execution: One builder; failing test, then the check.

## Risks + recovery

A client that reports a model name without the requested alias in it blocks every run; recovery is to request the reported name.

## ux_reference

N/A — test harness change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1826 passed, the same 8 environment failures as `develop`; `tests/test_agent_checks.py` 35 passed. Ruff, Pyrefly (0 errors), Vulture and jscpd (0 clones) pass.
E2E: N/A — live eval runs need Codex and run on Abid's Mac through the release canary.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
