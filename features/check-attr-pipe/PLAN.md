# Read generated-file attributes without a live stdin pipe

Status: Complete

## Outcome + scope

`generated_sources` no longer hangs on macOS under load (issue 375). Git reads the path list from a temporary file, so Hard Eng never writes to a pipe that git is not reading. Non-goals: other git calls that take no large input.

## Repository context

Owner: `.hooks/gate_config.py` (`generated_sources`); tests in `tests/test_dart_config.py`.
Same cause: N/A — no other Hard Eng call passes a large `input=` to a git command that writes output per path.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-22 to fix and merge the open hard-eng issues.

## Acceptance + steps

- [x] Git reads the paths from a file, not a live pipe, and still finds generated files among 5000 paths → `tests/test_dart_config.py::test_generated_sources_reads_paths_from_a_file_not_a_live_pipe`.
- [x] Existing behavior still holds: linguist-generated and vendored files are found → `tests/test_dart_config.py::test_dart_generator_output_is_marked_generated_once`.

## Baseline + execution

Result: Passed
Evidence: develop CI on b495725 passed.
Execution: One builder, this session.

## Risks + recovery

- A temporary file costs one disk write per check. The path list is small (a few hundred kilobytes at most).

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: Focused test passes; full `hard-eng.py check` in the cloud passes except the 6 Dart/Swift tests this container cannot run. The macOS hang is not reproducible here; the next Mac canary run is the field proof.
Delivery target: Merge
Delivery: Pending — PR merged to develop.
E2E: N/A — no user journey.
