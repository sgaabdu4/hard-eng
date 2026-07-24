# Build Workflow

## Enter + Resume

1. `$he` inspect → require approved PLAN + `build-ready|building` + exact active slice/completed slices/next action.
2. `$deterministic-checks` worktree `write` → PASS.
3. Read accepted outcome + non-goals + material decisions + acceptance examples + affected canonical areas + risk/rollback + first vertical slice.
4. Read current code/tests/docs + actual repository diff before edit.
5. `build-ready` → preserve inspected `completed_slices` exactly → select the first remaining planned `S-ID` not present in that ordered set → run `$he` checkpoint with current token:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set lifecycle_status=building --set active_slice=<first-remaining-S-ID> --set "completed_slices=<inspected-ordered-value>" --set "next_action=<first-remaining-observable-behavior>"`

6. `building + active_slice=none + completed_slices!=none` → resume the recorded final pre-ship action; do not invent another slice.
7. Missing remaining slice in `build-ready` OR progress conflicting with the living brief → stop as invalid state; resetting/omitting completed progress = forbidden.
8. Other `building` resume = continue recorded active slice; do not recreate PLAN, candidate patch, manifest, audit packet, or approval receipt.

## Slice Loop

1. Select one independently demonstrable behavior from active slice → state precondition + action + observable result.
2. Bug/regression → reproduce first; behavior with a useful automated seam → `$test-quality` RED for intended reason; non-applicable RED → record why.
3. Change canonical owner + every connected caller/schema/key/route/config/test/doc required by that behavior.
4. Run targeted GREEN + smallest relevant deterministic checks.
5. Refactor → remove legacy/alias/dual paths + enforce SSOT/DRY/YAGNI → rerun targeted GREEN.
6. Review actual diff once with `$code-review`; standard slice requires no independent whole-feature audit.
7. Validate each finding:
   - implementation defect → fix root in place + connected blast radius → affected proof + finding-scoped re-review;
   - accepted outcome change → `$he` `reopen --reason changed-outcome` → `$he-plan`;
   - material security/privacy/data-loss/irreversible contract change → `$he` `reopen --reason material-safety-contract` → `$he-plan`;
   - taste/duplicate/unsupported claim → reject with evidence.
8. Critical/risky slice → targeted independent review of changed protected boundary + callers + negative/recovery cases:
   - auth/security/privacy/trust → `$security-review`;
   - data-loss/irreversible/schema/recovery → `$code-review` + applicable domain/test/runtime owner;
   - other scoped critical overlay → its named specialist owner.
   - scope = changed protected boundary only; unrelated slices = forbidden.
9. UI/runtime behavior → `$e2e` actual environment + canonical `$e2e` receipt PASS; inspect requested/produced media.
10. Demonstrate acceptance example + rollback/observability when applicable → refresh PLAN token → one atomic `$he` checkpoint:
    - append current `S-ID` once to comma-separated `completed_slices`;
    - more slices → `active_slice=<next-S-ID>` + `next_action=<next-observable-behavior>`;
    - no slices remain → `active_slice=none` + `next_action=Run the full pre-ship gate.`
    - command = `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set "completed_slices=<ordered-comma-list>" --set active_slice=<next-S-ID|none> --set "next_action=<exact-next-action>"`.
11. Inspect checkpoint → require recorded completed/active/next values → continue the recorded next action.

## Finding Rules

- Discovered connected file/schema/route/test = implement now; never request planning approval for path bookkeeping.
- Gate failure = diagnose root → fix in active/final loop → affected proof.
- Repeated same implementation root ≥2 → `$repeated-failure-learning`; build continues when a safe corrected approach exists.
- Protected-boundary uncertainty = stop affected mutation + one material question.
- Process gap = send verified trigger to `$he-learn` asynchronously; no routine cross-repository source pause.

## Final Pre-ship Gate

1. All slices demonstrated → update README/API/user/operator/design docs only for accepted current truth.
2. Run one full repository gate through `$deterministic-checks` with explicit timeout.
3. User-visible journeys → replay relevant cross-slice behavior through `$e2e`; requested/produced visual proof requires canonical actual-media receipt PASS.
4. Applicable protected boundaries → confirm every targeted independent review remains current.
5. Full-gate finding → return to final build loop → root fix + affected proof → rerun the full gate on the corrected exact snapshot.
6. Repeat finding → fix → affected proof → full-gate run while findings or snapshot changes remain; convergence requires one unchanged corrected snapshot with full gate PASS.
7. Unchanged full-gate PASS + actual diff reviewed + zero open finding/unknown → refresh token → run:

   `python3 "$HOME/.agents/skills/he/scripts/plan_state.py" checkpoint --repo <repo> --plan <PLAN> --expect-token <token> --set lifecycle_status=green --set active_slice=none --set "completed_slices=<ordered-comma-list>" --set "next_action=<exact-delivery-action-or-approval-boundary>"`

## Pause

- Material outcome/protected-contract decision → checkpoint exact evidence + one question + `next_action`; reopen only with the matching accepted `$he` reason.
- External dependency/authority → checkpoint owner + condition + exact resume action.
- Before handoff/turn end → checkpoint completed slices + active slice + next action.
