# Test Quality Workflow

1. Read requirements, user story, public API, diff, and existing high-quality tests.
2. List scenarios before test code when practical: happy path, failure path, boundary/edge path, and integration or side-effect path when relevant.
3. Use project test style as the template: naming, fixtures, Arrange-Act-Assert, and assertions.
4. Test the real implementation. Mock only external boundaries: network, DB, filesystem, clock, random, process, and third-party services.
5. Assert public behavior: return values, rendered output, state changes, emitted effects, persisted records, public logs/events, and thrown errors.
6. Avoid tautologies. Do not assert "called the mocked function" unless the call is the public contract.
7. Cover realistic boundaries: empty/null, invalid input, limits, permissions, partial failures, concurrency, timezones, unicode, overflow, timeout, and cancel.
8. Run the smallest relevant test command.
9. For risky logic, prove test strength with one red state: first run a failing test when doing TDD, or make a tiny production mutation and confirm the test fails, then restore it.
10. After implementation, audit requirements and diff for missing cases.
