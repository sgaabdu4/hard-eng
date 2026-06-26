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

Read `references/workflow.md` before writing or reviewing tests.

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
