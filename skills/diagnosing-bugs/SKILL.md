---
name: diagnosing-bugs
description: Find reproducible root causes for bugs, flakes, failures, or regressions.
---

# Diagnosing Bugs

## Contract

- Diagnose request = inspect + execute only; source edit/fix requires explicit authority.
- Active impact/data-loss/security risk → preserve evidence + follow project containment/runbook owner first; remote mutation requires approval.
- Root cause = proven mechanism at canonical owner; correlation, stack-frame proximity, and plausible narrative = insufficient.
- Hypothesis = falsifiable prediction + discriminating evidence; no mandatory count.
- Missing reproduction/access → stop with exact proof gap + next action; never guess or manufacture green.

## Route

| State | Load/action | Complete |
|---|---|---|
| Root cause unproven | [diagnose.md](references/diagnose.md) | Mechanism proven, or exact reproduction/access blocker |
| Root cause proven + fix explicitly requested | [fix.md](references/fix.md) | Original proof + regression proof + applicable gates pass |
| Root cause proven + no fix request | Report only | Evidence + blast radius + fix direction returned; source unchanged |

## Evidence Owners

| Need | Route |
|---|---|
| Authorized Sentry runtime evidence | `$sentry` |
| Real UI reproduction | `$e2e` |
| Regression-test design | `$test-quality` |
| Commands + final project gates | `$deterministic-checks` |

- Specialist result = evidence input; this skill owns causal synthesis.

## Report

| Field | Required content |
|---|---|
| Result | `PASS | CONCERNS | FAIL` |
| Reproduction | Command/path + environment + observed red proof |
| Root cause | Owner + mechanism + decisive evidence |
| Eliminated | Rejected hypothesis + counterevidence, or `N/A` when one decisive mechanism required no alternative |
| Blast radius | Callers/data/contracts/UI/tests/config/runtime affected |
| Proof | Original + regression + gates, or exact gap |
| Next | Fix direction or blocker owner/action |
