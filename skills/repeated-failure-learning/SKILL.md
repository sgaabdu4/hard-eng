---
name: repeated-failure-learning
description: Prove whether failures share one recurring root cause.
---

# Repeated Failure Learning

## Trigger

- Same root cause or failed approach occurs twice.
- User reports recurrence.
- Unrelated failures != recurrence.
- Attempted fix recurs → prior cause = unproven → return `$diagnosing-bugs`; extending workaround = forbidden.

## Ownership

- Diagnosis = `$diagnosing-bugs`.
- Regression strength = `$test-quality`.
- Gate contract + commands/hooks/CI = `$deterministic-checks`.
- Active Feature Loop → record recurrence evidence → hand packet to `$he-learn`; lifecycle continues.
- Block delivery only when recurrence proves continued work risks security/privacy/accessibility/data integrity/data loss/irreversible action.
- This skill owns recurrence + root-cause evidence only; prevention selection = `$he-learn`.

## Evidence

| Field | Required proof |
|---|---|
| Signature | Stable error/symptom + affected boundary |
| Attempts | Change + result for each comparable attempt |
| Recurrence | Same root cause or failed approach ≥2 times |
| Cause | Root owner + why prior action failed |
| Success | Correcting change + passing proof |
| Exposure | Callers/data/routes/tests/docs/config affected |

## Complete

- Recurrence proven by comparable evidence.
- Root cause + successful correction identified.
- Evidence packet = signature + attempts + cause + correction + exposure.
- Active lifecycle → `$he-learn` packet handed off without routine source pause; otherwise evidence packet reported.

Report = `PASS | CONCERNS | FAIL` → recurrence proof → root cause → correction → exposure → handoff/gap.
