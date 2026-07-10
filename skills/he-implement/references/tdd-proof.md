# TDD Proof

Use `test-quality` before `owner-change`.

## Red Path

1. List behavior scenarios for the owner change.
2. Name the public seam that should prove the behavior: API, component output, state transition, persisted record, emitted event, CLI output, or thrown error.
3. Add or identify the smallest failing behavior test first.
4. Run and record the red state in `test-first-proof` with `sequence` and explicit `test-quality` evidence before `owner-change`.
5. Implement after the red state is recorded.

If red-first is impossible, run a mutation or "make it fail" proof before readying Verify.
Proof commands fail closed on no-op flags, failure masking, unsafe path/preload/config overrides, package-script passthrough bypasses, and dry-run/list-only runner modes.

## Test Shape

- Assert public behavior, not implementation structure
- Mock only external boundaries: network, DB, filesystem, clock, random, process, and third-party services
- Do not count "called the mocked function" as proof unless the call is the public contract
- Do not write tautological tests that restate the implementation
- Keep refactors after green proof unless the refactor is needed to expose the behavior seam safely
- Record the seam, failing command, failure signal, and later green command in state
