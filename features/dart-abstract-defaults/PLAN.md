# Omit bodyless Dart methods with parameter defaults from coverage

Status: Complete

## Outcome + scope

Fix [#142](https://github.com/sgaabdu4/hard-eng/issues/142): the Dart coverage classifier treats `abstract class Port { Future<void> clear({bool includeFiles = false}); }` as executable, so a fully exercised implementation fails with `Coverage report omits production files`. Bodyless methods are erased whatever their parameters; methods with bodies, constructors and executable initializers stay required. Non-goals: mixins and other declaration kinds the classifier does not yet erase.

## Repository context

Owner: `erasedClassMember` in `.hooks/dart_coverage.py`, which rejects any `FormalParameterDefaultClause` before checking `EmptyFunctionBody`. Proof owner: `tests/test_dart_coverage.py`. Native check on Dart 3.13.4: `dart test --coverage` + `coverage:format_coverage` emit no record for a library holding only bodyless methods with named, positional and `const Duration(...)` defaults, and emit `DA:2,0` for `int read([int page = 1]) => page;` in an abstract class. A redirecting factory with a default is a compile error (`default_value_in_redirecting_factory_constructor`), so it never reaches coverage.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix open Hard Eng issues, open a PR and land it on main.

## Acceptance + steps

- [x] A bodyless method with a parameter default is erased; the same method with a body stays required → `tests/test_dart_coverage.py`.
- [x] Native LCOV omits a contract whose bodyless method has a default while its implementation, called with and without the argument, is covered → `tests/test_dart_coverage.py`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `91171b2` + this plan → exit 0; 17/17 gates PASS.
Execution: One builder; check body presence before the default-clause guard.

## Risks + recovery

A bodyless method has no code to count, so erasing it cannot hide an executable line. Revert the one-line move if a supported analyzer reports defaults on a bodyless member that the VM counts.

## ux_reference

N/A — no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_dart_coverage.py` → 3 passed; with the unfixed classifier both native tests fail (`default_parameter.dart` and `contract.dart` not erased). Native LCOV omits `contract.dart` and records `runtime_contract.dart` at 4/4 after calls with and without each default; `default_body.dart` stays required. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS.
E2E: N/A — coverage classifier; the native `dart test --coverage` fixture exercises the affected boundary.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
