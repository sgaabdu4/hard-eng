# Built-in checks for Swift in Flutter apps

Status: Complete

## Outcome + scope

Setup gives a Flutter app that has handwritten Swift in `ios/` or `macos/` one Swift group per platform with these checks: Swift format and lint, Xcode build and tests with a 70% line minimum, duplicate code, and a Swift Semgrep rule file. Impact selection puts only those groups on a macOS runner. Fixes issue #312. Non-goals: plain SwiftPM packages and pure Xcode apps (they keep the `Gap:` line), Swift mutation testing, dead-code checks and a Swift performance report (each group records a reviewed `performance_exception`).

## Repository context

Owners:
- `.hooks/gate_config.py`: languages, required roles, parent-role lookup and `nonproduction_source`. It sits at 995 lines, so Swift rules live in the new `.hooks/swift_setup.py`.
- `.hooks/hard-eng.py`: `production_files`, `prepare_reports`, `reject_test_filters`, `impact`. At 990 lines; each edit is a short call into an owner module.
- `.hooks/reports.py`, `.hooks/coverage_sources.py`: test and coverage readers; Dart's `erased_dart` is the model for files with no executable lines.
- `.hooks/ci_setup.py`, `.github/workflows/hard-eng.yml`: generated workflow and its migrations.
- `.hooks/comments.py`, `.hooks/plans.py`: comment blocks, switched-off checks, test path rules.
- Design and probes: `swift-design.md` in the session scratchpad. Toolchain facts were measured on Xcode 27 with Flutter 3.47.5: `swift format lint --strict` passes the `flutter create` Swift files and fails the macOS `GeneratedPluginRegistrant.swift`; `xcodebuild test` plus `xcresulttool` and `xccov` give the test summary and per-file coverage; a file with no executable lines is absent from the coverage report.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user decided: format, lint, build and test with `xcodebuild`; Flutter `ios/` and `macos/` Swift now, SwiftPM later; the runner is chosen by impact and the `hard-eng` job is never skipped; enforcement starts at once; a small Semgrep rule file with a test for each rule; each Swift group records a reviewed `performance_exception`; duplicates through jscpd; `macos-latest` floats; time budgets come from a real run; warnings are errors only for the app's own targets. The user asked for one PR, a Codex review loop, merge when green and a final report.

## Acceptance + steps

- [x] Detection finds an `ios` or `macos` Swift group only when `Runner.xcodeproj` and authored Swift outside `Flutter/` and `Pods/` are tracked; test folders are not sources → `test_swift_groups_follow_tracked_handwritten_swift`, `test_nested_flutter_app_names_its_platform_folder`.
- [x] Setup writes the gates (`format-lint`, `tests`, `duplicates`, `security`, plus `pods-locked` when a `Podfile` exists), sets `depends_on` to `[]` and `impact_inputs` to the app's pubspec files so an update can install, leaves `performance_exception` for review, and keeps an existing reviewed group → `test_setup_writes_swift_gates`, `test_swift_group_in_a_monorepo_reads_only_its_apps_pubspec_files`, `test_setup_adds_the_pods_gate_only_with_a_podfile`, `test_setup_keeps_a_reviewed_swift_group`.
- [x] A Flutter app with Swift but no Swift group fails; a group without `format-lint`, `tests`, `duplicates` or `security`, or without a performance review, fails; one under `ios/` takes lockfile and vulnerability checks from its Flutter parent, one elsewhere does not → `test_missing_swift_group_fails`, `test_swift_group_needs_its_roles`, `test_swift_group_needs_a_security_scan`, `test_swift_group_needs_a_performance_review`, `test_swift_group_takes_services_from_its_flutter_parent_only`; a group that is not language swift, or that misses a Swift folder in its sources, format, duplicate or security scope, fails → `test_swift_group_must_declare_swift`, `test_swift_folder_added_after_setup_must_be_scanned`, `test_podfile_added_after_setup_needs_the_pods_gate`.
- [x] The tests report fails on a failed result and on failed tests; zero passed tests are reported as no tests → `test_xcode_tests_report_must_pass`.
- [x] Coverage reads the xccov JSON (higher count per file), fails below 70% and when a production file is missing, and accepts a missing file that has no executable code → `test_xccov_coverage_keeps_the_higher_count_per_file`, `test_xccov_coverage_fails_for_a_production_file_missing_from_the_report`, `test_swift_file_without_executable_code_may_be_missing`, `test_coverage_accepts_a_missing_file_with_no_executable_code`, `test_conditional_swift_code_is_never_exempt`, `test_xccov_coverage_keeps_the_larger_denominator_per_file`, `test_swift_production_files_exclude_tests`; the duplicates report accepts Swift → `test_duplicates_report_covers_swift`.
- [x] The generated tests script precaches the Flutter engine, picks a booted iPhone simulator by id (else the first), fails without one, and on macOS fails when Flutter changes project files while preparing → `test_ios_tests_script_picks_a_simulator_by_id`, `test_ios_tests_script_needs_an_iphone_simulator`, `test_macos_tests_script_keeps_the_project_files_unchanged`.
- [x] A Swift test gate with `-only-testing`, `-skip-testing`, test-configuration or `-testPlan` flags is rejected → `test_swift_test_filters_rejected`.
- [x] `impact` prints `runner=macos-latest` when a Swift group is selected, else `ubuntu-latest`, also on the proven-change exit → `test_impact_runner_is_macos_only_for_swift`, `test_impact_prints_the_runner`, updated impact tests.
- [x] A project with a Swift group gets the impact job and the runner expression; a project without Swift keeps its jobs; existing workflows migrate once; customised ones get a note; the mise launcher no longer uses `${…,,}` → `test_swift_workflow_selects_runner`, `test_workflow_without_swift_keeps_its_jobs`, `test_existing_workflow_gains_the_runner_job_once`, `test_customised_workflow_is_left_with_a_note`, `test_launcher_migration`.
- [x] Added `swift-format-ignore`, `XCTSkip`, `.disabled(` inside `@Test(…)` or `@Suite(…)`, `<SkippedTests>`, `<SelectedTests>`, `skippedTests` and `skipped = "YES"` lines fail; Swift comment blocks and assertion loss follow the existing rules → `test_swift_switch_offs_fail`, `test_swift_assertion_loss_fails`, `test_swift_comment_blocks`.
- [x] Each Swift Semgrep rule fires on its fixture line and nowhere else → `test_swift_security_rules` over `tests/semgrep/`.
- [x] A tracked `Package.swift` keeps a `Gap:` line → `test_swiftpm_packages_keep_a_gap_line`.
- [x] README, `gates.md` and `DECISION.md` name the Swift checks → review of the diff.
- [x] On this Mac, a fresh `flutter create` app passes `check`, and each red run fails for its own reason; plugin warnings do not fail the build for SwiftPM or CocoaPods → E2E below.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on origin/main `7781a343` plus this plan exited 0; it reused that commit's passed CI (log `swift-baseline1.log` in the session scratchpad).
Execution: One builder on branch `feature/swift-checks`. Order: prep (remove the pass-through wrapper in `gate_config.py`), red tests, detection and setup, gate validation, readers, comment rules, CI, Semgrep rules, docs, then the end-to-end run on this Mac.

## Risks + recovery

The scoped warnings setting must skip SwiftPM plugin targets and Pods; the end-to-end run proves both and the setting changes if either fails. An Xcode update can change `xcresulttool` or `xccov` keys; the readers fail closed on a missing key. Every Flutter project with Swift fails its check until its Swift group is reviewed (`depends_on`, `performance_exception`); the user accepted this. A real macOS GitHub runner is not available to this task, so the runner design is proven by workflow lint and tests only. Recovery is reverting this branch.

## ux_reference

N/A — hooks, gate configuration and CI; no product appearance.

## Verification

Result: Passed
Evidence: End-to-end on this Mac with Xcode 27, Flutter 3.47.5 and an iOS 18.5 simulator, on a fresh `flutter create` app (`ios` and `macos`) after `setup.py`, with the machine load average between 120 and 190.
- Green: `check --base HEAD` selected only the `ios` group and passed (format-lint 0.2 s, tests 48 s with 10/10 lines, duplicates 0.2 s, security 3 s); the `macos` group passed after one real test (16/16 lines, tests 18 s).
- Red, each for its own reason: bad indentation failed `format-lint` (`[Indentation]`); `let unused = 1` failed `tests` as a compile error from the scoped warnings setting; `XCTAssertEqual(1, 2)` failed `tests` (exit 65, failing test named); eight uncalled functions failed the minimum (10/42 lines); a Swift file outside every target failed with "Coverage report omits production files: Runner/Orphan.swift"; an added `swift-format-ignore` line failed the suppression rule; a fresh `macos` app failed the minimum at 10/16 lines (62.5%) until its delegate had a test.
- Plugin warnings: a local plugin with an unused value failed a plain `SWIFT_TREAT_WARNINGS_AS_ERRORS=YES` build as an error and passed the gate as a warning, for the SwiftPM plugin target and for a CocoaPods target (`pods-locked` also passed, `pod install --deployment`); the app's own `unused` still failed in the CocoaPods app.
- `impact --base HEAD~1` printed `runner=macos-latest` after an `ios/` change and `runner=ubuntu-latest` after a Dart change. The generated workflow passed `actionlint` and `zizmor`; the new launcher printed `mise-darwin-arm64` under `/bin/bash` 3.2, where the old `${RUNNER_ARCH,,}` printed "bad substitution".
- Budgets (measured, loaded Mac): iOS tests 231 s on the first run then 45-67 s, macOS tests 18 s (43 s first), other Swift gates under 5 s, whole `check` for one platform 52-76 s without tool installs. The per-gate limit floor is 600 s. The fixture used `ci_seconds` 1800.
- Codex adversarial review (gpt-6-astra), six rounds. Round 1: a Swift folder added after setup escaped scanning, and CocoaPods ran before Flutter engine artifacts existed; both fixed. Round 2: files under `#if` looked empty to the parse, and Swift files at the platform root were missed; both fixed. Round 3: a custom group without `language: swift` bypassed the roles; fixed. Round 4: a larger denominator was discarded across targets, and Flutter's macOS configuration could rewrite `Package.resolved`; both fixed. Round 5: Flutter migrations could rewrite authored macOS files (fixed with a content check of the platform folder); native dependency vulnerability scanning of `Podfile.lock` and `Package.resolved` was skipped as a new feature nobody asked for (gap, reported). Round 6 approved with no findings. The Hard Eng challenge review then found that a Podfile added after setup needs the pods-locked gate, and the `.disabled(` pattern flagged SwiftUI controls and, once narrowed, missed multi-line traits; both fixed by reading the whole `@Test(...)` or `@Suite(...)` attribute (`test_only_swift_testing_disabled_traits_are_switch_offs`). Later challenge rounds fixed deleted Swift files crashing the rule and parentheses or `.disabled(` text inside a test display name (`test_deleting_a_swift_file_does_not_break_the_switch_off_rule`). The last round's finding, `@Testing.Test(.disabled(…))` written with the module name, is skipped: nobody writes that form and the other spellings are caught.
- Release canary on this Mac (30 installed projects): the first run showed that a new Swift group without `depends_on` made the updater of every Flutter app refuse to install (the new hooks reject an unreviewed multi-package configuration); setup now fills `depends_on: []` and `impact_inputs`. A second run showed that copying the app's own `depends_on` breaks an app that sits in a dependency cycle, so the value stays `[]`.
- A trial on a clone of a real Flutter app with an extension target (nothing pushed): format-lint found swift-format errors in one file, the template test stubs have no tests, and the app targets iOS 26, so the simulator is picked from the newest runtime (a booted iPhone first, else the last listed). Touching a Swift file that holds multi-line comments fails the comment rule.
- Challenge round 9: a Flutter app inside a Dart workspace lost its lockfile and vulnerability checks to the workspace root, which its Swift group did not see, and a local plugin's native folders did not select the Swift group; both fixed (`test_swift_group_in_a_dart_workspace_takes_its_roles_from_the_workspace`, `test_swift_group_watches_the_native_folders_of_local_plugins`). Round 10: the workspace root's pubspec files were not watched, and a plugin added after setup was never watched; both fixed (`test_plugin_added_after_setup_must_be_watched`).
- Repository checks: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates (final run after the last review fix).
E2E: Passed — the runs above, from a fresh app through setup, green checks, six red runs, both plugin builds and the runner output; logs are kept in the session scratchpad.
Not checked: native dependency vulnerability scanning (`Podfile.lock`, `Package.resolved`), a real macOS GitHub runner (needs a test repository), Swift packages outside Flutter apps, Xcode projects with a `.xctestplan`, app extension targets with their own tests.

Delivery target: Merge
Delivery: Pending — PR checks, rebase merge and a green main run.
