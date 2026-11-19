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
- Rule, no scan and no added time unless an ignored Dart file could be linked (none exists, a tool of the project writes it, or the commit already holds it): In scope — Link speed is recorded in Verification: no scan without a candidate, and the measured added time with one
- Rule, a generator in the snapshot writes through a link into the main checkout, so its output is not linked: In scope — A file that a tool of the project writes (`*.g.dart`, `*.freezed.dart`, `*.mocks.dart`, the gen-l10n files named by `l10n.yaml`) is not linked and starts no scan
- Rule, Dart imports resolve as Dart resolves them: In scope — An import resolves the way Dart resolves it

## Repository context

Owners: `local_files`, `link_local_files` and `placed_by_hard_eng` in `.hooks/ship_actions.py` own what a new worktree and the push snapshot get from the main checkout. `prepare_checkout` runs them for the snapshot and for the `post-checkout` hook.
Same cause: the cause is a snapshot that holds only tracked files while the commit's code needs a local file that git ignores. Earlier fixes: the `.env*` and local settings links (before this plan) helped for those names only. Searched `.hooks` for other readers of ignored files in a snapshot: `update_submodules` (submodules, not ignored files) and `drop_derived_data` (cache removal). No resolver of Dart imports exists in `.hooks`: `dart_boundaries.py` reads analysis options, and `dependency_graph.py` and `coverage_sources.py` list source suffixes without reading imports. Other languages keep the same gap and are a stated limit. A file in a wholly ignored folder (the folder matches an ignore pattern) shows in the ignored listing as the folder, so it is not linked; this is a stated limit. An ignored file that a file pattern names is listed as the file, even when it is alone in its folder; the link makes the missing parent folder in the snapshot. Imports of a sibling package in a workspace (`package:<other>/...`) are not linked, because the request names this package only. A block comment that holds an import line at the start of a line can link an unneeded file; this is a stated limit, declined as a narrow case. The extra link is not always harmless: if the linked file imports a package that the commit removed, the analyzer reports an error that the clean commit does not have. A `name:` line whose quoted value sits on the next line, after a comment line, is not read; no pubspec is written that way, and `name: app # note` resolves, so this is declined. The declined review findings are recorded under Risks + recovery.
Single source: the ignored listing has one owner, `local_files`; the new Dart candidates come from it, with no second listing. The link and the placed check share it, so `placed_by_hard_eng` needs no import scan. Searched `.hooks` and `tests` for other `import`/`export`/`part` readers: `agent_hooks.py` and `comments.py` match import lines for other purposes and give no path resolution to reuse.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The maintainer gave this task and the design limits in the request; no release or merge is part of this builder's task.
Decisions:

1. The import scan runs only in `link_local_files`, and only when an ignored `.dart` file is a candidate: absent from the checkout and not written by a tool of the project. A project with none adds no process and reads no file. A new linked worktree runs it once, from the `post-checkout` hook, which exits at once unless the previous head is all zeros; a branch switch does not run it.
2. `placed_by_hard_eng` does no scan. A link stays Hard Eng's own after the task removes the import, because it compares the link with the main checkout's file.
3. The scan reads only tracked Dart files of the snapshot. It never reads the ignored file.

## Acceptance + steps

- [x] A tracked Dart file imports an ignored file that exists in the main checkout: the snapshot holds a link to it → `tests/test_snapshot_imports.py::test_an_ignored_file_that_tracked_code_imports_is_linked_into_the_snapshot`
- [x] A missing imported file stays missing → `tests/test_snapshot_imports.py::test_a_missing_imported_file_stays_missing_in_the_snapshot`
- [x] An ignored file that nobody imports is not linked → `tests/test_snapshot_imports.py::test_an_ignored_file_that_no_tracked_file_imports_is_not_linked`
- [x] An ignored file that only an untracked file imports is not linked → `tests/test_snapshot_imports.py::test_an_ignored_file_that_only_an_untracked_file_imports_is_not_linked`
- [x] The link stays placed by Hard Eng → `tests/test_snapshot_imports.py::test_the_link_stays_placed_by_hard_eng_after_the_import_is_removed`
- [x] An import resolves the way Dart resolves it → `tests/test_snapshot_imports.py::test_an_import_resolves_the_way_dart_resolves_it`
- [x] An imported ignored file that is alone in its folder is linked and the folder is made: the status lines equal the placed set and cleanup keeps nothing → `tests/test_snapshot_imports.py::test_an_ignored_file_alone_in_its_folder_is_linked_with_the_folder_made`
- [x] An imported ignored file whose folder the pushed commit removed is linked the same way → `tests/test_snapshot_imports.py::test_an_ignored_file_is_linked_when_the_commit_removed_its_folder`
- [x] A file that a tool of the project writes (`*.g.dart`, `*.freezed.dart`, `*.mocks.dart`, the gen-l10n files named by `l10n.yaml`) is not linked and starts no scan → `tests/test_snapshot_imports.py::test_files_that_a_generator_of_the_project_writes_are_not_linked_and_not_scanned_for`
- [x] No scan runs when the commit already holds every candidate → `tests/test_snapshot_imports.py::test_the_scan_does_not_run_when_the_commit_already_holds_every_candidate`
- [x] Link speed is recorded in Verification: no scan without a candidate, and the measured added time with one → N/A — a timing record of two runs each side, not a test

## Baseline + execution

Result: Passed
Evidence: the base is origin/develop at a7909cdb; `tests/test_ship_cleanup.py` passed on it.
Execution: one builder; failing tests first, then the change, the static gates, the Complete gate and the independent review.

## Risks + recovery

- A wrong resolution links a file nobody needs, or misses one; the check then fails as before. Recovery: revert the commit; no data step.

Review declined: a comment line between `name:` and a quoted value on the next line is not read :: no pubspec is written that way, and `name: app # note` already resolves.
Review declined: a block-commented import at the start of a line can link an unneeded file :: a narrow case; the real limit is stated in Repository context, including the case where the linked file imports a package that the commit removed.
Review declined: the made folder can follow a link that the pushed commit put in place of the generated folder, and write outside the worktree :: far-fetched; an existing parent folder that is a link was followed by the link step before this change in the same way.
Review declined: a made folder can block the clone of a submodule that the pushed commit adds at that path :: far-fetched; it needs a commit that turns the folder into a submodule while the main checkout still holds the ignored file and tracked code imports it.
Review declined: a quoted key `"output-localization-file":` in `l10n.yaml` falls back to the default name :: far-fetched; no project quotes a key in that file, and the installed project that ignores gen-l10n files writes it plain.
Review declined: the gen-l10n name filter also drops an individually ignored hand-made file with the same stem outside the output folder :: far-fetched; it needs a hand-made ignored file named like the localization output in another folder, and the failure is the old one, a missing import.
Review declined: when the task branch ignores the whole generated folder and the main checkout ignores only the file, cleanup keeps the worktree :: the refusal is safe and names the path; the two checkouts must hold different ignore rules for the same path.

## ux_reference

N/A — no screen changes.

## Verification

Result: Passed
Evidence: the new tests failed before the change (15 of 16 failed; log kept in the builder's scratch folder) and pass after it: 16 passed. `tests/test_ship_cleanup.py` and `tests/test_tool_setup.py` pass with them. A real `dart analyze` in a real push snapshot of a small Flutter-shaped project gave "No issues found" with the link, and "Target of URI doesn't exist" with the imported file removed from the main checkout, so a missing file still fails. Timing of `link_local_files` with compiled modules, median of 7 snapshots, two runs each side: this repository old 97.7 and 53.5 ms, new 55.6 and 61.0 ms; fixture with an ignored imported file old 44.5 and 42.0 ms, new 42.0 and 47.5 ms; fixture with no Dart file old 44.0 and 54.6 ms, new 42.1 and 47.4 ms. The runs overlap, so no added time is measurable. After the independent review at 5695b270, a scratch repository with real git (2.56) showed two cases. (i) An ignored file alone in its folder, named by a file pattern: the candidate list holds the file (git lists the folder and the file), and the parent check fails, because the snapshot has no such folder. A folder that matches an ignore pattern lists as the folder only; that stays the stated limit. (ii) The main checkout tracks a file in the folder and the pushed commit removed it: the candidate list is right and the parent check fails. So the parent check was the only fault. `--directory` stays, and no new scan runs. The fix makes the parent folder of an imported Dart link. Both new tests failed before the fix and pass after it; the 52 tests of `tests/test_snapshot_imports.py` and `tests/test_ship_cleanup.py` pass. Git shows the made folder as the file line `!! lib/gen/key.dart`, so `placed_by_hard_eng` matches the status lines and `unchanged_checkout` keeps nothing. A real `dart analyze` in a real push snapshot of that layout gave "No issues found" with the link, and "Target of URI doesn't exist" with the file removed from the main checkout. Timing of `link_local_files` with compiled modules, median of 8 snapshots, two runs each side, old is origin/develop: this repository old 67.8 and 67.0 ms, new 71.2 and 67.3 ms; fixture with no Dart file old 75.3 and 62.0 ms, new 76.1 and 79.3 ms; Flutter-shaped fixture of 1500 tracked Dart files and two ignored imported files, with large ignored build folders: old 57.2 and 62.1 ms, previous head 213.8 and 183.2 ms, new 325.5, 218.0, 199.6 and 188.5 ms in four runs. The parent folder fix adds no time over the previous head. The import scan itself runs only when an ignored Dart file exists, and it does add time there: about 130 to 160 ms on that fixture of 1500 tracked Dart files, almost all of it opening the files of the new snapshot (cProfile: 96 of 174 ms in `open`). A project with no ignored Dart file adds no scan. The review at 99a5b3e1 found that `local_files` still called `is_file` on every ignored entry (12 calls on this repository against 0 on origin/develop); the name test now runs first, so the count is 0 again, and three later runs of the no-Dart fixture overlap: old 55.1, 67.3 and 68.5 ms, new 63.4, 54.1 and 57.1 ms. A prefilter with `git grep` for the candidates' file names was tried: it cut the scan to about 50 ms when few files import a candidate, but it added a process and made the case worse when many files name a candidate (ignored generated files), so it was not kept. The independent review at 99a5b3e1 named this as a slowdown, and the scope row above now says so. After the coordinator's review at 28f04f74: the `post-checkout` hook runs the link step only for a new linked worktree (the launcher exits unless the previous head is all zeros), never on a branch switch. Every push snapshot and new worktree starts with no link, so a skip for an existing link helps only when the commit holds the file itself; that case now starts no scan. A real `build_runner` run (json_serializable) in a snapshot that held a link wrote through the link and replaced the main checkout's copy of the generated file, so files that a tool of the project writes are no longer linked. In the installed Dart projects of this Mac, only one ignores Dart files (235, all generated by `build_runner` or gen-l10n, which its gate regenerates), so the scan now starts nowhere there; no installed project has an ignored hand-made Dart file that tracked code imports. Timing of the whole `post-checkout` run in a new worktree, compiled modules, median of 8, two runs each, on a fixture of 1500 tracked Dart files with 235 ignored generated files: develop 705.3 and 570.7 ms, previous head 1502.2 and 904.4 ms, new 539.4 and 377.4 ms; with one ignored imported file: develop 251.4 and 238.1 ms, previous head 403.0 and 359.7 ms, new 411.3 and 339.9 ms (the scan, and the link it brings). The Complete gate result is in the pull request.
E2E: N/A — no user journey of an app changes.
Real service: N/A — the change calls no outside service.
Retro: (1) The fault reached the base branch: the snapshot linked only `.env*` files, and no test built a snapshot of a project whose tracked code imports an ignored file → `tests/test_snapshot_imports.py::test_an_ignored_file_that_tracked_code_imports_is_linked_into_the_snapshot`, which fails on the old code. (2) The first Ready check run failed the lint gate on a branch that the new `.dart` case made equal to the `.env*` case (SIM114) → merged into one condition in `local_files`; a parallel full test run also failed one unrelated process test under load, which passes alone → None — a one-off under load. (3) The first version skipped a link when the snapshot had no parent folder, and no test covered an ignored file that is alone in its folder or whose folder the commit removed → `tests/test_snapshot_imports.py::test_an_ignored_file_alone_in_its_folder_is_linked_with_the_folder_made` and `::test_an_ignored_file_is_linked_when_the_commit_removed_its_folder`, which fail on the old code. (4) The first version linked every imported ignored Dart file, including generated parts, and no test ran a real generator in a snapshot that held a link → `tests/test_snapshot_imports.py::test_files_that_a_generator_of_the_project_writes_are_not_linked_and_not_scanned_for`, which fails on the old code. A generator-written file is named by its double extension or by `l10n.yaml`; a hand-made ignored file with a double extension, such as `env.local.dart`, is not linked, which is a stated limit.

Delivery target: Merge
Delivery: Pending — required remote proof.
