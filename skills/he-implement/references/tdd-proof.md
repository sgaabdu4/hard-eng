# TDD Proof

Use `test-quality` before `owner-change`.

1. List behavior scenarios for the owner change.
2. Add or identify the smallest failing behavior test first.
3. Run and record the red state in `test-first-proof` with `sequence` and explicit `test-quality` evidence before `owner-change`.
4. Implement after the red state is recorded.

If red-first is impossible, run a mutation or "make it fail" proof before readying Verify.
Proof commands fail closed on no-op flags, failure masking, unsafe path/preload/config overrides, package-script passthrough bypasses, and dry-run/list-only runner modes.
