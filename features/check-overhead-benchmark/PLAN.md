# Check overhead benchmark

Status: Complete

## Outcome + scope

The `performance` gate fails when a check starts more of its own child processes in a large repository than in a small one. Hard Eng's per-check work stays constant, so a change that adds a Git call per file fails CI on any runner speed. Non-goals: gate run times, the project's own tests and wall-clock limits, which differ between runners.

## Repository context

Owners: `tests/performance` holds Hard Eng's count-based benchmarks and runs as the `performance` gate in `hard-eng.gates.json`. The new test counts process starts with Python's `subprocess.Popen` audit event while `check` runs with 10 and with 400 files. Measured on 2026-10-20: a check of this repository starts 33 Git commands before its gates, so the count is small and stable.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to make the Hard Eng flow faster without weaker checks and to ship into `develop`; the coordinator asked for a deterministic benchmark that fails CI on slowdowns. Decided: count process starts, not seconds, because seconds flake on shared runners.

## Acceptance + steps

- [x] A check starts the same child processes for 10 and for 400 files → `tests/performance/test_check_overhead.py::test_check_starts_the_same_processes_for_ten_or_four_hundred_files`.

## Baseline + execution

Result: Passed
Evidence: `develop` 6d6063d: the test passes. With one `git check-ignore` call per file added to `repository_files`, the test failed.
Execution: One builder; the test only, no production change.

## Risks + recovery

A future change that needs one process per file fails this test; that change must state why. Remove the test file to undo.

## ux_reference

N/A — a test with no visual surface.

## Verification

Result: Passed
Evidence: The new test passes alone and inside the `performance` gate. Branch full suite 1,822 passed; the same 8 environment failures as `develop` (no Dart or Swift in this container, and the 2 interrupted pre-push cases). Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the test runs the real `check` on a real Git repository.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
