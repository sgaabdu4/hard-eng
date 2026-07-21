# Plan Admission

## Purpose

- Admission = prove accepted design is implementable + failure-complete before `build-ready`.
- User approval = product/decision acceptance; never substitutes for engineering completeness.
- Final build audit = implementation verification; first discovery of a planned owner/state/boundary/scenario = false planning gate.

## Required Evidence

`## Traceability` table header:

`ID | Requirement | Flow/state | Contract/owner | Proof | Telemetry/rollout | Slice`

- Row = `TR-*` + concrete `R-*` + `F-*` + `C-*` + `T-*` + `S-*` references.
- Every accepted requirement/risk + failure-model proof maps forward once; broad labels do not cover multiple unnamed behaviors.

`## Failure Model` table header:

`ID | Boundary/transition | Failure/interrupt | Durable state | Recovery owner | Retry/timeout | Observable proof`

- Row = one `FM-*` crash/failure timing at one `C-*` boundary + traced `T-*` proof.
- Inventory = before call + during/ambiguous call + accepted call/before local persistence + persistence failure + timeout/expiry + duplicate/concurrent + retry exhaustion + process termination + operator recovery as reachable.
- Async/distributed/irreversible/security/privacy/data-risk plan = concrete model; `FM-NA` forbidden.
- Standard plan with no reachable async/external/partial/irreversible boundary = one evidenced `FM-NA` row.
- Every non-terminal durable state = one recovery owner + bounded next action; unowned state = blocker.

`## Plan challenge` table header:

`Perspective | Scope | Result | Evidence`

- Standard = one independent read-only `complete` review.
- Critical = independent read-only `owner-first` + `boundary-first` reviews.
- Reviewer = ephemeral `codex exec` + no mutation/tools + exact PLAN/repository evidence; review is plan-only, never final code audit.
- Evidence = SHA-256 of complete structured result; only clean `PASS` enters the table.
- Finding = cited gap + earliest owning stage + materiality + required correction; same-root repeat → `$repeated-failure-learning` + pause.

## Classification

| Finding changes | Class | Route |
|---|---|---|
| Implementation already contradicted a concrete approved `TR-*`/`FM-*` row | implementation defect | current build owner fix ⇄ affected proof |
| New/changed state, transition, schema, API/event, owner, dependency guarantee, retry/recovery, security/privacy boundary, operational control, or proof family | plan defect | pause build → reopen earliest affected planning stage |
| Same semantic root after one correction | systemic recurrence | `$repeated-failure-learning` → `$he-learn`; no new audit round |

- Unchanged product outcome does not make a plan defect an implementation defect.
- Plan-defect correction updates canonical accepted content + downstream traceability; issue chronology never becomes replacement architecture.
- User reconfirmation = changed product/UX/trade-off/scope only; engineering-only correction still reruns admission + final full-PLAN approval contract.

## Gate

1. Run plan challenges → resolve every material finding at earliest owner.
2. Repeat affected planning stages + consistency; unrelated accepted proof auto-revalidates.
3. Run `python3 "$HOME/.agents/skills/he-plan/scripts/plan_admission.py" --plan <PLAN.md>` → PASS.
4. Present canonical plan for user approval; approval checkpoint independently reruns the validator.

Complete = structured trace + failure model + clean risk-tier challenge + deterministic admission PASS + zero open item.
