---
name: he
description: Route new features, intentional product decisions, and persistent PLAN state through Hard Eng lifecycle.
---

# Hard Eng

## Ownership

- `$he` = sole lifecycle router + state gate; never perform stage work.
- `features/<feature-slug>/PLAN.md` = per-feature state SSOT.
- Stage skill = stage execution + checkpoint updates; specialist skill = evidence only.
- Natural lifecycle request or `$he <action>` → inspect state before routing.
- Existing bug/incident/production triage → direct specialist; escalate only when fixing requires a new product decision.

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

- Success = exit `0` + canonical v2 `features/<slug>/PLAN.md` + `plan_stage=repository`.
- Existing plan/path, invalid identity, or write/validation failure = exit `4`; never overwrite or hand-build fallback state.

## State

- Schema + template + validation = `plan_state.py`; never hand-add/drop/rename fields.
- Active-item schema = script-owned; stage skills update values/rows only.
- Transition legality + lifecycle/plan-stage/item invariants + `route_target` = `plan_state.py`; validate every checkpoint with `inspect`.
- Human stage routing parity = `scripts/check-skill-contracts.py`; `$he-plan` executes only the script-owned current stage.
- Checkpoint after every material evidence/decision/item/stage change + before every question, handoff, compaction boundary, or turn end.
- Checkpoint = update state + affected plan sections → reread → prove exact next action + UTC time + current Git identity.

## Route

| Intent/state | Target |
|---|---|
| New feature/product-behavior change + no plan | Initialize state → `$he-plan` |
| New feature + active plan | Show active plan → ask continue or create distinct plan; never overwrite |
| Active plan + resume/build/ship/learn | Use script-emitted `route_target`; explicit action mismatch → stop + report |
| `plan` + post-plan lifecycle | Require explicit reopen + impact confirmation → choose earliest affected `plan_stage` → apply script-valid reopen → validate → `$he-plan` |
| `status` | Report state/items/next action only |

- Explicit action never bypasses transition gates.
- Missing target skill → stop + report; never emulate it.
- Terminal plan = `shipped|cancelled`; reopen requires explicit user decision + state transition.
