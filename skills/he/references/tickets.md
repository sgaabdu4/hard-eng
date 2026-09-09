# Ticket Workflow

## Ownership
- Ticket file `features/<slug>/tickets/T-<n>.md` = script-owned via `ticket_state.py` only; raw writes forbidden, same rule as PLAN.md. Epic v2 (`execution_mode=tickets`) stays quiescent for the whole parallel phase: no agent writes the epic PLAN; live progress reads from `board` only.
- One ticket = one executor; a claimed ticket's worktree + branch is sanctioned creation, not a decision point.

## Claim → Materialize → Build
```sh
python3 <skill-dir>/scripts/ticket_state.py claim --repo <repo> --epic-plan <PLAN.md> --ticket <T-n> --session-id <session>
python3 <skill-dir>/scripts/ticket_state.py claim --repo <repo> --epic-plan <PLAN.md> --next --session-id <session>
```
- Claim: per-ticket flock + whole-file CAS token → dependency gate = every `depends_on` entry `shipped` (merged) only, a green-not-merged dependency is unreachable from a fresh branch → records `claimed_by`/`claimed_at`/`worktree`/`branch` in the ticket state; the only minted receipt is the worktree-local `authorization.json`. `--ticket <T-n>` claims the named ticket; `--next` claims the lowest-n claimable `todo` and reports `result=none` + board when nothing is claimable; a race loser errors — rerun `--next` against the remaining set. Autonomy = the claiming session's own current-prompt directive only, never inherited from the epic or another session.
- Materialize: `git worktree add` on `ticket/<slug>/T-<n>` off the default branch (`origin/HEAD` must resolve; after a manual remote add, run `git remote set-head origin -a` once) → script writes a byte-copy of the v2 PLAN + a copy of `research.json` + a fresh worktree-local `authorization.json` keyed to the epic fingerprint, no expiry; the worktree never gets a `tickets/` mirror. The minted authorization is standard mode; autonomous mode = a fresh re-mint in the worktree from the claiming session's own prompt directive. The `research.json` copy keeps its original freshness windows — stale research re-runs under the existing rule before external-contract work. Worktree `write` PASS required before the first checkpoint sets `status=building`.
- Build: unchanged `he-build` slice loop (Implement ⇄ Verify), scoped to the ticket's own `slices` only; checkpoints go through `ticket_state.py checkpoint`, never `plan_state.py`; slice receipts bind to the worktree's own artifact/HEAD. Every commit moves the worktree HEAD and stales `research.json`; re-run `execution_evidence.py record-research` before the next gate or evidence step.

## Exit + Ship
- Exit: every ticket slice done → full project gate + `slice_gate --full` on the ticket worktree tree + `code-review` of the ticket's actual diff (+ critical overlay when the ticket carries the risky slice) → `status=green`, records `green_artifact`.
- Ship: fetch + rebase onto updated default (stale receipts → gates re-run, the merge-conflict story for free) → `assert-ticket-green` → `publish` PASS → push → PR → per-run CI verify → merge → `status=shipped` + `delivery` recorded → tracker `update-status` + `close-ticket` → `release` the shipped ticket (clears worktree + branch, never forced: the worktree must hold only claim scaffolding and the branch must be merged to the base ref) → executor loops `claim --next`.

## Refresh + Release + Board
- The worktree `authorization.json` never expires; `claim --refresh` re-validates it against the current epic fingerprint and prints `result=refreshed ticket=<id> worktree=<path>`.
- `release` = same session only without force: a claimed ticket returns to `todo`, a building ticket needs `--force-release` and cancels; another session's ticket always needs `--force-release`, an explicit user decision. Release deletes the worktree AND the ticket branch and resets both rows to `none`; claim scaffolding (mirrored PLAN.md + `receipts/`) is expected dirt and never blocks, while any other uncommitted work or branch commits not on the base ref refuse without `--force-release`. A shipped ticket releases without force only: status stays `shipped`, worktree + branch rows clear, and `--force-release` is refused. Claims never auto-expire; `board` shows claim age instead of reclaiming automatically.
- checkpoint `--set status=cancelled --confirm-cancel` cancels `todo` tickets only; claimed or building work routes through `release`; `T-int` is never cancellable — it closes with the epic.
- `board` computes live from the ticket files on every call: status/claimed-by/claim age/next_action for every ticket, with zero epic PLAN write.

## Integration Ticket
- `T-int` is auto-generated at decompose, never supplied; claimable only once every work ticket is `shipped`. Runs on the PRIMARY checkout, pulled to the default branch containing every merged ticket PR.
- Claiming session runs the same Claim → Materialize flow as any other ticket; the freshly minted worktree-local `authorization.json` uses the current epic fingerprint and touches neither the PLAN nor the approval fingerprint.
- Runs the existing Final Pre-ship Gate against the EPIC plan on the integrated tree: full receipt + every acceptance ordinal A-1..A-k re-verified on the integrated tree (never trusted from per-ticket proofs alone) + cross-slice `e2e`.
- `T-int` green → epic checkpoint `building → green` with bulk `completed_slices=S-1..S-n` → epic takes today's unmodified `green → shipped` path.
- At epic Finish, `T-int` is checkpointed `shipped` with `delivery = <repo-url>@<delivered-epic-HEAD>` — same `<url>@<hex>` format work tickets record for their merged PR.

## Orchestrator + Executors
- Orchestrator role = board + dispatch + verification + `T-int` only; it never claims or implements a work ticket.
- Executor context = frozen brief + its own ticket file + its own worktree only; the orchestrator transcript and sibling ticket outputs are never in scope.
- Model tiering is advisory, never a gate: mechanical tickets may run on a cheaper model/effort; the orchestrator and every verification pass stay on the strong model, since a weak driver invalidates every verification above it.

## Mid-Build Plan Changes
- Detail (how, not what) = zero stop: executor updates its own ticket evidence + continues; no epic write, no other ticket notices.
- Additive (more work, same goal) = `decompose --amend`: no approval, because the slice universe sits outside the approval fingerprint; running executors never stall. Amend extends the partition upward or refills cancelled slices, always under a new ticket id; the combined live set must stay a gapless disjoint partition.
- Outcome/risk change = scoped replan: finding goes into the ticket's `next_action`, executor stops checkpointing + posts to board → smallest affected brief section reopens via `he-plan` → one re-approval → the new fingerprint fail-closes every ticket state write + ship instantly → `decompose --reconcile --dry-run` previews survive (byte-identical → claim/status restored) vs cancelled (worktree listed for cleanup) vs shipped (immutable, untouched) → `--reconcile` applies it.

## Failure Routes
- Dead agent → `release` or `--force-release`; board shows claim age. Release deletes the worktree and the ticket branch; re-claim starts fresh.
- Surviving ticket depends on a cancelled ticket → cancel the dependent too (checkpoint for `todo`, `release` for live work) and `--amend` a replacement covering both tickets' slices.
- Epic fingerprint mismatch (a replan landed) → fail-closes every ticket state write + ship instantly; recovery = re-approval then `decompose --reconcile`.
- Claim race loss → flock + byte-level CAS token guarantee the loser errors instead of overwriting; `--next` retries against the remaining claimable set.
