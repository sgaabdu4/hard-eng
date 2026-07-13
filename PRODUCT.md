# Product — Hard Eng

## Identity

- Product = Hard Eng.
- Promise = Plan, build in an Implement ⇄ Verify loop, ship, and learn when evidence demands it.
- Category = stateful engineering workflow for OpenAI Codex.
- Status = alpha rebuild.

## Problem

- User problem = material software work loses intent, evidence, state, or verification across long agent sessions.
- Evidence = `README.md` + `AGENTS.md` + lifecycle skills at revision `20b8c38849b58f86e627c852e7c034d9da8eb483`.
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
| `$he-build` | vertical slices move through Implement ⇄ Verify | pending rebuild |
| `$he-ship` | proven change delivered through repository release contract | pending rebuild |
| `$he-learn` | proven repeated process gap becomes durable prevention | pending rebuild |

## Boundaries

- In scope = OpenAI Codex + repository-local skills/state/docs/checks.
- Non-goals = plugin packaging + Claude/Pi compatibility + Treehouse + no-mistakes dependency + hidden autonomous daemons/evals.
- Direct route = small clear fix + read-only audit + existing incident without new product decision.

## Success

| Outcome | Metric | Baseline | Target | Evidence owner |
|---|---|---|---|---|
| Durable lifecycle state | valid resume after compaction/new task | contract fixtures | 100% valid active plans | `plan_state.py` |
| Safe plan/build boundary | build-ready with missing stage/context/open item | contract fixtures | 0 accepted | `check-skill-contracts.py` |
| Verified delivery | completed slice without required proof | unknown until `$he-build` | 0 accepted | future `$he-build` gate |
| Efficient workflow | tokens spent on duplicated process/context | unknown | downward trend per comparable task | future usage evidence |

## Constraints

- Runtime = OpenAI Codex only.
- Context = Codebase Memory CLI + bounded native verification; MCP transport forbidden for Codebase Memory.
- State = repository `features/<feature-slug>/PLAN.md`.
- Mutation = explicit approvals + full migration + no compatibility residue.
- Skills = canonical repository `skills/`; managed lock owners remain immutable.

## Evidence

- `README.md` @ `20b8c38849b58f86e627c852e7c034d9da8eb483`.
- `AGENTS.md` @ `20b8c38849b58f86e627c852e7c034d9da8eb483`.
- `AGENTS.override.md` @ `20b8c38849b58f86e627c852e7c034d9da8eb483`.
- `skills/he/` + `skills/he-plan/` @ `20b8c38849b58f86e627c852e7c034d9da8eb483`.

## Unknowns

| Unknown | Impact | Next proof |
|---|---|---|
| Build/ship stage contract | lifecycle incomplete | design + approve `$he-build`, then `$he-ship` |
| Comparable token baseline | efficiency target lacks baseline | collect model/task/token evidence after full lifecycle exists |
