---
name: he-build
description: Execute an approved PLAN one demonstrable vertical slice at a time until the actual implementation is green.
---

# Hard Eng Build

## Contract

- Input = `he` route + approved PLAN Feature Brief + Ready-to-build approval + `lifecycle_status=build-ready|building` + repository `write` PASS.
- Output = demonstrated slices + four build records per slice (`edges` `green` `review` `verify`) + one successful full pre-ship gate + `full` verify record + mutation receipt + closing walkthrough answer + generated `BUILD.md` + exact local `green` snapshot.
- Owner = Implement ⇄ Verify loop + actual diff review + affected behavior proof + build findings.
- Publish/rebase/commit/push/PR/CI = `he-ship`; forbidden here.
- Decomposed epic ticket = this same contract, scoped to the ticket's own slices + worktree; entry/exit + integration steps = workflow.md `Ticket Loop` / `Ticket Integration`.
- Load [workflow.md](references/workflow.md) before mutation or resume.

## Ownership

| Evidence | Owner |
|---|---|
| Behavior/RED/GREEN/assertion quality | `test-quality` |
| Commands/analyzers/scanners/hooks | `deterministic-checks` |
| Actual implementation diff | `code-review` |
| Auth/security/privacy/data boundaries | `security-review` |
| Data-loss/irreversible/schema/recovery boundary | `code-review` + applicable domain/test/runtime owner |
| UI owner/tokens/components/a11y | `atomic-ui` + stack skill |
| Real browser/device behavior | `e2e` |
| Repeated implementation root | `repeated-failure-learning` |
| Proven process gap | `he-learn` |

## Invariants

- Work unit = one active independently demonstrable vertical slice.
- Working instruction ledger = accepted brief + every later user/delegated outcome, constraint, example, exclusion, and correction; later guidance supersedes only exact conflicts.
- Before each mutation/resume = reconcile ledger + current messages; material outcome/risk delta → reopen; unchanged additions → implement + prove without reapproval.
- Gate preflight precedes first product mutation + re-verifies the feature-setup receipt/manifest; `deterministic-checks` `gate-migration` pauses the slice without resetting PLAN state.
- Build order = failed `write`/setup → smallest safety repair + focused proof + rerun `write` → complete accepted persistence/API/backend/UI path → targeted proof → slice/full gates; unrelated tooling/reference/receipt debt waits unless continuation is unsafe, corrupting, or unverifiable.
- Loop = reproduce/RED where applicable → canonical-owner change + connected callers/schema/routes → targeted GREEN → SSOT/DRY/YAGNI refactor → actual-diff review → relevant E2E/security proof.
- One active slice only; slice completion requires observable behavior, not path/task completion.
- Slice completion + `building → green` = current `deterministic-checks` slice-gate receipt on the final tree; checkpoint rejects missing/stale/uncovered proof.
- Build records = `plan_state.py record-build` per slice: `edges` (every edge case → success test + failure test) → `green` (exact passing command) → `review` (fresh reviewer on the generated packet, findings ledger, ≤3 rounds, no open finding) → `verify` (independent verifier, faked outside hosts, before/after evidence, edge names ⊆ edges); every record binds to the exact tree and goes stale on change; the slice gate refuses a slice missing any record when enforcement is configured.
- Reviewer = fresh subagent reading only `receipts/<S-ID>-review-<k>.txt`; verifier = separate subagent reading only `receipts/<S-ID>-verify.txt`; the builder never records its own opinion as either.
- Mutation receipt = `plan_state.py record-mutation` per runner over every source file changed since the approval base, recorded on the green tree; `he-ship` `assert-green` refuses without it.
- Closing question = after the full gate, ask once: walkthrough video yes|no → `checkpoint --set walkthrough=yes|no`; `yes` requires a decodable video in the `full` verify record; the `green` checkpoint refuses a `pending` answer, writes `features/<slug>/BUILD.md`, and `inspect` prints `handoff=ship`.
- Build-ready entry = preserve completed slices + select first remaining slice; progress reset = forbidden.
- Standard work = one actual-diff review + scoped re-review only for accepted findings.
- Critical/risky slice = standard review + targeted independent review by every applicable protected-boundary owner; whole-feature ceremony is forbidden merely because one slice is risky.
- Implementation finding = verify → root fix in current loop → affected proof → scoped re-review.
- Planning reopens only when evidence changes an accepted frozen constraint (outcome + non-goals + material decisions incl. `ux_reference` + acceptance) OR adds/changes a material security/privacy/data-loss/irreversible contract.
- Caller/path/schema/test discovery inside accepted outcome = implementation work; planning reapproval is forbidden.
- Candidate patches + path manifests + patch/hash admission + repeated final LLM audits = forbidden.
- Blocked-external dependency = `he` Continuity rule at slice scope; continue every independent step of the active slice; guessing the blocked answer is forbidden.
- Learning = record verified `he-learn` trigger + continue; pause only when continued work risks a protected boundary.
- Security/trust/privacy/accessibility/schema/data-loss protections + rollback/observability = preserved.
- Checkpoint after slice/status/material finding change + before pause/handoff/turn end.
- Slice green + checkpoint = default context reset point; carrying prior-slice raw logs/media/evidence bytes forward = forbidden; PLAN.md + receipts = resume state.

## Complete

- Every accepted slice = implemented + demonstrated.
- Every instruction-ledger item = proven, explicitly superseded, `N/A`, or exact blocker.
- Actual diff = reviewed; accepted findings = closed by affected proof + scoped re-review.
- Applicable risky boundary + E2E evidence = PASS.
- Docs/context = accepted current behavior.
- One successful full pre-ship gate + `full` verify record + mutation receipt = current exact local snapshot.
- Closing walkthrough answer recorded; `BUILD.md` generated; `inspect` prints `handoff=ship`.
- Blocker/unknown count = zero.
- `he` checkpoint = `lifecycle_status=green`; authorized delivery → `he-ship`.
