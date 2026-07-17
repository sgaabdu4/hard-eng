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
- Active Hard Eng lifecycle → record recurrence evidence → hand candidate to `$he-learn`; lifecycle stays unchanged.
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
- Active lifecycle → `$he-learn` candidate handed off; otherwise evidence packet reported.

Report = `PASS | CONCERNS | FAIL` → recurrence proof → root cause → correction → exposure → handoff/gap.
