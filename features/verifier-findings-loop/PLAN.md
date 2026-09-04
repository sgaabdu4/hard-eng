# Feature Brief: Verifier Findings Loop

<!-- hard-eng-state:v1 -->
- state_version = 1
- plan_id = verifier-findings-loop-92c16fc5
- lifecycle_status = planning
- approval_status = pending
- approval_fingerprint = none
- approval_provenance = none
- green_artifact = none
- active_slice = S-1
- completed_slices = none
- next_action = Update changed frozen constraints and request Ready-to-build approval.
- replan_reason = changed-outcome
<!-- /hard-eng-state -->

## Outcome
- A verifier finding sends the build back to code the same way a review finding does: the verify record carries rounds with findings, an open finding blocks the slice gate and the full gate and prints as the next action, the loop stops after three rounds and asks the user; green then waits for the user's approval of `BUILD.md` before ship starts, and shipped writes `features/<slug>/SHIP.md` with the delivery SHA, the CI run, and the receipt summary.

## Non-goals
- Human-readable per-slice files (`S-n.md`); JSON receipts stay the only record.
- Automatic `he-learn` triggering on process failures; separate feature.
- Ticket-mode record gaps and parallel features; separate features.
- Changing what reviewers or verifiers check; only how their findings flow.

## Material decisions
- Verify record = `rounds` like review: each round has `verifier`, `packet_sha256`, `findings` (id, text, status open|fixed|rejected with reason) plus the existing mode, fakes, outside_calls, before, after, edge_cases; at most three rounds; round three still open = stop and ask the user; the round's `packet_sha256` must match the current verify packet.
- Gate = slice gate and full gate refuse while the last verify round has an open finding; `inspect` prints `build_steps_open_finding` for verify findings as it does for review; the whole-feature verify record (`full`) follows the same rule.
- Batch rule = after review and verify findings, fix every finding, then one re-review and one re-verify; the he-build skill states it and the record shapes keep each round bound to the tree.
- BUILD.md approval = `checkpoint --set lifecycle_status=green` writes `BUILD.md` as today, then `plan_state.py approve-build --approval-reply "<user words>"` records the user's plain yes as `build_approval` in the state block; `assert-green` and `inspect handoff=ship` refuse until it is recorded; a tree change after the approval clears it.
- SHIP.md = `checkpoint --set lifecycle_status=shipped --set next_action=...` generates `features/<slug>/SHIP.md` from the plan state, the green artifact, the mutation receipt totals, and a required `--delivery-sha` and `--ci-url`; the file is generated, never hand-written.
- Verifier and reviewer subagents default to the cheapest capable model; the packet text says so.
- ux_reference = n/a
- ux_reference_sources = n/a

## Acceptance examples
- Given a verify payload whose last round has a finding with status open, when the slice gate runs, then it fails naming the finding and `inspect` prints it as `build_steps_open_finding`.
- Given a verify payload with four rounds, when `record-build --step verify` runs, then it refuses saying round four needs the user.
- Given a verify round whose `packet_sha256` does not match the current verify packet, when `record-build` runs, then it refuses naming the packet file.
- Given every verify finding closed as fixed or rejected with a reason, when the slice gate runs on fresh records, then it passes.
- Given a plan at green with no build approval, when `assert-green` runs, then it refuses naming `BUILD.md`; after `approve-build` with the user's reply it passes and `inspect` prints `handoff=ship`.
- Given a build approval and then a product file change, when `inspect` runs, then `build_approval` reads stale and `assert-green` refuses again.
- Given a shipped checkpoint with `--delivery-sha` and `--ci-url`, when it completes, then `features/<slug>/SHIP.md` exists with the SHA, the URL, the green artifact, and the mutation totals, and a checkpoint without them refuses.

## Affected canonical areas
- `skills/he/scripts/build_steps.py` (verify validator, open findings, gate errors, inspect lines), `skills/he/scripts/build_steps_regression.py`.
- `skills/he/scripts/plan_state.py` and `skills/he/scripts/plan_handoff.py` (approve-build, assert-green, handoff, shipped checkpoint), `skills/he/scripts/build_report.py` (SHIP.md), `skills/he/scripts/plan_parser.py` (state field).
- `skills/he/scripts/review_packet.py` (verifier rules text), `skills/he-build/SKILL.md`, `skills/he-ship/SKILL.md`, `skills/he/SKILL.md`, `skills/he/references/`.
- `hard-eng.gates.json` required paths, `scripts/check-skill-contracts.py`, `scripts/fast_feature_loop_contracts.py`.

## Risk and rollback
- risk_level = standard
- critical_overlay = none
- rollback = revert the commits; existing plans with one-round verify records stay valid because a record without rounds is read as one closed round.
- deferred = none
- blocked_on = none
- tickets = none
- tracker = not-probed

## Vertical slices
- S-1 = verify record rounds and findings: validator, open finding blocks slice and full gates, inspect prints it, three-round cap, regression; depends_on = none
- S-2 = BUILD.md approval: `approve-build`, `build_approval` state field, stale on tree change, `assert-green` and handoff refuse without it, regression; depends_on = S-1
- S-3 = SHIP.md generation at the shipped checkpoint with required delivery SHA and CI URL, plus he-build/he-ship/he skill text for the batch rule and the new gates; depends_on = S-2
- proof = build_steps and plan_state regressions, skill contracts, full push gate, CI.
