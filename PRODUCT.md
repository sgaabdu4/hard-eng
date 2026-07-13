# Product — Hard Eng

## Identity

- Product = Hard Eng.
- Promise = Plan, build in an Implement ⇄ Verify loop, ship, and learn when evidence demands it.
- Category = stateful engineering workflow for OpenAI Codex.
- Status = alpha rebuild.

## Problem

- User problem = material software work loses intent, evidence, state, or verification across long agent sessions.
- Evidence = current `README.md` + `AGENTS.md` + lifecycle skills + active PLAN proof.
- Consequence = premature implementation + repeated questions + hidden gaps + unsafe handoff + unnecessary token burn.

## Users

| User | Job | Context | Pain | Desired outcome |
|---|---|---|---|---|
| Codex operator | Deliver reliable repository changes | Long/compacted/new sessions | lost state + unclear gates | resumable evidence-backed delivery |
| Repository maintainer | Preserve product/engineering truth | Multiple features + contributors | duplicate owners + drift | one current owner + deterministic proof |

## Value

- Core value = one lifecycle entrypoint + persistent per-feature state + explicit approval boundaries.
- Differentiator = planning evidence + user decisions + implementation/verification loop + deterministic gates share one stateful flow.
- Why now = agent capability rises faster than repository context + verification discipline.

## Principles

- Evidence before assumption.
- Ask when intent cannot be proven.
- KISS + YAGNI + DRY + SSOT; root cause + blast radius remain mandatory.
- Implement ⇄ Verify until evidence is green.
- Specialists provide evidence; lifecycle state has one owner.
- Deterministic checks before model judgment.
- Token cost must purchase decision or proof.

## Core capabilities

| Capability | Observable outcome | Status |
|---|---|---|
| `$he` router | fresh PLAN selected + validated + exact stage emitted | alpha implemented |
| `$he-plan` | ordered evidence/decision stages → explicit build-ready approval | alpha implemented |
| `$he-build` | exact-snapshot slices converge through Implement ⇄ Verify + runtime evidence | alpha implemented |
| `$he-ship` | exact green artifact survives sync, publish gates, Git delivery, and CI | alpha implemented |
| `$he-learn` | proven repeated process gap becomes durable prevention | pending rebuild |

## Boundaries

- In scope = OpenAI Codex + repository-local skills/state/docs/checks.
- Non-goals = plugin packaging + Claude/Pi compatibility + Treehouse + no-mistakes dependency + background autonomous daemons/eval fleets.
- Direct route = small clear fix + read-only audit + existing incident without new product decision.

## Success

| Outcome | Metric | Baseline | Target | Evidence owner |
|---|---|---|---|---|
| Durable lifecycle state | valid resume after compaction/new task | contract fixtures | 100% valid active plans | `plan_state.py` |
| Safe plan/build boundary | build-ready with missing stage/context/open item | contract fixtures | 0 accepted | `check-skill-contracts.py` |
| Verified delivery | completed slice without required proof | contract fixtures | 0 accepted | `$he-build` |
| Efficient workflow | tokens spent on duplicated process/context | unknown | downward trend per comparable task | future usage evidence |

## Constraints

- Runtime = OpenAI Codex only.
- Context = Codebase Memory CLI + bounded native verification; MCP transport forbidden for Codebase Memory.
- State = repository `features/<feature-slug>/PLAN.md`.
- Mutation = explicit approvals + full migration + no compatibility residue.
- Workspace = `$deterministic-checks` worktree contract + explicit ignored inputs + reproducible setup/smoke proof.
- Skills = canonical repository `skills/`; managed lock owners remain immutable.

## Evidence

- Router + plan = `skills/he/` + `skills/he-plan/`.
- Build convergence = `skills/he-build/` + `features/he-build/PLAN.md`.
- Delivery = `skills/he-ship/` + commit-snapshot adoption in `skills/he/scripts/`.
- Enforcement = `AGENTS.md` + `scripts/check-skill-contracts.py`.

## Unknowns

| Unknown | Impact | Next proof |
|---|---|---|
| Comparable token baseline | efficiency target lacks baseline | collect model/task/token evidence after full lifecycle exists |
