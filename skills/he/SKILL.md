---
name: he
description: Route explicit lifecycle requests, new durable products or features, and complex or high-risk staged work through one living Feature Brief.
---

# Hard Eng

## Route

- `he` = lifecycle router + state gate; stage work stays with the emitted owner.
- Explicit `plan|resume|status|build|ship|learn` = `he`.
- Cross-boundary work = `he` only when unresolved durable decisions, high-risk change, or staged coordination makes a persistent plan useful.
- New durable product/greenfield repository = lifecycle work; small scope/simplicity never downgrades it; user-named throwaway scratch = direct owner flow.
- Clear bounded UI/layout/style/copy/fix/refactor/test/doc/config = direct owner flow.
- File count + code size + `feature` label + missing `PRODUCT.md|DESIGN.md` ≠ lifecycle eligibility.
- Direct work exposing a material product/UX/architecture choice → pause + confirm lifecycle scope → `he`.
- Existing bug/incident/production triage → direct diagnostic owner; enter `he` only for a newly required material decision.

## State

- SSOT = `features/<feature-slug>/PLAN.md`.
- Format + validation + transitions = `scripts/plan_state.py`.
- One active plan = one accepted outcome; parallel unrelated outcomes = separate plans.
- Decomposed epic = `state_version` v2 (adds `execution_mode=tickets`); v1 plans keep the 11-key format unchanged forever.
- Ticket SSOT = `features/<slug>/tickets/T-<n>.md`; format + validation + transitions = `scripts/ticket_state.py`; full workflow = [tickets.md](references/tickets.md); tracker mirror = [tracker-adapter.md](references/tracker-adapter.md).
- Read-only intent → `inspect`; planning-only PLAN init/edit → current feature-setup receipt (`setup_state.py verify` PASS) + selected checkout + `deterministic-checks` worktree `read` PASS; product/tooling mutation → worktree `write` PASS first.
- Feature setup precedes planning: checkout decision + worktree `write` + gate manifest + memory index = feature-setup receipt PASS before PLAN `init`.
- Planning steps = `plan_state.py record-step` receipts (`code-study`, `research`, `edge-scan`, `decisions`, `slices`, `closing`) in `features/<slug>/receipts/plan-steps.json`; `approve` refuses until all six are current; `inspect` at `build-ready|building` prints the handoff block (`handoff_root|branch|plan|prompt`, or `handoff_ticket_N` + prompt per claimable ticket).
- Planning route cannot be preempted by full-gate repair while the selected checkout remains readable + the feature-setup receipt stays current; record build-entry debt → continue `he-plan`.

```sh
python3 <skill-dir>/scripts/plan_state.py inspect --repo <repo> [--plan <PLAN.md>]
python3 <skill-dir>/scripts/plan_state.py init --repo <repo> --feature-slug <slug>
```

| Inspect result | Route |
|---|---|
| no active plan + eligible work | setup `verify|run` PASS → `init` → `he-plan` (six step receipts → approval → handoff block) |
| one valid plan | script `route_target` |
| multiple active plans | show candidates → user selects exact plan |
| invalid plan | stop + report validator repair |
| explicit action conflicts with state | stop + report valid next action |

- Never overwrite, silently select, recreate, or hand-edit the State block.
- Terminal state content = immutable; exact user-authorized terminal PLAN file cleanup = plan_state.py cleanup + terminal proof + path/hash inventory + recovery note; active/nonterminal removal is forbidden until cleanup writes a validated cancelled state + invalid legacy input requires explicit cancellation.
- Terminal checkpoint = exact slug PLAN + receipts → shared `$GIT_COMMON_DIR/info/exclude` via Git plumbing; tracked paths + other feature assets remain visible; broad patterns + per-worktree Git config forbidden.
- Checkpoint = stale-token-guarded state update; living brief prose may be edited directly via the plan_state.py draft command + exact external candidate + unchanged State block.
- Slice completion + `building → green` = current `deterministic-checks` slice-gate receipt; `inspect` emits `slice_receipt|full_receipt` debt while building.
- Active approved brief + frozen-byte drift = restore approved bytes; `reopen` only for materially changed accepted constraints.

## Setup

- Feature setup = pre-`init` phase owned by `scripts/setup_state.py`; steps = base branch + feature worktree + copied ignored inputs → parallel probes = worktree `write` + gate manifest static validity + codebase memory index.
- Selectable repository + primary checkout → `git fetch origin` → base = `origin/<current>` when already on `main|develop`, else the one existing `origin/main|develop`, else `origin/HEAD`; both exist + not on either → ask once (`--base-branch main|develop`).
- Clean primary → `git worktree add ../<repo>.worktrees/<slug> -b feature/<slug> <base>` automatically (`--feature-slug` required); dirty primary → ask once: `--checkout-choice current|worktree`; existing linked worktree (Codex/Claude/any) → continue there; no `origin` → stay in place; `primary-only` policy → primary always, no branch/worktree/base step.
- Ignored env files in the primary (`.env`, `.env.*`, `*.env`; templates excluded) not yet in `.worktreeinclude` → ask once with `env_candidate_N` (`--include-env <path>`... or `none`) → chosen paths appended to `.worktreeinclude` + staged in the selected checkout + copied private into a linked worktree; freshly created feature branch commits it (`chore: list worktree inputs`), otherwise the feature's first commit carries it.
- `run` = decisions → parallel probes → git-private receipt in the selected checkout; `repository_root` on PASS = the checkout every later command (`init`, `verify`, `plan_state.py`) must use; current receipt short-circuits; `verify` = sub-second receipt check at router entry, `he-plan` entry, resume.
- Exit 0 = PASS; 3 = decisions required, every independent question batched as `choice_N=checkout|base-branch|worktreeinclude` + `choice_N_prompt` → ask them together → rerun with the answers; 4 = failed/invalid (missing/invalid manifest → `gate-migration`; worktree failure → `repair` → rerun; missing slug/base/hook owner → exact error); 5 = memory index behind HEAD → `run` refreshes only the memory probe.
- Memory probe = soft: tool unavailable/refresh incomplete = WARN + planning evidence degrades to direct reads; never blocks.
- Receipt = per checkout `<git-dir>/hard-eng-feature-setup-v1.json`; second feature in the same checkout = zero probes; rerun from the primary for an existing `feature/<slug>` worktree = reuse (verifies inside that worktree, no question); slug = `[a-z0-9][a-z0-9-]*`, never `none`.

```sh
python3 <skill-dir>/scripts/setup_state.py run --repo <repo> --feature-slug <slug> \
  [--checkout-choice current|worktree] [--base-branch main|develop] [--include-env <path>]... [--include-env none]
python3 <skill-dir>/scripts/setup_state.py verify --repo <repo>
```

## Approval Boundary

- `he-plan` obtains one explicit **Ready-to-build** approval for the whole brief.
- Explicit current-prompt autonomous directive + valid execution evidence = Ready-to-build authorization after the complete brief validates; no second approval prompt.
- Standard approval = complete brief shown → user's plain yes (any literal reply) → `plan_state.py approve --approval-reply "<their words>"`; decision answers + pre-brief replies = reject; empty reply fails.
- Approval freezes only Outcome + Non-goals + Material decisions + Acceptance examples + `risk_level` + `critical_overlay`.
- Affected canonical areas + implementation owner/file/test discoveries + rollback mechanics + `deferred`/`blocked_on` rows + slice detail remain living engineering context.
- Engineering-only discovery → update living brief when useful + continue; reapproval forbidden.
- Replan = accepted outcome changes OR material security/privacy/data-loss/irreversible contract changes.

```sh
python3 <skill-dir>/scripts/plan_state.py approve --repo <repo> --plan <PLAN.md> \
  --expect-token <token> --approval-reply "<the user's literal words>" \
  [--allowed-action parallel-subagents]
python3 <skill-dir>/scripts/plan_state.py reopen --repo <repo> --plan <PLAN.md> \
  --expect-token <token> --reason <changed-outcome|material-safety-contract>
python3 <skill-dir>/scripts/plan_state.py checkpoint --repo <repo> --plan <PLAN.md> \
  --expect-token <token> --set <field=value>
```

- Approval records a fingerprint of frozen constraints only; engineering-only edits do not stale it.
- Approval is valid for that brief forever: never bound to a session, a request, or an expiry window; commits and new sessions never require re-approval.
- Reopen resets approval + returns to planning; changed constraints are then edited + reapproved once.
- Critical overlay = only the risky slice + its security/privacy/data/data-loss/irreversibility proof; normal slices stay on the normal route.

## Safety

- Protected action = irreversible destructive loss defined by `AGENTS.md`; recoverable tool access never needs a protected approval.
- Ready-to-build approval authorizes the accepted build; it never authorizes unrequested irreversible destruction.
- Autonomous receipt authorizes only its allowed list; irreversible stop boundaries still follow `AGENTS.md`.
- Exact protected approval (active PLAN) = state target + permanent effect → user's plain yes → `authorize-protected --approval-reply '<their literal reply>'` + `action-digest` over the exact upcoming tool input → one matching call consumes receipt.
- Exact protected approval (direct route, no active PLAN) = state target + permanent effect → user's plain yes → `authorize-protected --plan direct --approval-reply '<their literal reply>'` + `action-digest` over the exact upcoming tool input → one matching call consumes the Git-private receipt; approval reply = caller-asserted, same trust class as the autonomous directive; per `git stash` docs, mistakenly dropped or cleared stash entries cannot be recovered through the normal safety mechanisms, so stash drop/clear stays protected.
- A failed authorized attempt records `authorize-protected` again from the same yes and retries; a different target/effect, or a second successful run, needs a fresh yes.
- Secret exposure + permanent data-loss risk follow `AGENTS.md` stop rules; account/environment mismatch remains a verification failure, not an approval boundary.
- Deterministic validation proves document shape/state only; it never predicts semantic completeness.

## Lifecycle

| `lifecycle_status` | `route_target` |
|---|---|
| `planning` | `he-plan` |
| `build-ready|building` | `he-build` |
| `green` | `he-ship` |
| `shipped|cancelled` | terminal |

- `lifecycle_status=building` + `execution_mode=tickets` → `he-build` ticket mode (per-ticket worktree loop, not the scalar single-slice loop).
- Stage owner checkpoints only `lifecycle_status`, `active_slice`, `completed_slices`, and `next_action`.
- Build owner loop = `Implement ⇄ Verify` until the active vertical slice is green.
- `building → green` = bind current non-lifecycle repository artifact; `he-ship` requires `assert-green` before delivery boundaries.
- Legal flow = `planning → build-ready → building → green → shipped`; `cancelled` = explicit user decision.
- Finding changes only implementation owner/file/test/approach → current owner fixes + verifies.
- Finding changes frozen constraints → `reopen` → `he-plan`.
- Status request = state + open risk + next action; no mutation.

## Continuity

- Explicit `continue until complete|blocker` = one Codex goal for requested lifecycle scope.
- Route transition PASS → checkpoint → inspect → next owner in same turn.
- Pause only for material decision, unapproved irreversible destructive action, or proven invalid state.
- Decision waiting on user action = deliver the exact checklist in that same turn + record `blocked_on` + checkpoint `next_action` → continue every step independent of it; idle whole-plan waiting is forbidden.
- Only the dependent step waits; independent discovery, proof, and slice work continue in parallel.
- Before compaction/turn boundary during explicit continuity → checkpoint current state + next action.
- Slice green checkpoint + stage handoff = required context reset outside explicit continuity; PLAN.md + receipts = complete resume state; resume = fresh context → `inspect` + `setup_state.py verify` → route owner.
