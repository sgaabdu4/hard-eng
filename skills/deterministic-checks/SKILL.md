---
name: deterministic-checks
description: Enforce project-specific analyzers, linters, scanners, and tests for JavaScript/TypeScript, React, and Dart/Flutter. Use before code handoff or shipping, when resolving findings, enforcing SSOT drift, adding rules, or wiring CI.
---

# Deterministic Checks

## Route

- Stack evidence + project gate owners → run every matching row on final tree.

| Stack | Required gates |
|---|---|
| JS/TS | typecheck + chosen linter + tests + [Fallow](references/fallow.md) |
| React/Next | JS/TS row + [React Doctor](references/react-doctor.md) |
| Dart, non-Flutter | package-root `dart analyze` + `dart test` + [Dart Decimate](references/dart-decimate.md) |
| Flutter | package-root `dart analyze` + `flutter test` + [Dart Decimate](references/dart-decimate.md) |

## Select Rules

- Existing project → preserve linter + config SSOT; never add a second linter implicitly.
- JS/TS missing owner → ask user: ESLint = plugin breadth; Oxlint = fast dedicated lint; Biome = integrated format/lint.
- Flutter + Riverpod → `$building-flutter-apps` lint profile; other Flutter/Dart → existing or user-approved `analysis_options.yaml`.
- SSOT candidates = clock/timezone/date formats + routes/schemas/keys + UI tokens/primitives/components/widgets + permissions/events/config.
- SSOT gate = canonical owner first; then project lint/scanner/test rejects duplicate definitions/implementations + raw literals/styles/calls outside owner.
- Detectable syntax/graph drift → lint/scanner; semantic drift → contract test; uncertain regex = forbidden.
- Project rule eligibility = accepted contract or repeated defect; owner = closest existing rule, otherwise narrow custom lint/test.
- Custom rule proof = violating fixture fails + valid fixture passes + CI executes it.

## Enforce

- Commands + config + CI = project-owned SSOT.
- Missing/changing hook or CI wiring → read [hooks.md](references/hooks.md).
- Native gates + scanners = complementary proof.
- Finding → fix root cause + connected blast radius → rerun unchanged gate; exit `0` cannot erase report content.
- Tool/config/runtime error = `FAIL`; missing gate = `CONCERNS` + exact wiring proposal.
- Forbidden = `--no-verify` + `|| true` + `continue-on-error` + silent skip + severity downgrade + baseline refresh to manufacture green.
- Exception = exact finding + evidence + narrow scope + explicit user approval.
- New repo = all findings block; existing repo = introduced findings block + inherited findings remain visible.

## Proof

| Result | Evidence |
|---|---|
| `PASS` | Matching commands + exits + reports; no unresolved finding |
| `CONCERNS` | Missing gate or approved exception + exact gap |
| `FAIL` | Finding, crash, config error, skipped scope, or unapproved bypass |
