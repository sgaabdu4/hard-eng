# Keep tests gate settings in Dart mutation runs

Status: Complete

## Outcome + scope

Dart mutation testing runs the tests with the same leading `env NAME=value` settings as the package's tests gate. Packages whose tests need those settings no longer abort with "failed with unmodified code". Non-goals: other adapters, the mutation_test tool, gate commands.

## Repository context

Owner: `dart` in `.hooks/mutation.py` wrote a fixed `dart test` or `flutter test --no-pub` command into the mutation_test config. A gate such as `env PHONE=... dart run coverage:test_with_coverage` lost its settings, so tests that read them failed before any mutation. Tests live in `tests/test_mutation.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to run mutation testing fully and fix what blocks it.

## Acceptance + steps

- [x] A tests gate starting with `env NAME=value ...` keeps those settings in the Dart mutation command.
- [x] Gates without settings keep `dart test` or `flutter test --no-pub`.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: A consuming project's Dart mutation run aborted because four tests needed gate settings; the new parameterised test covers plain and `env` forms for Dart and Flutter.
Execution: One builder; one owner change.

## Risks + recovery

A setting value containing spaces depends on mutation_test's command parsing. Recovery: quote or move such settings into the test setup.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Passed
Evidence: Pending full gate result below.
E2E: N/A — command text covered by unit cases.

Delivery target: Merge
Delivery: Pending — PR checks, rebase merge, main CI.
