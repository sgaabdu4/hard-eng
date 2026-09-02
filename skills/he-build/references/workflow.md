# Build Workflow

## Enter + Resume

1. `he` inspect → require approved PLAN + `build-ready|building` + exact active slice/completed slices/next action + emitted `slice_receipt|full_receipt` debt; `missing|stale` debt = proof still owed on the current tree.
2. `deterministic-checks` worktree `write` → PASS.
   - FAIL from setup/readiness owner → use `repair` for the smallest blocked owner + focused contract → rerun `write`.
   - PASS after repair → start the accepted behavior; defer independent repair delivery/full gates until behavior proof unless continuation is unsafe, corrupting, or unverifiable.
3. Build working instruction ledger = accepted outcome/non-goals/material decisions/acceptance/risk + every later user/delegated outcome, constraint, example, exclusion, and correction.
4. Reconcile conflicts = later guidance supersedes exact conflicting item only; nonconflicting items accumulate; material outcome/risk delta → reopen; implementation detail → continue.
5. Read current code/tests/docs + actual repository diff before edit; map every ledger item to owner + proof + `open|proven|N/A|blocked|superseded`.
6. `build-ready` → preserve inspected `completed_slices` exactly → select the first remaining planned `S-ID` not present in that ordered set → run `he` checkpoint with current token:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set lifecycle_status=building --set active_slice=<first-remaining-S-ID> --set "completed_slices=<inspected-ordered-value>" --set "next_action=<first-remaining-observable-behavior>"`

7. `building + active_slice=none + completed_slices!=none` → resume the recorded final pre-ship action; do not invent another slice.
8. Missing remaining slice in `build-ready` OR progress conflicting with the living brief → stop as invalid state; resetting/omitting completed progress = forbidden.
9. Other `building` resume = continue recorded active slice; do not recreate PLAN, candidate patch, manifest, audit packet, or approval receipt.

## Slice Loop

1. Select one independently demonstrable end-to-end behavior from active slice → state precondition + action + durable observable result; required persistence/API/backend/UI = one path, never separate skeleton-first completion.
2. Bug/regression → reproduce first; behavior with a useful automated seam → `test-quality` RED for intended reason; non-applicable RED or no feasible real-boundary seam → record why.
3. Change canonical owner + every connected caller/schema/key/route/config/test/doc required by that behavior.
4. Run targeted GREEN + smallest relevant deterministic checks.
5. Refactor → remove legacy/alias/dual paths + enforce SSOT/DRY/YAGNI → rerun targeted GREEN.
6. Review actual diff once with `code-review`; standard slice requires no independent whole-feature audit.
7. Validate each finding:
   - implementation defect → fix root in place + connected blast radius → affected proof + finding-scoped re-review;
   - accepted outcome change → `he` `reopen --reason changed-outcome` → `he-plan`;
   - material security/privacy/data-loss/irreversible contract change → `he` `reopen --reason material-safety-contract` → `he-plan`;
   - taste/duplicate/unsupported claim → reject with evidence.
8. Critical/risky slice → targeted independent review of changed protected boundary + callers + negative/recovery cases:
   - auth/security/privacy/trust → `security-review`;
   - data-loss/irreversible/schema/recovery → `code-review` + applicable domain/test/runtime owner;
   - other scoped critical overlay → its named specialist owner.
   - scope = changed protected boundary only; unrelated slices = forbidden.
9. UI/runtime behavior → finish every backend/persistence connection required by the active behavior → `e2e` actual environment + canonical `e2e` receipt PASS; inspect requested/produced media; reference/screenshot/receipt work never gates unfinished backend/persistence wiring.
10. Demonstrate acceptance example + rollback/observability when applicable → run the slice gate on the final slice tree → receipt PASS via the `deterministic-checks` slice-gate reference; checkpoint rejects missing/stale receipts.
11. Refresh PLAN token → one atomic `he` checkpoint:
    - append current `S-ID` once to comma-separated `completed_slices`;
    - more slices → `active_slice=<next-S-ID>` + `next_action=<next-observable-behavior>`;
    - no slices remain → `active_slice=none` + `next_action=Run the full pre-ship gate.`
    - command = `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set "completed_slices=<ordered-comma-list>" --set active_slice=<next-S-ID|none> --set "next_action=<exact-next-action>"`.
12. First completed end-to-end surface slice (`ux_reference` != n/a) → display the receipt's actual screenshots/video in the conversation (per-view, desktop + mobile as applicable; never only paths) → one `question-me` user look-and-feel acceptance before the next independently complete behavior; visual acceptance never pauses persistence/API/backend work required by the current behavior; changed look → `ux_reference` change = `he` reopen route.
13. Inspect checkpoint → require recorded completed/active/next values → continue the recorded next action.
14. Before slice close/turn end → reconcile current messages + ledger; any omitted open item keeps slice/task nonterminal.

## Finding Rules

- Discovered connected file/schema/route/test = implement now; never request planning approval for path bookkeeping.
- Gate failure = diagnose root → fix in active/final loop → affected proof.
- Repeated same implementation root ≥2 → `repeated-failure-learning`; build continues when a safe corrected approach exists.
- Protected-boundary uncertainty = stop affected mutation + one material question.
- Process gap = record verified `he-learn` trigger + continue; no routine cross-repository source pause; execution follows global Subagents contract.
- Unrelated process/tooling finding = record exact delivery deadline + keep active behavior on the critical path; repair after behavior proof and before its required gate/delivery.

## Final Pre-ship Gate

1. All slices demonstrated → update README/API/user/operator/design docs only for accepted current truth.
2. Run one full repository gate through `deterministic-checks` with explicit timeout + slice gate `--full` receipt on the same snapshot; the `green` checkpoint rejects a missing/stale `full` receipt.
3. User-visible journeys → replay relevant cross-slice behavior through `e2e`; requested/produced visual proof requires canonical actual-media receipt PASS.
4. Applicable protected boundaries → confirm every targeted independent review remains current.
5. Full-gate finding → return to final build loop → root fix + affected proof → rerun the full gate on the corrected exact snapshot.
6. Repeat finding → fix → affected proof → full-gate run while findings or snapshot changes remain; convergence requires one unchanged corrected snapshot with full gate PASS.
7. Unchanged full-gate PASS + actual diff reviewed + zero open finding/unknown → refresh token → run:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set lifecycle_status=green --set active_slice=none --set "completed_slices=<ordered-comma-list>" --set "next_action=<exact-delivery-action-or-approval-boundary>"`

## Ticket Loop

1. `ticket_state.py claim --next` (or `--ticket <id>`) → per-ticket flock + whole-file CAS win → records `claimed_by`/`claimed_at`/`worktree`/`branch` in the ticket state (`--session-id` sets `claimed_by`) → `git worktree add <path> -b ticket/<slug>/T-<n> origin/<default>`.
2. `materialize` → worktree gets a byte-copy of the v2 PLAN + `research.json` + a fresh worktree-local `authorization.json` keyed to the epic fingerprint, no expiry; never a `tickets/` mirror.
3. Worktree `write` PASS → first checkpoint `status=building`.
4. Unchanged Slice Loop (above), scoped to the ticket's own `slices` only; every state write goes through `ticket_state.py checkpoint`, never `plan_state.py`.
5. All ticket slices done → full project gate + slice gate `--full` on the worktree tree + `code-review` of the ticket's actual diff (+ critical overlay when the ticket holds the risky slice) → checkpoint `status=green` (records ticket `green_artifact`).
6. Ticket `green` → hand off to `he-ship` scoped to this ticket (workflow.md `Ticket Ship`); publish/rebase/commit/push/PR/CI stay forbidden here, same as any slice.
7. Ticket `shipped` → `claim --next` for the next todo ticket; board empty → report board, stop looping.

## Ticket Integration

1. Every work ticket `shipped` → integration ticket `T-int` claimable, worktree = the PRIMARY checkout only, pulled to the default branch containing every merged ticket PR.
2. Claiming session runs the same Claim → Materialize flow as any other ticket; the freshly minted worktree-local `authorization.json` uses the current epic fingerprint and touches neither PLAN bytes nor the approval fingerprint.
3. Run the Final Pre-ship Gate (above) against the EPIC plan on the integrated primary tree: epic full receipt + EVERY epic acceptance ordinal A-1..A-k re-verified on the integrated tree (not trusting per-ticket proofs) + cross-slice `e2e`.
4. T-int `green` → epic checkpoint `building` to `green` with a bulk completed-slices list covering every `S-ID`, gated by `ticket_state.epic_green_gate_error()` in place of the +1-progress and per-slice-receipt rules (every work ticket shipped + T-int green + bulk list = exact partition + acceptance coverage complete); the full-receipt requirement + `green_artifact` binding stay unchanged.
5. Any cancelled/unclaimed/unfinished ticket → partition incomplete → gate stays closed → epic cannot green until `decompose --reconcile` reassigns those slices.
6. Epic `green` → hand off to `he-ship` Epic Closure (workflow.md), unchanged Finish path to `shipped`.

## Pause

- Material outcome/protected-contract decision → checkpoint exact evidence + one question + `next_action`; reopen only with the matching accepted `he` reason.
- External dependency/authority → checkpoint owner + condition + exact resume action.
- Before handoff/turn end → checkpoint completed slices + active slice + next action.
