# Check Swift in a Flutter app only beyond Flutter's starter files

Status: Ready

## Outcome + scope

A Flutter app's `ios/` or `macos/` folder gets a Swift group only when it holds at least one Swift file in a source folder that is not an unchanged starter file. Template-only folders get no group, and setup removes a group it created earlier for such a folder. Inside a group, unchanged starter files are not production files, like generated files. Non-goals: other Swift layouts, Swift packages, and starter files from tools other than `flutter create`.

## Repository context

Owners: `.hooks/swift_setup.py` (detection, group building, validation), `.hooks/hard-eng.py` `production_files` (expected coverage files), `tests/test_swift.py`.
Starter files are the Swift files `flutter create` writes: `AppDelegate.swift`, `SceneDelegate.swift`, `MainFlutterWindow.swift` and `RunnerTests.swift`; `GeneratedPluginRegistrant.swift` is generated and never counts.
How to tell "unchanged" (decision, with evidence from a copy of 11 real Flutter apps and the Flutter repository history):
- Git history ("never changed since added") is rejected. Real unchanged starter files have 2 to 6 commits (formatting, Flutter migrations, moves), so history calls them edits. A file edited before the first commit looks unchanged, so real Swift would escape the checks.
- Equality with the installed SDK template alone is rejected. Apps made with older Flutter versions hold older template text, so a template-only app would still get a group.
- Chosen: the file's text, with comments and whitespace removed, equals a Flutter template text, either one of the 16 released template versions listed in `swift_setup.py` (taken from the Flutter repository history of the `AppDelegate`, `SceneDelegate`, `MainFlutterWindow` and `RunnerTests` templates), or a template in the installed Flutter SDK, which covers versions newer than the list. It does not depend on history, so migrations, reformatting and older templates still match, while any added or changed statement does not.
- Measured on the 11 real apps: 5 are template-only; 6 keep a group (3 with project-added Swift files, 3 whose `AppDelegate.swift` or `SceneDelegate.swift` holds notification, method-channel or deep-link code).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user decided the three rules (no group for starter-only folders, setup removes a group it made earlier, starter files are not production files) and asked for one PR with the Codex review, challenge, canary and merge flow, and a bounded review loop that fixes only realistic findings.

## Acceptance + steps

- [ ] Starter files are recognised by text across template versions; edits, added statements and renamed files are not → `test_starter_text_matches_flutter_templates`, `test_edited_starter_text_is_not_a_starter`, `test_installed_sdk_templates_count_as_starters`.
- [ ] A template-only folder gets no group; one added Swift file, or an edited `AppDelegate.swift`, creates it; a test-only edit does not → `test_template_only_folder_has_no_swift_group`, `test_project_swift_creates_the_group`.
- [ ] Setup removes a group for a folder that is now template-only, and validation names it → `test_setup_removes_a_group_for_a_template_only_folder`, `test_group_for_a_template_only_folder_fails`.
- [ ] Unchanged starter files are left out of the expected coverage files; edited ones stay in → `test_unchanged_starters_are_not_production_files`.
- [ ] A group's sources are the folders that hold project Swift, so a starter-only `Runner` is not scanned until it is edited → `test_sources_skip_starter_only_folders`.
- [ ] On this Mac a fresh `flutter create` app has no Swift group and passes `check`; one added Swift file or an edited `AppDelegate.swift` creates the group and its gates run → E2E below.
- [ ] The 11 installed Flutter apps are tried with the release canary → report.

## Baseline + execution

Result: Passed
Evidence: main `50083286` passed the Hard Eng workflow on push (run 38961977123).
Execution: One builder on branch `feature/swift-starter-files`: plan, red tests, detection, coverage exclusion, setup removal, then the end-to-end run, review loops and the canary.

## Risks + recovery

A starter file written by a tool other than `flutter create` counts as project code, so the folder gets a group. A project-edited file whose text equals a template (an edit that restores the template) counts as a starter, which is correct. A new Flutter template version is covered by the installed SDK read; if no SDK is installed, the list is the only source and a newer starter would count as an edit until the list is extended. Recovery is reverting this branch.

## ux_reference

N/A — hooks and gate configuration; no product appearance.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — a fresh Flutter app on this Mac: no group and a passing check; then an added Swift file and an edited `AppDelegate.swift`, each creating the group and running its gates → `tests/test_swift.py` for the logic and the recorded run for Xcode.

Delivery target: Merge
Delivery: Pending — PR checks, rebase merge, a green main run and the canary report.
