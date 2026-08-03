---
name: diagnose-flutter-mobile-runtime
description: Diagnose Flutter integrations that compile or install but fail on real Android or iOS devices. Use for recurring or cross-layer failures involving runtime permissions, Health Connect or HealthKit, local or push notifications, FCM or APNs, Appwrite targets, native-plugin hangs, app lifecycle states, or release-only APK, AAB, or IPA behavior.
---

# Diagnose Flutter Mobile Runtime

## Contract

- Owner = cross-layer seam isolation; causal synthesis remains `diagnosing-bugs`.
- Before native, provider, backend, or device action = read [runtime-seam-ladder.md](references/runtime-seam-ladder.md).
- Start = reporter ledger + red-capable user-visible reproduction + exact artifact/device/account/environment identity.
- Proceed one seam at a time; first red/unknown prerequisite cancels downstream retries.
- Installed dependency + present manifest entry + successful provider request + green widget test = wiring evidence only.
- Reinstall = fresh app-instance perturbation; invalidate token, installation, permission, session, and prior delivery evidence.
- Every plugin/external observation = bounded deadline + captured terminal result; indefinite wait or blind polling = `FAIL`.
- Product timeout/fallback change = explicit fix authority + defined user-visible semantics + regression proof; diagnostic timeout alone never selects the fix.
- Source mutation = forbidden without explicit fix authority.

## Route

| Need | Owner |
|---|---|
| Reproduction + mechanism + blast radius | `diagnosing-bugs` |
| Current OS/plugin/provider contract | `research` |
| Flutter/Riverpod/native packaging change | `building-flutter-apps` |
| Appwrite provider/target/message/CLI seam | `appwrite-backend` |
| Sentry issue/release evidence | `sentry` |
| Real device/UI behavior | `e2e` |
| Commands + gates + retry readiness | `deterministic-checks` |
| Proven recurrence | `repeated-failure-learning` → `he-learn` |

## Workflow

1. Build the closure matrix from the reference; include every user-named platform, artifact, lifecycle state, permission state, and delivery path.
2. Bind local versions + exact target identity; verify current external contracts through `research` before platform-dependent diagnosis or repair.
3. Reproduce once at the public seam; descend the ladder until the first red/unknown boundary.
4. Prove the owner/mechanism with one discriminating check; do not reinstall, resend, rebuild, or vary payloads as a substitute.
5. With fix authority, repair the narrowest owner → rerun original red proof → affected downstream states → full requested matrix.
6. Close test data, processes, temporary artifacts, and every reporter-ledger item.

## Complete

| Result | Required proof |
|---|---|
| `PASS` | Original violation green + exact installed release identity + every requested state/path green + backend/source-of-truth readback where applicable + zero open ledger items |
| `CONCERNS` | Exact unavailable seam + impact + attempts + next executable action/owner |
| `FAIL` | Violation remains, root mechanism unproven, prerequisite skipped, evidence invalidated by reinstall/rebuild, or broad retry substituted for isolation |

Report = result → reproduction → identity → first red seam → mechanism → correction or direction → state/artifact matrix → remaining gaps.
