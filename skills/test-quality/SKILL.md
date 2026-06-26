---
name: test-quality
description: Use for tests/specs/QA/TDD/mutation: design, write, review, repair, behavior assertions, failure proof.
---

# Test Quality

Keep tests requirement-led, behavior-facing, and executable.

## Trigger

Use for:
- Writing or reviewing tests
- Fixing weak/flaky/over-mocked tests
- Adding tests after an implementation
- Checking AI-generated test quality
- Mutation or "make it fail" drills

## Flow

1. Read requirements, user story, public API, diff, and existing high-quality tests.
2. List scenarios before test code when practical:
   - happy path
   - failure path
   - boundary/edge path
   - integration or side-effect path when relevant
3. Use project test style as the template: naming, fixtures, Arrange-Act-Assert, assertions.
4. Test the real implementation. Mock only external boundaries: network, DB, filesystem, clock, random, process, third-party services.
5. Assert public behavior: return values, rendered output, state changes, emitted effects, persisted records, logs/events when public, and thrown errors.
6. Avoid tautologies: no "called the mocked function" assertions unless the call is the public contract.
7. Cover realistic boundaries: empty/null, invalid input, limits, permissions, partial failures, concurrency, timezones, unicode, overflow, timeout/cancel.
8. Run the smallest relevant test command.
9. For risky logic, prove test strength with one red state:
   - first run a failing test when doing TDD, or
   - make a tiny production mutation and confirm the test fails, then restore it
10. After implementation, audit requirements and diff for missing cases.

## Review Report

For test reviews, report:
- Missing requirement scenarios
- Over-mocking or internal assertions
- Tautological assertions
- Boundary gaps
- Flake risks
- Verification command and result

## Stop Conditions

Do not accept tests that only snapshot broad output, only assert mocks, duplicate the implementation, or pass after the targeted bug is introduced.
