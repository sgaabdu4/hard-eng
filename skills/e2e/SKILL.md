---
name: e2e
description: Prove browser/device behavior and visual evidence.
---

# E2E

## Contract

- Input = accepted behavior + runnable environment + target evidence mode.
- Evidence classes = automated assertions + persisted state + deployment + visual artifacts; independent status per class.
- Execute through real browser/device UI; exploratory control may discover the path.
- Durable regression = existing project E2E runner + conventions.
- Product defect → preserve reproduction/evidence; fix only when requested.
- Commands + hooks + CI → `$deterministic-checks`; assertion strength → `$test-quality`.
- Requested/produced screenshot or video → load [visual-evidence.md](references/visual-evidence.md) + validate its receipt.

## Route

| Target | Load |
|---|---|
| Web + Playwright | [playwright.md](references/playwright.md) |
| Flutter device/emulator | [flutter.md](references/flutter.md); Riverpod app also → `$building-flutter-apps` |
| Other stack | Existing project runner/docs; absent owner → report gap |

| Evidence mode | Required proof |
|---|---|
| Smoke/regression | User path + assertions + result; failure → diagnostic artifacts |
| UI review | Existing UI → comparable before/after; new UI → accepted reference/mockup + final states |
| Audit/demo | Video only when requested or necessary to prove temporal behavior |

- Load only matching target reference; combine modes when requested.
- Missing environment/account/data/permission → exact blocker; never fabricate pass evidence.

## Proof

| Result | Evidence |
|---|---|
| `PASS` | Every required evidence class independently PASS |
| `CONCERNS` | Partial surface + exact unproven behavior + next proof |
| `FAIL` | Reproduction step + expected/actual + failure artifacts |

- Artifact = smallest useful set; redact secrets + personal data.
- PASS requires visible outcome + durable state/source-of-truth evidence when behavior persists data.
