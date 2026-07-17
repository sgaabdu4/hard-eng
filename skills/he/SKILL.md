---
name: he
description: Route explicit lifecycle requests or material product work requiring durable PLAN state.
---

# Hard Eng

## Ownership

- `$he` = sole lifecycle router + state gate; never perform stage work.
- Invocation gate = `AGENTS.md`; direct-eligible work never enters `$he`.
- Root `PRODUCT.md` + `DESIGN.md` = mandatory repository context; creation/content owner = `$he-plan` + `$atomic-ui`.
- `features/<feature-slug>/PLAN.md` = per-feature state SSOT.
- Stage skill = stage execution + checkpoint updates; specialist skill = evidence only.
- Natural lifecycle request or `$he <action>` → inspect state before routing.
- Existing bug/incident/production triage → direct specialist; escalate only when fixing requires a new product decision.

## Eligibility

| Work | Route |
|---|---|
| Explicit `plan|resume|status|build|ship|learn` | `$he` |
| New user capability/cross-boundary product change + unresolved durable decisions/staged coordination | `$he` |
| Clear bounded UI/layout/style/copy/fix/refactor/test/doc/config | Direct specialist flow |

- `feature` wording + code size + file count + missing context docs ≠ lifecycle eligibility.
- Direct task later exposes material product/UX/architecture choice → pause → enter `$he` with user-confirmed scope.

## Repository Context

After eligibility selects `$he`, invoke `$deterministic-checks` repository-context + worktree-readiness branches.

- Status/explanation = `read`; before mutation = `write`; before commit/push = `publish`.
- Always run read-only `plan_state.py inspect` too; route from context/worktree evidence + plan result together.

| Result | Route |
|---|---|
| valid | Continue state inspection |
| invalid + new/material lifecycle + no active plan | Initialize plan → `$he-plan` repository gate creates/validates both files |
| invalid + active planning plan | Show invalid context → confirm earliest affected-stage reopen → `$he-plan` |
| invalid + post-plan lifecycle | Stop → explicit planning reopen required before build/ship |
| invalid + status/read-only intent | Report invalid context + exact repair route; do not mutate |

- User-selected checkout change + fresh approved PLAN + exact task-owned planning/context dirt → [Transfer](#transfer) in either direction; never auto-transfer/baseline-commit/recreate/manual-rebind.
- Other worktree `write|publish` invalid → stop before mutation; route repair through `$he-plan` repository stage.
- `$he` detects only; never drafts context documents or bypasses invalid gates.

## Inspect

Run:

```sh
python3 <skill-dir>/scripts/plan_state.py inspect --repo <repo-root> [--plan <PLAN.md>]
```

| Exit | Meaning | Route |
|---:|---|---|
| 0 | One valid fresh plan | Apply intent + transition gate |
| 2 | No active plan | New feature/behavior → initialize; other lifecycle intent → report none |
| 3 | Multiple active plans | Show candidates → user selects |
| 4 | Invalid state | Exact v3 compatibility → State Migration; otherwise stop + report |
| 5 | Repository/branch/HEAD drift | Stop → inspect impact → reconcile |

- Explicit plan path wins; never select by filename similarity.
- New plan requires confirmed repository + feature slug; initialize only after `inspect` returns `2` or user accepts a distinct plan.

## Initialize

```sh
python3 <skill-dir>/scripts/plan_state.py init --repo <repo-root> --feature-slug <slug> [--plan-id <stable-id>]
```

- Success = exit `0` + canonical v4 `features/<slug>/PLAN.md` + `plan_stage=repository`.
- Existing plan/path, invalid identity, or write/validation failure = exit `4`; never overwrite or hand-build fallback state.

## State Migration

```sh
python3 <skill-dir>/scripts/plan_state.py migrate-state --repo <repo-root> --plan <PLAN.md>
```

- Eligibility = exact state v3 schema + canonical path; every other invalid/current state → reject unchanged.
- Mutation = repository lock + atomic PLAN replace; only `state_version=4` + `approved_plan_digest` added.
- Approved PLAN → digest-bound Git-metadata receipt created before replace; crash/retry remains fail-closed.
- Success = exit `0` + preserved prose/manifests/items/checkpoint state + new checkpoint token → `inspect`.

## Transfer

```sh
python3 <skill-dir>/scripts/plan_state.py transfer --repo <source> --to-repo <linked-worktree> \
  --plan <PLAN.md> --expect-token <token> [--include <exact-task-owned-path>]...
```

- Preflight = distinct roots + same Git common directory + same HEAD + linked destination + fresh source token/state.
- Bundle = PLAN automatically + exact changed regular files only; broad path/glob/directory/symlink/destination dirt = reject.
- Ownership = shared checkpoint/transfer repository lock + source-stale-first write + locked rollback/postconditions + exact crash resume → one fresh writer.
- Success = destination identity checkpointed + destination `inspect` selected + source `inspect` stale + destination `write` PASS.
- Failure = source/destination unchanged + exact error; commit/recreated plan/direct state edit = forbidden.

## State

- Schema + template + validation = `plan_state.py`; never hand-add/drop/rename fields.
- State + items + approval receipt = `checkpoint`; direct mutation = forbidden.
- `artifact_id` = effective non-PLAN content; `snapshot_id` = artifact + staged evidence layer; any drift → stale build.
- Transition legality + lifecycle/plan-stage/item invariants + `route_target` = `plan_state.py`; validate every checkpoint with `inspect`.
- Human stage routing parity = `scripts/check-skill-contracts.py`; `$he-plan` executes only the script-owned current stage.
- Checkpoint after every material evidence/decision/item/stage change + before every question, handoff, compaction boundary, or turn end.

## Checkpoint

1. Planning only → edit accepted plan prose; approved PLAN change → checkpoint replan reset first.
2. Run one atomic checkpoint with token from latest `inspect`:

```sh
python3 <skill-dir>/scripts/plan_state.py checkpoint --repo <repo-root> --plan <PLAN.md> --expect-token <token> \
  [--set key=value] \
  [--add-item <blocker|issue|unknown> <evidence> <impact> <owner> <next-action>] \
  [--update-item <ID> <evidence|impact|owner|next-action> <value>] \
  [--close-item <ID>] \
  [--add-learning <trigger> <source> <evidence> <cause> <owner> <required-proof>] \
  [--resolve-learning <L-ID> 'PASS: <proof>'] \
  [--refresh-learning <L-ID> 'PASS: <current-proof>'] \
  [--transfer-learning <L-ID> <destination-PLAN.md> <destination-L-ID>] \
  [--prune-closed]
```

- Command owns item IDs + open-item fields + repository/branch/HEAD + UTC; learning PASS binds required-proof digest + current snapshot/artifact; `--refresh-learning` re-proves a closed local candidate after drift; `--prune-closed` requires current receipts + zero open candidate.
- `reconcile-head` may normalize committed HEAD/snapshot only when `artifact_id` remains exact.
- `inspect recovery_action=reconcile-build-head` → run `plan_state.py reconcile-build-head --repo <repo> --plan <PLAN> --expect-token <token>`; requires building + current approved PLAN + descendant non-PLAN HEAD → bind exact identity + reset snapshot evidence; changed accepted intent remains Planning rule.
- Stale token/identity, illegal transition, invalid item, or write failure → exit `4` + unchanged file.
- Approval → freeze accepted non-runtime PLAN content in Git-metadata receipt; content/manifest drift invalidates Build/Ship.
- Success → persist candidate once + emit new token + exact `route_target`; run `inspect` before next mutation.

Build slice PASS → atomic drift reconciliation + contiguous-prefix advance:

```sh
python3 <skill-dir>/scripts/plan_state.py complete-slice --repo <repo-root> --plan <PLAN.md> --expect-token <token>
```

- Command owns `completed_slices + active_slice + next_action`; manual slice-transition `--set` = forbidden.

## Route

| Intent/state | Target |
|---|---|
| Eligible material product change + no plan | Validate repository context → initialize state → `$he-plan` |
| New feature + active plan | Show active plan → ask continue or create distinct plan; never overwrite |
| Active plan + resume/build/ship | Use script-emitted `route_target`; explicit action mismatch → stop + report |
| Explicit `learn` + active plan | Keep lifecycle unchanged → `$he-learn` overlay; required mutation follows current stage owner |
| `plan` + post-plan lifecycle | Require explicit reopen + impact confirmation → choose earliest affected `plan_stage` → apply script-valid reopen → validate → `$he-plan` |
| `status` | Report state/items/next action only |

- Explicit action never bypasses transition gates.
- Missing target skill → stop + report; never emulate it.
- Terminal plan = `shipped|cancelled`; reopen requires explicit user decision + state transition.

## Continuity

- Explicit `continue until complete|blocker` or equivalent → create/maintain one Codex goal for requested lifecycle scope; complete only at terminal scope.
- Progress = material stage/slice/finding change OR ≥60s heartbeat; ≤2 terse lines; accepted intent/test-list restatement + command-by-command narration = forbidden.
- Incomplete slice/work + elapsed turn/context compaction/token/tool budget → checkpoint PLAN + goal → auto-continue; `CONCERNS`/final answer/`continue?` = forbidden.
- Stage `PASS` → atomic checkpoint → inspect emitted `route_target` → invoke target in same turn.
- Intermediate PASS = commentary only; final answer or “continue?” prompt = forbidden.
- Stop = `CONCERNS|FAIL` + material user decision + explicit requested scope end + approval/external wait boundary.
- `build-ready` + implementation in requested scope → `$he-build`; `green` + delivery authority present → `$he-ship`.
