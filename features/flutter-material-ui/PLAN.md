# The Flutter starter uses the material_ui package

Status: Complete

## Outcome + scope

A new Flutter project passes its full check with Flutter 3.50.0. That release marks `package:flutter/material.dart` as deprecated, and the starter imported it.

1. The starter imports `package:material_ui/material_ui.dart` and lists `material_ui` in its pubspec. The app passes the delegates of `material_ui`, because the Material widgets now read their texts from that package.
2. The main file that `flutter gen-l10n` writes is excluded from the analysis. Flutter 3.50.0 writes two deprecated delegates into that file, and no generator option changes it ([flutter issue 191072](https://github.com/flutter/flutter/issues/191072)). Setup writes the exclusion, and the exclusion rule accepts only that one file.

Non-goals: a change of the `package:flutter/widgets.dart` imports, which are not deprecated; an exclusion of the per-language files or of other files in that folder; a pin of an older Flutter in CI; the test tools of the Flutter skill source.

## Repository context

Owners: `.agents/starters/flutter/` (`pubspec.yaml`, `lib/app.dart`, the counter screen); `.hooks/dart_boundaries.py::localization_file`, `::localization_exclusions`, `::add_exclusions`; `.hooks/project_setup.py::validate_dart_exclusions`; `setup.py::configure_dart`, `::localization_outputs`.
Same cause: the cause is an upstream release, Flutter 3.50.0 of 2026-11-09. Searched the starters and the shipped skills for `flutter/material.dart` and `flutter/cupertino.dart`: two starter files, both changed. Test fixtures hold the import as a plain string and no analyzer reads them.
Single source: the defaults of `l10n.yaml` (output folder and file name) live only in `dart_boundaries.localization_file`. Setup's list of generated files and the exclusion both call it. `add_exclusions` is the one function that adds an exclusion; it had the name `exclude_nested_packages`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The owner asked on 2026-11-13 to move away from `material.dart`, and gave full authority for design, merge and release.
Decisions:

1. The generated file is excluded, with proof that it is generated. An ignore comment in the file header and an `errors:` entry are suppressions, and Hard Eng refuses both. The exclusion needs the `linguist-generated` mark that setup already writes for this file, so a hand-written file at that path is refused.
2. A project that later changes the output folder or file name in `l10n.yaml` removes the old exclusion entry by hand. The refusal names the entry and the options file. Setup does not track old paths; the entry of a nested package that loses its `types` check has the same rule.

## Acceptance + steps

- [x] Only the main gen-l10n file, marked generated, can be excluded; a per-language file, another file, a folder pattern, a package with no `l10n.yaml` and a hand-written file are refused → `tests/test_dart_localization.py::test_dart_exclusions_accept_only_the_main_localization_file`
- [x] Setup writes the exclusion for a root package and for a nested package with a custom output file, its own check accepts it, and a second run changes nothing → `tests/test_dart_localization.py::test_dart_setup_excludes_the_main_localization_file_and_its_own_check_accepts_it`
- [x] A new Flutter project passes its full check with Flutter 3.50.0 → N/A — no unit test can run Flutter; the proof is the `scaffold-flutter` new project of `release_canary.py`, which CI runs on Linux and macOS

## Baseline + execution

Result: Passed
Evidence: the starting code is the base branch at af5c7ea4, and the Hard Eng check run of that commit passed. The new-project job runs only when installed files change, so it first met Flutter 3.50.0 on this branch and failed with four deprecation findings.
Execution: one builder; the failed new-project job is the first proof, then the two tests fail before the code.

## Risks + recovery

- A project that removes the `linguist-generated` line for its main gen-l10n file gets a refusal for the exclusion. Setup writes the line again.
- The generated file is no longer analyzed. It holds generator output only, and the per-language files stay in the analysis.
- The starter needs Flutter 3.47 or newer, the minimum of `material_ui`. A new project always uses the newest Flutter.
- Recovery: revert the two commits; the starter then fails its check again on Flutter 3.50.

## ux_reference

N/A — the starter screen looks the same; only its import changes.

## Verification

Result: Passed
Evidence: a scratch project from the old starter gave the same four findings with Flutter 3.50.0 on this Mac. With the new starter and the exclusion, the analyzer reports no issue and the two starter tests pass. The two new tests failed before the code for the named cause and pass now. The `scaffold-flutter` new project passed its full check on this Mac.
Review: the independent challenge ran on the final commit.
E2E: N/A — no user journey changes; the starter's widget test taps the button in the real app.
Retro: (1) The new-project job failed on the pull request, four days after the Flutter release → Outside cause: an upstream release; the job caught it at the first change of installed files, which is its purpose.

Delivery target: Merge
Delivery: Pending — the pull request into `develop`, its checks, the release pull request into `main` and the release run.
