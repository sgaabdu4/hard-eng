# Test Quality Workflow

1. Read requirements, user story, public API, diff, and existing high-quality tests.
2. Name the behavior seam before test code: API, component output, state transition, persisted record, emitted event, CLI output, or thrown error.
3. List scenarios before test code when practical: happy path, failure path, boundary/edge path, and integration or side-effect path when relevant.
4. Use project test style as the template: naming, fixtures, Arrange-Act-Assert, and assertions.
5. Test the real implementation. Mock only external boundaries: network, DB, filesystem, clock, random, process, and third-party services.
6. Assert public behavior: return values, rendered output, state changes, emitted effects, persisted records, public logs/events, and thrown errors.
7. Avoid tautologies. Do not assert "called the mocked function" unless the call is the public contract.
8. Cover realistic boundaries: empty/null, invalid input, limits, permissions, partial failures, concurrency, timezones, unicode, overflow, timeout, and cancel.
9. Run the smallest relevant test command.
10. For risky logic, prove test strength with one red state: first run a failing test when doing TDD, or make a tiny production mutation and confirm the test fails, then restore it.
11. After implementation, audit requirements and diff for missing cases.

## TDD Notes

- Agree the seam before changing production code
- Keep the first red proof narrow enough to fail for the behavior, not for setup noise
- Move broad refactors after green unless the seam cannot be tested safely without a small preparatory extraction
- Prefer one vertical behavior test over many implementation-detail assertions
