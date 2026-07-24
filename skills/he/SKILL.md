---
name: he
description: Route explicit lifecycle requests or genuinely complex or high-risk staged work through one living Feature Brief.
---

# Hard Eng

## Route

- `$he` = lifecycle router + state gate; stage work stays with the emitted owner.
- Explicit `plan|resume|status|build|ship|learn|migrate-v4` = `$he`.
- Cross-boundary work = `$he` only when unresolved durable decisions, high-risk change, or staged coordination makes a persistent plan useful.
- Clear bounded UI/layout/style/copy/fix/refactor/test/doc/config = direct owner flow.
- File count + code size + `feature` label + missing `PRODUCT.md|DESIGN.md` ≠ lifecycle eligibility.
- Direct work exposing a material product/UX/architecture choice → pause + confirm lifecycle scope → `$he`.
- Existing bug/incident/production triage → direct diagnostic owner; enter `$he` only for a newly required material decision.

## State

- SSOT = `features/<feature-slug>/PLAN.md`.
- Format + validation + transitions = `scripts/plan_state.py`.
- One active plan = one accepted outcome; parallel unrelated outcomes = separate plans.
- Read-only intent → `inspect`; mutation → `$deterministic-checks` worktree `write` PASS first.

```sh
python3 <skill-dir>/scripts/plan_state.py inspect --repo <repo> [--plan <PLAN.md>]
python3 <skill-dir>/scripts/plan_state.py init --repo <repo> --feature-slug <slug>
```

| Inspect result | Route |
|---|---|
| no active plan + eligible work | `init` → `$he-plan` |
| one valid plan | script `route_target` |
| multiple active plans | show candidates → user selects exact plan |
| invalid plan | stop + report validator repair |
| explicit action conflicts with state | stop + report valid next action |

- Never overwrite, silently select, recreate, or hand-edit the State block.
- Checkpoint = stale-token-guarded state update; living brief prose may be edited directly.
- Active approved brief + frozen-byte drift = restore approved bytes; `reopen` only for materially changed accepted constraints.

## Approval Boundary

- `$he-plan` obtains one explicit **Ready-to-build** approval for the whole brief.
- Approval freezes only Outcome + Non-goals + Material decisions + Acceptance examples + `risk_level` + `critical_overlay`.
- Affected canonical areas + implementation owner/file/test discoveries + rollback mechanics + slice detail remain living engineering context.
- Engineering-only discovery → update living brief when useful + continue; reapproval forbidden.
- Replan = accepted outcome changes OR material security/privacy/data-loss/irreversible contract changes.

```sh
python3 <skill-dir>/scripts/plan_state.py approve --repo <repo> --plan <PLAN.md> \
  --expect-token <token>
python3 <skill-dir>/scripts/plan_state.py reopen --repo <repo> --plan <PLAN.md> \
  --expect-token <token> --reason <changed-outcome|material-safety-contract>
python3 <skill-dir>/scripts/plan_state.py checkpoint --repo <repo> --plan <PLAN.md> \
  --expect-token <token> --set <field=value>
```

- Approval records a fingerprint of frozen constraints only; engineering-only edits do not stale it.
- Reopen resets approval + returns to planning; changed constraints are then edited + reapproved once.
- Critical overlay = only the risky slice + its security/privacy/data/data-loss/irreversibility proof; normal slices stay on the normal route.

## Legacy v4

- Legacy v4 detected → load [legacy-v4.md](references/legacy-v4.md).
- `inspect` never auto-migrates.

## Safety

- Exact approval boundaries remain separate for destructive action, external write, commit, push, merge, and publish.
- Generic lifecycle approval never authorizes those actions.
- Secret exposure + external account/environment mismatch + data-loss risk follow `AGENTS.md` stop rules.
- Deterministic validation proves document shape/state only; it never predicts semantic completeness.

## Lifecycle

| `lifecycle_status` | `route_target` |
|---|---|
| `planning` | `$he-plan` |
| `build-ready|building` | `$he-build` |
| `green` | `$he-ship` |
| `shipped|cancelled` | terminal |

- Stage owner checkpoints only `lifecycle_status`, `active_slice`, `completed_slices`, and `next_action`.
- Build owner loop = `Implement ⇄ Verify` until the active vertical slice is green.
- `building → green` = bind current non-lifecycle repository artifact; `$he-ship` requires `assert-green` before delivery boundaries.
- Legal flow = `planning → build-ready → building → green → shipped`; `cancelled` = explicit user decision.
- Finding changes only implementation owner/file/test/approach → current owner fixes + verifies.
- Finding changes frozen constraints → `reopen` → `$he-plan`.
- Status request = state + open risk + next action; no mutation.

## Continuity

- Explicit `continue until complete|blocker` = one Codex goal for requested lifecycle scope.
- Route transition PASS → checkpoint → inspect → next owner in same turn.
- Pause only for material decision, exact external approval boundary, or proven invalid state.
- Before compaction/turn boundary during explicit continuity → checkpoint current state + next action.
