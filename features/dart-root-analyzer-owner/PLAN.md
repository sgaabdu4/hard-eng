# Keep one owner for root Dart analyzer gates

Status: Complete

## Outcome + scope

Fix [#159](https://github.com/sgaabdu4/hard-eng/issues/159): setup and update keep a single root Dart types gate. They reuse a project's package-root `dart analyze --fatal-infos` (with or without `.`) as the owner, expand Hard Eng's own unexpanded template gate in place, and remove identical copies and Hard Eng's `strict-` gate left beside that owner by earlier installs. Weaker or narrower analyzer commands still get the strict template gate. Non-goals: changing nested Dart package scopes, analyzer flags, or the Python types gate.

## Repository context

Owners: `setup.py` `configure_typing_checks` + `adopt_root_dart_gates`, called by `plan_install` on install and update; tests in `tests/test_setup.py`. Since #110, root Dart packages expand the template's `.` to declared sources plus existing test roots, but matching compared exact commands. So a project-owned `dart analyze --fatal-infos` became `project-types` next to a second strict gate. A fresh root install did the same to the template's own `types-lint` gate. `test_plain_dart_uses_native_coverage_tool` indexed gates by role and missed that duplicate.

Python types scope (the request's first premise) needed no change. `prepare_command` in `.hooks/hard-eng.py` passes every production and test `.py` file explicitly to pyrefly for the `types` role, using `rglob` rather than Git ignore rules. In a synthetic consumer inside `<repo>/.claude/worktrees/fx`, with `**/.claude/worktrees/` in the shared `.git/info/exclude`, raw `pyrefly check` printed "No Python files matched" and exited 0. The runner's `run_gate` reported `FAIL types` on a planted `bad-return`, both with and without `tests/`. The same held for this repository's own gate.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open Hard Eng issues and include the relevant ones in this PR. #159 shares the typing-gate matcher with this request; #158 (Flutter browser LCOV) is handled separately.

## Acceptance + steps

- [x] Project root analyzer `dart analyze --fatal-infos` or `... .` → kept as the sole `types` gate, command unchanged, across repeated setup (`test_root_dart_analyzer_is_reused_only_when_it_covers_the_package`).
- [x] Weaker `dart analyze` and narrower `... lib` → kept as `project-types`, and the strict explicit gate is added (same test).
- [x] Earlier-install duplicate state (project or template root gate as `project-types` + `strict-types-lint` explicit) → one `types` gate: the project's root command unchanged, or the template's `types-lint` expanded (`test_root_dart_update_consolidates_duplicate_analyzers`).
- [x] Fresh root Dart install → exactly one analyzer gate (`test_plain_dart_uses_native_coverage_tool`).
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `34b0703` (after `git submodule update --init --recursive` in this worktree) → exit 0; 17/17 gates PASS, 803 tests passed.
Execution: One builder; widen the existing matcher at its single owner.

## Risks + recovery

A project root `.` analyzer can cover more files than the explicit scope, and may fail on nested or generated code. That is the project's own stronger choice, and it stays visible as a failing gate. Recovery: replace it with the explicit command, which the matcher also accepts.

## ux_reference

N/A — setup-only change with no visual surface.

## Verification

Result: Passed
Evidence: With the old `setup.py`, the new and strengthened tests failed (both root forms duplicated, earlier-install duplicates kept, fresh install duplicated); with only the matcher change, the two project-named duplicate cases still failed. With the fix, `pytest tests/test_setup.py tests/test_dart_config.py` → 118 passed. Real installer on a synthetic root Dart fixture: a fresh install gave one `types-lint` on `lib test`. After the gate was changed to `strict-types-lint` `dart analyze --fatal-infos`, reinstall kept exactly that gate with no duplicate. Starting from the issue's duplicated state (`strict-types-lint` path-less as `project-types` + `strict-types-lint` on `lib test`), reinstall and a repeat left only the path-less `strict-types-lint` as `types`. `python3 .hooks/hard-eng.py check --plan-stage Complete` → exit 0; 17/17 gates PASS, 810 tests passed.
E2E: Passed — `setup.py` fresh install and reinstall on the synthetic fixture, with the same reconciliation covered by `test_plain_dart_uses_native_coverage_tool`.

Delivery target: PR
Delivery: Pending — PR checks green.
