# Feature Brief: Plan Step Answers

<!-- hard-eng-state:v1 -->
- state_version = 1
- plan_id = plan-step-answers-ce8e3a30
- lifecycle_status = green
- approval_status = approved
- approval_fingerprint = sha256:447d0d3e87d3771bce283de51c30cad86346186e9f83356b763ac1e0543c67d0
- approval_provenance = ready-to-build
- green_artifact = sha256:578773e66ff170efafd9c4415d0d322c73584a3f10e7532d9e66bd3c4f30ea84
- active_slice = none
- completed_slices = S-1,S-2
- next_action = Commit, push main, verify CI.
- replan_reason = none
<!-- /hard-eng-state -->

## Outcome
- Every recorded planning step must answer a fixed list of named questions before it counts; a step receipt that only exists, or answers with a placeholder, is refused, so approval is impossible until the plan says what could break, who owns it, what was rejected and why, why the first slice is the thinnest complete path, and what is still unknown going into build.

## Non-goals
- Judging whether an answer is true or deep; the check proves the answer is present, specific text, not a placeholder.
- Changing the edge-scan step; its seven axes already are a fixed answer list.
- Changing research, approval, handoff, or ticket generation.

## Material decisions
- Answers live in an `answers` object inside the step payload; every listed key required, nonempty after trim, unknown keys refused, exactly like edge-scan axes.
- `code-study` answers = `could_break` (what this change can break), `owner` (who or which file owns that blast radius), `existing_capability` (the simpler existing thing checked, or `none`), `external_contract` (outside contract this depends on, or `none`); free-text `notes` is replaced by these answers.
- `decisions` answers = per decision a `rejected` field (alternatives considered and why not; for an open `user-decision` the options the user is choosing between).
- `slices` answers = `thinnest_path` (why S-1 alone proves value) + `parallel` (which slices can run at the same time, or `none`); a slices payload built from the brief still requires these two answers.
- `closing` answers = `unknowns` (what is still unknown going into build, or `none`).
- Placeholder rule = answer text equal to `tbd`, `todo`, `tba`, `n/a`, or `?` after trim and lowercase is refused; `none` stays legal wherever the question allows it.
- Receipt `schema_version` moves 1 → 2 so an older receipt without answers is refused on load; no real receipt exists outside test fixtures.
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given a `code-study` payload with owners but no `answers`, when `record-step` runs, then it fails naming the first missing answer and writes no receipt.
- Given a `slices` payload whose `thinnest_path` is `TBD`, when `record-step` runs, then it fails naming the placeholder and writes no receipt.
- Given a `closing` payload with an unknown answer key, when `record-step` runs, then it fails naming the unknown key.
- Given every step recorded with complete answers, when `approve` runs with the user's reply, then it passes as before.
- Given a schema-1 receipt from before this change, when `inspect` runs, then the plan-steps line reports it invalid.

## Affected canonical areas
- `skills/he/scripts/plan_steps.py` (validators, ANSWERS table, schema version).
- `skills/he/scripts/plan_steps_regression.py` + `skills/he/scripts/execution_evidence_regression.py` (fixtures + negative cases).
- `skills/he-plan/SKILL.md` Method table + `skills/he-plan/references/feature-brief.md` workflow rows.

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = revert the commit; no receipt outside fixtures depends on schema 2.
- deferred = none
- blocked_on = none
- tickets = none
- tracker = not-probed

## Vertical slices
- S-1 = answers required and checked in `plan_steps.py` with schema 2, both regression fixtures updated, negative cases for missing, placeholder, unknown key, and old schema; depends_on = none
- S-2 = he-plan Method table and feature-brief workflow name every answer per step; doc contract checks green; depends_on = S-1
- proof = `plan_steps_regression.py` + `execution_evidence_regression.py` + `scripts/check-skill-contracts.py` green, then full push gate.
