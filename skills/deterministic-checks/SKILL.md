---
name: deterministic-checks
description: Enforce project-specific analyzers, linters, scanners, and tests for JavaScript/TypeScript, React, and Dart/Flutter. Use before code handoff or shipping, when resolving findings, adding lint rules, or wiring CI.
---

# Deterministic Checks

## Layers

| Layer | Proof |
|---|---|
| Analyzer/typecheck | Language correctness |
| Linter | Accepted project conventions + best practices |
| Scanner | Cross-file, framework, architecture, dependency, duplication, security, a11y risk |
| Tests | Behavior |

## Route

- Stack evidence + project scripts/config/lock/CI → run every matching row on final tree.

| Stack | Required gates | Failure |
|---|---|---|
| JS/TS | typecheck + chosen linter + tests + Fallow | gate fail; unresolved report finding |
| React/Next | JS/TS row + React Doctor | configured gate fail; unresolved diagnostic ID |
| Dart, non-Flutter | package-root `dart analyze` + `dart test` + Dart Decimate | analyzer/test fail; Dart Decimate exit `1`, `2`, or `8` |
| Flutter | package-root `dart analyze` + `flutter test` + Dart Decimate | analyzer/test fail; Dart Decimate exit `1`, `2`, or `8` |

## Select Lints

- Existing project → preserve linter + config SSOT; never add a second linter implicitly.
- JS/TS missing owner → ask user: ESLint = plugin breadth; Oxlint = fast dedicated lint; Biome = integrated format/lint.
- Flutter + Riverpod → `$building-flutter-apps` lint profile; other Flutter/Dart → existing or user-approved `analysis_options.yaml`.
- Project rule eligibility = accepted contract or repeated defect; owner = closest existing rule, otherwise narrow custom lint/test.
- Custom rule proof = violating fixture fails + valid fixture passes + CI executes it.
- Linter replacement = coverage-proven full migration; superseded config/dependency/script = deleted.

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
