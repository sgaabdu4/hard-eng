# Product — Hard Eng

## Identity
- Product = Hard Eng.
- Promise = align once + build in verified slices + ship the proven artifact.
- Category = evidence-backed engineering workflow for OpenAI Codex.
- Status = alpha.

## Problem
- User problem = engineering agents lose intent or burn time on repeated planning, questions, approvals, and context.
- Failure mode = bureaucracy delays working-code evidence without adding protection.
- Consequence = slow delivery + token waste + review fatigue + hidden regression risk.

## Users

| User | Job | Pain | Desired outcome |
|---|---|---|---|
| Codex operator | deliver repository changes | repeated alignment + context loss | one approval + resumable slices |
| Repository maintainer | preserve product/engineering truth | duplicate owners + shallow proof | current SSOT + regression-safe delivery |

## Value
- Core value = fastest safe route from accepted outcome to verified code.
- Differentiator = one lean Feature Brief + one Ready-to-build approval + Implement ⇄ Verify slices.
- Safety model = critical scrutiny follows risky slices; routine work stays lean.

## Principles
- Direct = default.
- Material intent = ask once in a batch where possible.
- Reversible engineering = agent-owned.
- Working-code evidence outranks speculative process.
- KISS + YAGNI + DRY + SSOT.
- Root cause + blast radius remain mandatory.
- Security + privacy + accessibility + data-loss protections never weaken.
- Deterministic checks precede model judgment.
- Token cost must purchase decision or proof.

## Routes

| Route | Outcome |
|---|---|
| Direct | bounded work reaches focused green proof without lifecycle state |
| Feature Loop | standard capability reaches build through one approved Feature Brief |
| Diagnose | bug/failure reaches reproducible root cause before mutation |
| Critical overlay | affected risky slice receives stronger contract + proof + review |

## Feature Loop
- Brief = Outcome + Non-goals + Material decisions + Acceptance examples + Affected canonical areas + Risk and rollback + First vertical slice.
- Approval = one Ready-to-build decision for accepted brief.
- State = `planning | build-ready | building | green | shipped | cancelled`.
- Build = vertical slice → Implement ⇄ Verify → checkpoint.
- Green = unchanged full gate + exact non-PLAN artifact fingerprint; drift returns to build.
- Discovery = evidence update + affected proof; file/owner/test change ≠ replan.
- Replan = accepted outcome change OR material risk contract change.
- Context reset = alignment/slice boundary; canonical state checkpoint resumes without reapproval.
- Review = actual diff + affected behavior + risk-targeted evidence.
- Ship = separate destructive/external/Git/publish approvals remain explicit.

## Core Capabilities

| Capability | Observable outcome |
|---|---|
| `$he` | selects/resumes exact route + state |
| `$he-plan` | produces one lean approved Feature Brief |
| `$he-build` | converges vertical slices through Implement ⇄ Verify |
| `$he-ship` | delivers the unchanged green artifact through approved boundary |
| `$he-learn` | prevents proven process gaps without delaying safe product work |

## Boundaries
- In scope = OpenAI Codex + repository-local rules/skills/state/docs/checks.
- Non-goals = plugin packaging + cross-harness compatibility + background daemons/eval fleets + zero-risk claims.
- Direct work = contained change + focused proof.
- Feature state = repository `features/<feature-slug>/PLAN.md`.
- Legacy state = explicit one-time v4 converter + byte/mode archive; no active dual workflow.
- Managed skills = pinned vendor owners remain immutable.

## Success

| Outcome | Metric | Target |
|---|---|---|
| Fast alignment | approval rounds before standard build | 1 |
| Useful questions | questions tied to material decision | 100% |
| Stable build | replans caused only by outcome/risk change | 100% |
| Safe delivery | applicable deterministic/protected-boundary gates | 100% PASS |
| Regression control | escaped defect in changed behavior | downward trend |
| Efficient context | repeated context/approval tokens per comparable task | downward trend |
| Working feedback | time from request to first verified slice | downward trend |

## Evidence Owners
- Routing + approval contract = `AGENTS.md` + `skills/he/` + `skills/he-plan/`.
- Build convergence = `skills/he-build/`.
- Delivery = `skills/he-ship/`.
- Learning = `skills/he-learn/`.
- Enforcement = `scripts/check-skill-contracts.py` + `$deterministic-checks`.

## Unknowns
- Baseline token/time/defect data = collect across comparable completed tasks.
