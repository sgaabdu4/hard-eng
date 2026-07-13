---
name: he
description: Route new features, intentional product decisions, and persistent PLAN state through Hard Eng lifecycle.
---

# Hard Eng

## Ownership

- `$he` = sole lifecycle router + state gate; never perform stage work.
- Root `PRODUCT.md` + `DESIGN.md` = mandatory repository context; creation/content owner = `$he-plan` + `$atomic-ui`.
- `features/<feature-slug>/PLAN.md` = per-feature state SSOT.
- Stage skill = stage execution + checkpoint updates; specialist skill = evidence only.
- Natural lifecycle request or `$he <action>` → inspect state before routing.
- Existing bug/incident/production triage → direct specialist; escalate only when fixing requires a new product decision.

## Repository Context

Invoke `$deterministic-checks` repository-context + worktree-readiness branches before lifecycle routing.

- Status/explanation = `read`; before mutation = `write`; before commit/push = `publish`.
- Always run read-only `plan_state.py inspect` too; route from context/worktree evidence + plan result together.

| Result | Route |
|---|---|
| valid | Continue state inspection |
| invalid + new/material lifecycle + no active plan | Initialize plan → `$he-plan` repository gate creates/validates both files |
| invalid + active planning plan | Show invalid context → confirm earliest affected-stage reopen → `$he-plan` |
| invalid + post-plan lifecycle | Stop → explicit planning reopen required before build/ship |
| invalid + status/read-only intent | Report invalid context + exact repair route; do not mutate |

- Dirty primary + fresh approved PLAN + exact task-owned planning/context dirt → [Transfer](#transfer); never baseline-commit/recreate/manual-rebind.
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
| 4 | Invalid state | Stop → repair with user confirmation |
| 5 | Repository/branch/HEAD drift | Stop → inspect impact → reconcile |

- Explicit plan path wins; never select by filename similarity.
- New plan requires confirmed repository + feature slug; initialize only after `inspect` returns `2` or user accepts a distinct plan.

## Initialize

```sh
python3 <skill-dir>/scripts/plan_state.py init --repo <repo-root> --feature-slug <slug> [--plan-id <stable-id>]
```

- Success = exit `0` + canonical v3 `features/<slug>/PLAN.md` + `plan_stage=repository`.
- Existing plan/path, invalid identity, or write/validation failure = exit `4`; never overwrite or hand-build fallback state.

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
- State fields + active-item rows = `checkpoint`; direct mutation = forbidden.
- `artifact_id` = effective non-PLAN content; `snapshot_id` = artifact + staged evidence layer; any drift → stale build.
- Transition legality + lifecycle/plan-stage/item invariants + `route_target` = `plan_state.py`; validate every checkpoint with `inspect`.
- Human stage routing parity = `scripts/check-skill-contracts.py`; `$he-plan` executes only the script-owned current stage.
- Checkpoint after every material evidence/decision/item/stage change + before every question, handoff, compaction boundary, or turn end.

## Checkpoint

1. Edit accepted plan prose only.
2. Run one atomic checkpoint with token from latest `inspect`:

```sh
python3 <skill-dir>/scripts/plan_state.py checkpoint --repo <repo-root> --plan <PLAN.md> --expect-token <token> \
  [--set key=value] \
  [--add-item <blocker|issue|unknown> <evidence> <impact> <owner> <next-action>] \
  [--update-item <ID> <evidence|impact|owner|next-action> <value>] \
  [--close-item <ID>]
```

- Command owns item IDs + open-item fields + repository/branch/HEAD + UTC; slices completion sets `slice_count`; approval verifies it.
- Commit adoption may normalize `snapshot_id` only when `artifact_id` remains exact.
- Stale token/identity, illegal transition, invalid item, or write failure → exit `4` + unchanged file.
- Success → persist candidate once + emit new token + exact `route_target`; run `inspect` before next mutation.

## Route

| Intent/state | Target |
|---|---|
| New feature/product-behavior change + no plan | Validate repository context → initialize state → `$he-plan` |
| New feature + active plan | Show active plan → ask continue or create distinct plan; never overwrite |
| Active plan + resume/build/ship/learn | Use script-emitted `route_target`; explicit action mismatch → stop + report |
| `plan` + post-plan lifecycle | Require explicit reopen + impact confirmation → choose earliest affected `plan_stage` → apply script-valid reopen → validate → `$he-plan` |
| `status` | Report state/items/next action only |

- Explicit action never bypasses transition gates.
- Missing target skill → stop + report; never emulate it.
- Terminal plan = `shipped|cancelled`; reopen requires explicit user decision + state transition.
