# The push check links ignored files that tracked Dart code imports

Status: Complete

## Outcome + scope

The pre-push snapshot links each ignored, untracked Dart file of the main checkout that a tracked Dart file of the commit imports by path, so the commit compiles as it does in the main checkout. Non-goals: other languages; files in a wholly ignored folder; a stand-in for a missing file; a release.

## Sources + coverage

Sources: the request of the maintainer in this task, read in full.
Reviewer: N/A — one request in one message.
Deliverables: None

- Outcome, an ignored file that tracked code imports is linked into the snapshot: In scope — A tracked Dart file imports an ignored file that exists in the main checkout
- Rule, a missing file stays missing and the check fails with its own error: In scope — A missing imported file stays missing
- Rule, only imported files: In scope — An ignored file that nobody imports is not linked
- Rule, only imports of tracked files: In scope — An ignored file that only an untracked file imports is not linked
- Rule, status checks treat the link as Hard Eng's own: In scope — The link stays placed by Hard Eng
- Rule, no measurable added time: In scope — Link speed is recorded in Verification, with no measurable added time
- Rule, Dart imports resolve as Dart resolves them: In scope — An import resolves the way Dart resolves it

## Repository context

Owners: `local_files`, `link_local_files` and `placed_by_hard_eng` in `.hooks/ship_actions.py` own what a new worktree and the push snapshot get from the main checkout. `prepare_checkout` runs them for the snapshot and for the `post-checkout` hook.
Same cause: the cause is a snapshot that holds only tracked files while the commit's code needs a local file that git ignores. Earlier fixes: the `.env*` and local settings links (before this plan) helped for those names only. Searched `.hooks` for other readers of ignored files in a snapshot: `update_submodules` (submodules, not ignored files) and `drop_derived_data` (cache removal). No resolver of Dart imports exists in `.hooks`: `dart_boundaries.py` reads analysis options, and `dependency_graph.py` and `coverage_sources.py` list source suffixes without reading imports. Other languages keep the same gap and are a stated limit. A file in a wholly ignored folder shows in the ignored listing as the folder, so it is not linked; this is a stated limit. Imports of a sibling package in a workspace (`package:<other>/...`) are not linked, because the request names this package only; a block comment that holds an import line can link an unneeded file, which is harmless.
Single source: the ignored listing has one owner, `local_files`; the new Dart candidates come from it, with no second listing. The link and the placed check share it, so `placed_by_hard_eng` needs no import scan. Searched `.hooks` and `tests` for other `import`/`export`/`part` readers: `agent_hooks.py` and `comments.py` match import lines for other purposes and give no path resolution to reuse.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer gave this task and the design limits in the request; no release or merge is part of this builder's task.
Decisions:

1. The import scan runs only in `link_local_files`, and only when the ignored listing holds an ignored `.dart` file. A project with none adds no process and reads no file.
2. `placed_by_hard_eng` does no scan. A link stays Hard Eng's own after the task removes the import, because it compares the link with the main checkout's file.
3. The scan reads only tracked Dart files of the snapshot. It never reads the ignored file.

## Acceptance + steps

- [x] A tracked Dart file imports an ignored file that exists in the main checkout: the snapshot holds a link to it → `tests/test_snapshot_imports.py::test_an_ignored_file_that_tracked_code_imports_is_linked_into_the_snapshot`
- [x] A missing imported file stays missing → `tests/test_snapshot_imports.py::test_a_missing_imported_file_stays_missing_in_the_snapshot`
- [x] An ignored file that nobody imports is not linked → `tests/test_snapshot_imports.py::test_an_ignored_file_that_no_tracked_file_imports_is_not_linked`
- [x] An ignored file that only an untracked file imports is not linked → `tests/test_snapshot_imports.py::test_an_ignored_file_that_only_an_untracked_file_imports_is_not_linked`
- [x] The link stays placed by Hard Eng → `tests/test_snapshot_imports.py::test_the_link_stays_placed_by_hard_eng_after_the_import_is_removed`
- [x] An import resolves the way Dart resolves it → `tests/test_snapshot_imports.py::test_an_import_resolves_the_way_dart_resolves_it`
- [x] Link speed is recorded in Verification, with no measurable added time → N/A — a timing record of two runs each side, not a test

## Baseline + execution

Result: Passed
Evidence: the base is origin/develop at a7909cdb; `tests/test_ship_cleanup.py` passed on it.
Execution: one builder; failing tests first, then the change, the static gates, the Complete gate and the independent review.

## Risks + recovery

- A wrong resolution links a file nobody needs, or misses one; the check then fails as before. Recovery: revert the commit; no data step.

## ux_reference

N/A — no screen changes.

## Verification

Result: Passed
Evidence: the new tests failed before the change (15 of 16 failed; log kept in the builder's scratch folder) and pass after it: 16 passed. `tests/test_ship_cleanup.py` and `tests/test_tool_setup.py` pass with them. A real `dart analyze` in a real push snapshot of a small Flutter-shaped project gave "No issues found" with the link, and "Target of URI doesn't exist" with the imported file removed from the main checkout, so a missing file still fails. Timing of `link_local_files` with compiled modules, median of 7 snapshots, two runs each side: this repository old 97.7 and 53.5 ms, new 55.6 and 61.0 ms; fixture with an ignored imported file old 44.5 and 42.0 ms, new 42.0 and 47.5 ms; fixture with no Dart file old 44.0 and 54.6 ms, new 42.1 and 47.4 ms. The runs overlap, so no added time is measurable. The Complete gate result is in the pull request.
E2E: N/A — no user journey of an app changes.
Real service: N/A — the change calls no outside service.
Retro: (1) The fault reached the base branch: the snapshot linked only `.env*` files, and no test built a snapshot of a project whose tracked code imports an ignored file → `tests/test_snapshot_imports.py::test_an_ignored_file_that_tracked_code_imports_is_linked_into_the_snapshot`, which fails on the old code. (2) The first Ready check run failed the lint gate on a branch that the new `.dart` case made equal to the `.env*` case (SIM114) → merged into one condition in `local_files`; a parallel full test run also failed one unrelated process test under load, which passes alone → None — a one-off under load.

Delivery target: Merge
Delivery: Pending — required remote proof.
