---
name: deterministic-checks
description: Enforce deterministic quality gates for JavaScript/TypeScript, React, and Dart/Flutter. Use before code handoff or shipping, when resolving scanner findings, or when wiring CI.
---

# Deterministic Checks

## Route

- Stack evidence + project scripts/config/lock/CI → run every matching row on final tree.

| Stack | Required gates | Failure |
|---|---|---|
| JS/TS | lint + typecheck + tests + Fallow | Fallow fail/exit `1`; unresolved report finding |
| React/Next | JS/TS row + React Doctor | configured gate fail; unresolved diagnostic ID |
| Dart, non-Flutter | `dart analyze` + tests + Dart Decimate | Dart Decimate exit `1`, `2`, or `8` |
| Flutter | `flutter analyze` + `flutter test` + Dart Decimate | Dart Decimate exit `1`, `2`, or `8` |

## Enforce

- Command + config + exact pin + lockfile + CI = project-owned SSOT; local + CI use same command.
- Native gates + scanners = complementary proof.
- Finding → fix root cause + connected blast radius → rerun unchanged gate; exit `0` cannot erase report content.
- Tool/config/runtime error = `FAIL`; missing gate = `CONCERNS` + exact wiring proposal.
- Forbidden = unpinned execution + `|| true` + `continue-on-error` + silent skip + severity downgrade + baseline refresh to manufacture green.
- Exception = exact finding + evidence + narrow scope + explicit user approval.
- New repo = all findings block; existing repo = introduced findings block + inherited findings remain visible.

## Proof

| Result | Evidence |
|---|---|
| `PASS` | Matching commands + exits + reports; no unresolved finding |
| `CONCERNS` | Missing gate or approved exception + exact gap |
| `FAIL` | Finding, crash, config error, skipped scope, or unapproved bypass |
