---
name: he
description: Route new features, behavior changes, and persistent PLAN state through Hard Eng plan/resume/build/ship/learn.
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
- State item IDs ⇄ evidence rows = exact; open blocker/issue/unknown row status = `open`.
- Recorded HEAD drift = fresh only when recorded SHA remains ancestor + every committed changed path is the selected `PLAN.md`; output exposes current repository HEAD for checkpointing.
- Plan-stage enum/order = `plan_state.py:PLAN_STAGES`; `$he-plan` executes the selected stage.
- Planning = active `plan_stage`; every prior stage appears once in approved/skipped; current/later stages appear in neither.
- Advance only after current-stage approval or explicit skip; `approval` cannot skip.
- Build-ready = every plan stage accounted + `approval` approved + zero open items + `plan_stage=none`.
- Checkpoint after every material evidence/decision/item/stage change + before every question, handoff, compaction boundary, or turn end.
- Checkpoint = update state + affected plan sections → reread → prove exact next action + UTC time + current Git identity.

## Route

| Intent/state | Target |
|---|---|
| New feature/product-behavior change + no plan | Initialize state → `$he-plan` |
| New feature + active plan | Show active plan → ask continue or create distinct plan; never overwrite |
| `plan` or resume + lifecycle `planning` | `$he-plan` |
| `plan` + post-plan lifecycle | Require explicit reopen + impact confirmation → choose earliest affected `plan_stage`; retain only its approved/skipped prefix → set `planning/plan/in-progress/plan_approved=no` → `$he-plan` |
| `status` | Report state/items/next action only |
| `build` | Require `build-ready` + approval + zero open blockers/issues/unknowns → `$he-build` |
| Build-stage resume | `$he-build` |
| `ship` | Require `green` + accepted evidence → `$he-ship` |
| Ship-stage resume | `$he-ship` |
| `learn` | Require proven process gap → `$he-learn` |
| Learn-stage resume | `$he-learn` |

- Explicit action never bypasses transition gates.
- Missing target skill → stop + report; never emulate it.
- Terminal plan = `shipped|cancelled`; reopen requires explicit user decision + state transition.
