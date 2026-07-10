# Test-Driven Development Workflow

TDD is the red → green → refactor loop. Apply the test, seam, anti-pattern, and
cycle rules on every vertical slice.

Read `CONTEXT.md` when present so test names and interface vocabulary match the
project domain, and respect ADRs in the touched area.

## Test contract

Tests verify behavior through public interfaces. A good test reads like a
specification and survives internal refactors.

A **seam** is the public boundary where behavior is observed. Name the seam
before testing. When repo evidence makes the public boundary and critical
behavior unambiguous, record the seam and proceed. Ask the user only when
competing seams materially change coverage or behavior. No test is written at a
guessed seam.

## Anti-patterns

- **Implementation-coupled** — mocks internal collaborators, tests private methods, or verifies through a side channel
- **Tautological** — recomputes the expected value the same way as production code instead of using an independent literal, worked example, or spec
- **Horizontal slicing** — writes all imagined tests before implementation instead of letting each completed behavior inform the next tracer bullet

## Cycle

1. Red: write the smallest failing behavior test at the chosen seam.
2. Green: add only enough implementation to pass that test.
3. Refactor: improve structure without changing behavior, rerun the relevant tests, and keep the slice green.

Repeat with one seam and one behavior per vertical slice. Broader maintainability
review belongs to `code-review`.
