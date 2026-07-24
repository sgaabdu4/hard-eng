---
name: he-plan
description: Produce and approve one lean living Feature Brief after $he selects lifecycle work.
---

# Hard Eng Plan

## Contract

- Input = `$he`-selected valid `PLAN.md` with `lifecycle_status=planning`.
- Output = one Ready-to-build brief OR one material decision question.
- Owner = accepted current state in `PLAN.md`; planning history + rejected alternatives stay out.
- Production code/config mutation = forbidden.
- Load [feature-brief.md](references/feature-brief.md) for workflow + template + field meaning.

- No serial planning stages, trace graph, exact path manifest, semantic-completeness prediction, or repeated plan challenge.
- Research + `$atomic-ui` + `$codebase-design` + `$test-quality` = evidence specialists only when the brief needs them.
- External contract/current vendor fact → `$research` PASS before acceptance.
- Desired-state uncertainty → reference workflow `$question-me` branch.

## Brief Gate

| Section | Ready evidence |
|---|---|
| Outcome | one observable user/system result |
| Non-goals | explicit boundary |
| Material decisions | accepted constraints + unresolved material choice = none |
| Acceptance examples | concrete Given/When/Then or equivalent examples |
| Affected canonical areas | known owner surfaces; path precision optional |
| Risk and rollback | `risk_level`, scoped `critical_overlay`, recovery route |
| First vertical slice | smallest end-to-end behavior + focused proof |

- Unknown implementation owner/file/test = discover during build + update brief if useful.
- Such discoveries never trigger replan/reapproval.
- `risk_level=critical` only for payment/auth/security/privacy/destructive-data/irreversibility or a material unresolved safety uncertainty.
- Critical overlay = named risky slice + boundary owner + failure/recovery/rollback + negative proof; it does not expand the whole lifecycle.
- Validator checks shape, enums, state, placeholders, and frozen-constraint fingerprint only.

## Change Route

| Finding | Route |
|---|---|
| owner/file/test/internal approach changes | living brief update → current owner continues |
| accepted outcome/non-goal/material decision/acceptance changes | `$he reopen --reason changed-outcome` |
| material security/privacy/data-loss/irreversible contract changes | `$he reopen --reason material-safety-contract` |
| implementation contradicts accepted brief | implementation defect → fix + focused proof |

- Reopen only the brief; unchanged accepted constraints need no repeated review.
- Ready-to-build approval freezes outcome/material constraints, not implementation detail.
- Exact destructive/external/Git/publish approvals remain separate.
- Legacy v4 input → `$he migrate-v4`; then plan from the migrated lean brief.

## Completion

- `validate` PASS + no material unknown + explicit Ready-to-build yes = approve.
- Approval failure = remain planning + report exact validator issue.
- Approval PASS = commentary checkpoint + same-turn route to `$he-build`, unless user requested plan-only.
