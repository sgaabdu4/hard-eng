# A proven copy of a judged package is judged once, at its source

Status: Complete

## Outcome + scope

A folder that `generated_marks` proves to be a byte copy of a tracked package is no longer judged by the nested Dart settings rule or by the function's Dart Decimate gate, but only when its source package is a gate group of its own that runs the same Dart gates in full: strict typing with the Flutter skill lints, Dart Decimate with the CRAP limit of 30, and tests with coverage. Otherwise the copy is judged in place as before. Non-goals: relaxing any setting, lint or limit for the copy or the source; reading `.gitattributes` for any other rule.

## Sources + coverage

Sources: N/A — found while an installed Dart project could not pass the nested settings rule, the copy proof and the Dart Decimate gate together; the owner's reminder that Hard Eng stays strict (coordinator message, 2026-11-19) gives the three conditions.

## Repository context

Owners: `.hooks/generated_marks.py` owns the copy proof (`derived_copy`, `proven_copy`) and now also names the source folder of a proven copy. `validate_dart_typing`, `validate_dart_boundaries` and the new `judged_copies` and `leave_out_copies` live in `.hooks/dart_boundaries.py`; `prepare_command` and `run_limited_gate` in `.hooks/gate_runner.py` call them beside `leave_out_children`. Dart Decimate 0.0.75 `check --workspace <package name>` (repeatable) leaves out the other local packages: on a scratch project with a copy that has CRAP, complexity and dead-file findings it exits 0 with no finding and no clone group that names the copy.
Same cause: no earlier plan for this cause. Other rules that judge files in a proven copy: the comment scan, the switch-off scan, the whole-project pass, the text-wall scan, the coverage source list, the secret scan list and the UI rules all read `generated_sources`, which already hides a proven copy, so they are not at fault. Two rules did not read it: the nested settings walk in `validate_dart_typing` (it reads the copy's `analysis_options.yaml` through `rglob`) and the Dart Decimate scan (a tool that reads no `.gitattributes`). Fixed both here. Dart Analyze and `dart format` also read the copy; the copy is a byte copy that passes both at its source, so they need no change.
Single source: the copy proof stays in `generated_marks.py`; `judged_copies` calls it and keeps no mark parser. The gate list that proves the source (types, tests with coverage, Dart Decimate with the strict form) reuses `dart_scan_includes_boundaries`, `validate_dart_typing` and `validate_dart_boundaries`, the checks that run on that group. Searched `.hooks` for `analysis_options`, `dart-decimate`, `generated_sources`, `proven_copy` and `derived_copy`: no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The coordinator assigned this fix and set the three conditions; AGENTS.md line 10 lets this codebase fix faults at their cause.

## Acceptance + steps

- [x] A proven marked copy whose `analysis_options.yaml` has no include passes the nested settings rule when its source is a group that runs the full Dart gates → `tests/test_proven_copy_judged_once.py::test_a_proven_copy_with_a_source_group_skips_the_nested_settings_rule`.
- [x] A source that is no group, and a source group without the types gate, without the strict Dart Decimate gate or without tests with coverage, leave the copy judged in place and refused with the existing text → `tests/test_proven_copy_judged_once.py::test_a_copy_is_judged_in_place_unless_every_condition_holds`.
- [x] The same copy with one changed file, and a copy with no mark, are judged in place and refused with the existing text → `tests/test_proven_copy_judged_once.py::test_a_copy_with_one_changed_file_or_no_mark_is_judged_in_place`.
- [x] An unmarked nested settings file without the include is still refused → `tests/test_proven_copy_judged_once.py::test_an_unmarked_nested_settings_file_without_the_include_is_still_refused`.
- [x] A source whose strict typing settings or Dart Decimate CRAP limit fail their check does not excuse its copy → `tests/test_proven_copy_judged_once.py::test_a_source_that_fails_its_own_settings_does_not_excuse_its_copy`.
- [x] A run whose groups hold only the function's group still finds the source group (the fault of fc67e2be) → `tests/test_proven_copy_judged_once.py::test_a_run_with_only_the_function_group_still_finds_the_source`.
- [x] The function's Dart Decimate command leaves out a proven copy and keeps every other package, so findings inside the copy fail no gate → `tests/test_proven_copy_judged_once.py::test_the_decimate_gate_leaves_out_a_proven_copy`.
- [x] The same findings outside a copy, or in a copy that is not proven, still fail the gate → `tests/test_proven_copy_judged_once.py::test_findings_outside_a_copy_still_fail_the_gate` and `tests/test_proven_copy_judged_once.py::test_a_copy_that_is_not_proven_keeps_the_whole_scan`.
- [x] A copy of a package that has no gate group of its own is still judged by the function's gate → `tests/test_proven_copy_judged_once.py::test_a_copy_without_a_source_group_keeps_the_whole_scan`.

## Baseline + execution

Result: Passed
Evidence: Ready check passed before the code edits (`check --plan-stage Ready --base HEAD`, exit 0). 2026-11-19, develop a7909cdb: `uv run --frozen pytest tests/test_derived_copies.py tests/test_dart_nested_settings.py tests/test_scan_findings.py` passes locally before the edits. CI at that commit shows both a passing and a failing `hard-eng` run, the failing one from a stale queued job that this commit's parent fixed; this change adds no part of it.
Execution: One builder, this session.

## Risks + recovery

A source group that passes the gate-list check but whose group never runs because a `--base` run skips it: `judged_copies` runs the typing and Dart Decimate settings checks on the source itself before it skips the copy, so the proof does not rest on the source group being selected. A wrong skip would hide a real finding in a copy; the byte proof and the three conditions keep that to a copy that its source judges in full. Recovery: revert the commits.

## ux_reference

N/A — check messages only; no visible UI.

## Verification

Result: Passed
Evidence: Failing first, on develop a7909cdb with only the new test file added: 4 of 15 fail (`test_a_proven_copy_with_a_source_group_skips_the_nested_settings_rule`, `test_a_run_with_only_the_function_group_still_finds_the_source`, `test_the_decimate_gate_leaves_out_a_proven_copy`, `test_findings_outside_a_copy_still_fail_the_gate`); the 11 near-miss cases pass on both sides. With the fix 15 pass, and 304 pass across the Dart, runner and derived-copy test files. With the three conditions forced true, 7 of the near-miss cases fail, so each off-switch is held. Tool comparison on Dart Decimate 0.0.75, two scratch inputs, 2 of 2 agree: a copy with CRAP, complexity and dead-file findings gives 5 findings in full, 3 of them in the copy, and none in the copy when scoped with `--workspace`, exit 1 both times; a clean function beside two copies and another package gives exit 0, zero finding counts and files from the two kept packages only, and the real report passes `validate_dart_decimate`. Limit: a clone between function code and a copy stays a finding on the function side, which is right. Static gates run on the change: ruff format, lint, complexity and annotations, pyrefly, vulture, jscpd (0 clones) and Semgrep (0 findings).
E2E: N/A — no user journey changes; the proof runs the gate functions on fixture projects.
Real service: N/A — the change calls no outside service; the tool comparison runs the real Dart Decimate binary on scratch inputs, not a service.
Retro: (1) the fault passed every gate on its PR because no test held a project that had to pass the copy proof, the nested settings rule and the Dart Decimate gate together → `tests/test_proven_copy_judged_once.py` now holds that project through `prepare_command` and `run_limited_gate`; (2) the first edit put gate_runner.py over its 1000-line limit and the run_limited_gate statement limit → None — the focused complexity and file length checks caught both before the push.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
