# Product Context

## Ownership

- `<repo-root>/PRODUCT.md` = repository product SSOT; every Git repository requires exactly one.
- `PLAN.md` = feature delta; cite `PRODUCT.md`, never copy stable product truth.
- Code/docs/history = current-state evidence; user approval = intended product truth.
- Missing/stale/contradictory `PRODUCT.md` → research + `$question-me` → replace accepted truth before feature-stage completion.

## Structure

| Section | Required truth |
|---|---|
| `Identity` | product + promise + category/status |
| `Problem` | user problem + evidence + consequence |
| `Users` | user + job + context + pain + outcome |
| `Value` | core value + differentiator + why now |
| `Principles` | durable decision guardrails |
| `Core capabilities` | stable capability + observable outcome + status |
| `Boundaries` | scope + non-goals |
| `Success` | outcome + metric + baseline + target + evidence owner |
| `Constraints` | business + legal/security/privacy + platform/operations |
| `Evidence` | source path/URL + revision/date |
| `Unknowns` | unknown + impact + next proof, or `none` |

## Route

1. Read existing `PRODUCT.md` + repository evidence → classify `Verified | Inferred | Unknown`.
2. Missing/invalid/drift → research users/current behavior/history + ask only intent evidence cannot prove.
3. Draft current accepted truth only → show material delta → obtain explicit approval.
4. Write root `PRODUCT.md` → remove duplicate product owners → rerun `$deterministic-checks` repository-context branch.
5. Record path + evidence revision + feature delta in `PLAN.md`.

## Reject

- README copy + feature plan + architecture + task backlog + temporary roadmap + unsupported positioning.
- Placeholder/template text + inferred intent recorded as accepted + duplicate root/nested product owners.

## Complete

- Root file exists + required structure valid + evidence cited + intended truth approved.
- Feature outcome/scope/non-goals/terminology do not contradict `PRODUCT.md`.
