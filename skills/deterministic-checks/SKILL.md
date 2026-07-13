---
name: deterministic-checks
description: Run deterministic repository and stack quality gates.
---

# Deterministic Checks

- Owner = exact commands + analyzers/linters/scanners + hooks + CI wiring/results.
- Test behavior/seam/assertion/mutation design = `$test-quality`.
- Real browser/device scenario proof = `$e2e`.

## Route

- Stack evidence + project gate owners → run every matching row on final tree.

| Stack | Required gates |
|---|---|
| Repository context | [PRODUCT/DESIGN](references/context-docs.md) |
| JS/TS | typecheck + chosen linter + tests + [Fallow](references/fallow.md) |
| React/Next | JS/TS row + [React Doctor](references/react-doctor.md) |
| Dart, non-Flutter | package-root `dart analyze` + `dart test` + [Dart Decimate](references/dart-decimate.md) |
| Flutter | package-root `dart analyze` + `flutter test` + [Dart Decimate](references/dart-decimate.md) |

## Select Rules

- Existing project → preserve linter + config SSOT; never add a second linter implicitly.
- JS/TS missing owner → ask user: ESLint = plugin breadth; Oxlint = fast dedicated lint; Biome = integrated format/lint.
- Flutter + Riverpod → `$building-flutter-apps` lint profile; other Flutter/Dart → existing or user-approved `analysis_options.yaml`.
- SSOT gate = canonical clock/format/route/schema/key/UI/permission/event/config owner → reject duplicate owner + raw use outside it.
- Detectable syntax/graph drift → lint/scanner; semantic drift → contract test; uncertain regex = forbidden.
- New rule requires accepted contract/repeated defect + closest owner + failing violation fixture + passing valid fixture + CI execution.

## Enforce

- Commands + config + CI = project-owned SSOT.
- Missing/changing hook or CI wiring → read [hooks.md](references/hooks.md).
- Native gates + scanners = complementary proof.
- Finding → fix owned cause/blast radius → rerun exact gate; exit `0` cannot erase report content.
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
