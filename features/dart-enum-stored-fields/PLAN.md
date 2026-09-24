# Recognize counter-free Dart enums with stored fields

Status: Complete

## Outcome + scope

Fix [#156](https://github.com/sgaabdu4/hard-eng/issues/156): `erased_dart` treats a const enum whose members are only const empty-bodied constructors, final instance fields and static const fields as counter-free, so native LCOV's missing source record no longer fails coverage. Enum getters, methods, mixins and interfaces stay coverage-required. Non-goals: waiving all enums, lowering thresholds, or changing class rules.

## Repository context

Owners: `.hooks/dart_coverage.py` (`erased` enum branch), called by `line_coverage` in `.hooks/reports.py`; tests in `tests/test_dart_coverage.py`. The enum branch rejected any `ClassMember`, `ArgumentList` or `FormalParameterList`, so `enum Shift { am('Morning'); const Shift(this.label); final String label; }` stayed required. Scratch run on Dart 3.13.4 (`dart test --coverage` + `coverage:format_coverage`): enums with field formals, named and default parameters, initializer lists, asserts, instance field initializers, static const fields and const constant arguments emitted no LCOV record; an enum getter and an enum method emitted counters.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: User asked to fix all open Hard Eng issues (only #156 is open), then approved opening a PR and merging it.

## Acceptance + steps

- [x] Stored-field const enum and default-parameter const enum → `erased_dart` returns them in `test_native_dart_declarations_and_runtime_controls`.
- [x] Enum with a getter and enum with a method → stay required in the same test; existing class/runtime controls unchanged.
- [x] Real VM: `Shift` enum read by a test → absent from native LCOV and returned by `erased_dart` in `test_native_dart_lcov_omits_declaration_only_libraries`, while `runtime.dart` keeps its counters.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `f43d077` → exit 0; 17/17 gates PASS, 803 tests passed.
Execution: One builder; replace the enum descendant scan with a per-member enum rule at its single owner.

## Risks + recovery

A future Dart VM could start emitting counters for const enum constructors; the native LCOV test would then fail and show it. Recovery: narrow the enum member rule again.

## ux_reference

N/A — hook-only change with no visual surface.

## Verification

Result: Passed
Evidence: Scratch VM run → classifier erased exactly the 8 enum shapes with no LCOV record; getter, method, `static final` and factory enums emitted counters and stayed required. `uv run pytest tests/test_dart_coverage.py` → 3 passed; with the old classifier → 2 failed on `enum_field.dart`, `enum_default.dart` and `shift.dart`. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 803 tests passed.
E2E: Passed — `test_native_dart_lcov_omits_declaration_only_libraries` runs `dart test --coverage`; `shift.dart` is absent from LCOV and erased while `runtime.dart` keeps its counters.

Delivery target: Merge
Delivery: Pending — PR checks green, merge to main, main CI green.
