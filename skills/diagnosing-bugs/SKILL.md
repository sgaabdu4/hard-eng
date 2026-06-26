---
name: diagnosing-bugs
description: Use for hard bugs, failing behavior, flaky tests, exceptions, regressions, or unexplained slowness before fixing.
---

# Diagnosing Bugs

Use this before changing code when the failure is not already isolated.

Load `references/workflow.md` for the diagnosis loop.

Coordinate with nearby skills:

- If the user asks about latency, load `performance-rescue` too
- If the fix needs test design or TDD, load `test-quality` too
- If the bug is security, auth, secrets, or data exposure related, load
  `security-review` too.

Do not jump from symptom to patch.
First build evidence that the proposed fix addresses the exact user-described
failure.
