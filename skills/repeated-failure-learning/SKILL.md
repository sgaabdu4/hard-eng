---
name: repeated-failure-learning
description: Turn a repeated failure or failed approach into durable prevention.
---

# Repeated Failure Learning

## Trigger

- Same root cause or failed approach occurs twice.
- User reports recurrence.
- Unrelated failures != recurrence.

## Ownership

- Diagnosis = `$diagnosing-bugs`.
- Regression strength = `$test-quality`.
- Gate contract + commands/hooks/CI = `$deterministic-checks`.
- Active Hard Eng lifecycle → record evidence in `PLAN.md` → route lifecycle learning through `$he` with `learn` intent.
- This skill owns recurrence evidence + prevention proposal; it never silently rewrites global rules/skills.

## Evidence

| Field | Required proof |
|---|---|
| Signature | Stable error/symptom + affected boundary |
| Attempts | Change + result for each comparable attempt |
| Recurrence | Same root cause or failed approach ≥2 times |
| Cause | Root owner + why prior action failed |
| Success | Correcting change + passing proof |
| Exposure | Callers/data/routes/tests/docs/config affected |

## Prevention

| Cause | Durable response |
|---|---|
| Preventable | Choose narrowest: invariant/schema/type; regression test; scanner/lint; hook/CI |
| Not fully preventable | Choose narrowest: telemetry/alert; containment; rollback/recovery; runbook |

- Reuse existing SSOT owner; prevent the failure class, not one literal message/path.
- Prose-only lesson = last resort when behavior cannot be enforced or impact reduced.
- Active `PLAN.md` → record blocker/issue + evidence + owner + next proof + prevention status.
- Mutation outside authorized scope → propose exact owner/change/proof; do not apply.

## Complete

- Recurrence proven by comparable evidence.
- Root cause + successful correction identified.
- Narrowest durable owner + prevention selected.
- Authorized change applied + proven; otherwise exact proposal reported.

Report = `PASS | CONCERNS | FAIL` → recurrence proof → root cause → prevention → owner → validation/gap.
