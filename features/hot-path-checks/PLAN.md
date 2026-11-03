# Hot-path checks and CI time split

Status: Complete

## Outcome + scope

Every project that uses Hard Eng fails added code that builds a constant regex inside a function, allocates an array of booleans, reads whole rows or adds an in-process cache. Added code that holds a judgment case (awaits in a loop, independent awaits in sequence, URL parsing in a loop, JSON columns, whole-entity loads) prints a note. `hot-paths` lists old cases on request, and `ci-usage --runs N` splits the slowest jobs into queue, setup and run time. Non-goals: failing code already on the base branch, blobless CI clones, a CI step split, test sharding and Hard Eng's own `.hooks/` code.

## Repository context

Owners: `check` in `.hooks/hard-eng.py` runs the added-line checks (`validate_comments`, `validate_suppressions` in `.hooks/comments.py`); `diff_lines` gives added lines; `managed_command` in `.hooks/tool_setup.py` runs Semgrep through `uvx`; `ci_usage` lived in `.hooks/ci_setup.py` (952 lines, close to HE-FILE-LENGTH) and already read job steps. Rule files under `.agents/skills/he/` reach every installed project on update.
Same cause: N/A — new checks, no earlier fix. A blocking rule in the whole-repository `security` gate or the Biome `typing-style` gate would fail old code in every installed project, and HE-DEBT-SHRINK-ONLY gives updates no debt path, so the rules run only on added lines.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer asked to implement every practice in the review, review it adversarially with an Opus subagent, take advice from Fable, merge into `develop` and release to `main`.
Decided (Fable advice, verified): only rules with a rewrite that is never worse block; the others print notes; no rule enters the `security` or `typing-style` gate; Python regexes block in added code because the user asked for module-level regexes, although `re` caches compiled patterns; test files, `.hooks/` and `.agents/` are not scanned.

## Acceptance + steps

- [x] Each rule fires on its annotated fixture line and nowhere else (division, `g` regexes, column lists, dynamic patterns, module-level regexes stay clean) → `tests/test_hot_paths.py::test_each_rule_finds_exactly_the_annotated_lines`.
- [x] Added slow code fails, old slow code passes, judgment cases print as notes → `tests/test_hot_paths.py::test_added_slow_code_fails_while_old_code_and_notes_pass`.
- [x] `hot-paths` lists old findings and exits 0 → `tests/test_hot_paths.py::test_a_repository_scan_lists_old_and_new_findings`.
- [x] `ci-usage --runs 150` uses the newest runs and splits a job into 30 s queue, 22 s setup and 28 s run → `tests/test_ci_usage.py::test_ci_usage_splits_the_slowest_jobs_into_queue_setup_and_run`.
- [x] `ci-usage --runs 150` reads two pages of 100 runs and keeps the newest 150 → `tests/test_ci_usage.py::test_ci_usage_reads_only_the_newest_runs_across_pages`.
- [x] A Swift file Semgrep can only partly parse still reports its findings and does not fail → `tests/test_hot_paths.py::test_a_partly_parsed_file_still_reports_its_findings`.
- [x] Skills tell agents how to act on each practice and on a CI audit, and every command and link they name exists → `tests/test_skill_links.py::test_documented_commands_and_flags_exist` and `tests/test_skill_links.py::test_distributed_skill_links_resolve`.

## Baseline + execution

Result: Passed
Evidence: `develop` 079bdc3 `hard-eng` CI passed. Local full `check` on this machine fails only tests that need the Dart and Swift SDKs, which it lacks (`FileNotFoundError: 'dart'`); every other gate passed.
Execution: One builder in this session; Fable advised on the design; an Opus subagent reviews the diff adversarially until no verified finding remains.

## Risks + recovery

A note rule can be noisy in projects with many sequential awaits; notes never block. Semgrep adds a few seconds to `check` when code files change. Recovery: revert the merge; no state or configuration changes in installed projects.

## ux_reference

N/A — command-line checks and skill text; no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_hot_paths.py` and `tests/test_ci_usage.py`: 9 passed, with the fixture test counting findings per line. `python3 .hooks/hard-eng.py hot-paths` on this repository: `HE-HOT-PATH: 0 findings` after the four root-script regexes moved to module level. Full `check --plan-stage Ready` on b9e07d3: every gate passed except `tests`, whose only failures need the Dart and Swift SDKs this machine lacks (the same tests failed on `develop` here) and one process-exit race fixed in ba878b1; CI has the SDKs and runs the full suite. Opus adversarial review, 3 rounds: round 1 found 9 issues (a broken Swift rule test, false blocks on division, strings, comments, static fields, `EXISTS`, docstrings, `.json()`, Swift previews, a run-paging bug), round 2 found 3 (multi-flag `g` regexes, multi-line `EXISTS`, Dart comments), round 3 found 1 (a `g` regex after another on one line); all fixed with fixtures. Known gaps, not blocking: SQL inside Dart block comments still blocks, `--`-like text inside SQL strings hides a finding, Dart sequential awaits get no note (Semgrep's Dart parser cannot express "uses the first result"), `check --only-language` skips the scan, Hard Eng's own `.hooks/` are not scanned.
E2E: Passed — `python3 .hooks/hard-eng.py check` ran the new step on this repository's real diff, and `hot-paths` ran on the real tree.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, then the `develop` → `main` release PR.
