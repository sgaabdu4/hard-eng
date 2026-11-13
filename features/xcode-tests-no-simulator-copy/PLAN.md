# Xcode tests run on the named simulator, not on a new copy

Status: Complete

## Outcome + scope

Each run of the iPhone tests gate made macOS show a crash window on the maintainer's screen. Xcode started a new copy of the simulator for each run. On its first start, the wallpaper service of the copy crashed, and macOS reported that crash in a window. Now the iPhone branch of the tests command turns parallel testing off, so Xcode uses the named simulator and makes no copy. An installed project whose iPhone tests command lacks the flag is refused, and the refusal names the flag.

Non-goals: a change to the simulator choice, a change to the macOS tests, an automatic edit of the gate file of an installed project.

## Repository context

Owners: `.agents/skills/he/templates/hard-eng.swift.json` (the tests command), `.hooks/swift_setup.py` (`require_swift_groups`).
Same cause: searched the repository for `xcodebuild`. The template holds the only command that starts a simulator; the iPhone and Mac groups share it. No earlier fix of this cause exists.
Single source: the flag text has one owner, `SERIAL_TESTS` in `.hooks/swift_setup.py`. The template holds the command itself, as it holds each other flag.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer reported the crash windows and asked for the cause and a stop.

## Acceptance + steps

- [x] The tests command of a new project passes `-parallel-testing-enabled NO` to `xcodebuild test` → `tests/test_swift.py::test_ios_tests_script_picks_a_simulator_by_id`.
- [x] An iPhone group whose tests command lacks the flag is refused with the flag in the message, and a Mac group is not refused → `tests/test_swift.py::test_iphone_tests_must_run_on_the_named_simulator_not_on_a_copy`.
- [x] The rule reads each form of the Xcode command, and a command without Xcode is not refused → `tests/test_swift.py::test_iphone_tests_rule_reads_each_form_of_the_xcode_command`.
- [x] The Mac tests command gets no flag → `tests/test_swift.py::test_macos_tests_script_keeps_the_project_files_unchanged`.

## Baseline + execution

Result: Passed
Evidence: before the change the four cases of the two tests failed. The system log of a real run in an installed project held the line "Successfully cloned device", and macOS saved one crash report of the wallpaper service for each run: 10 reports in 2 days, each for a different simulator copy.
Execution: one session; tests first, one commit for the repair, one for this plan.

## Risks + recovery

The next update of an installed project with an iPhone group fails its check until the gate file holds the flag. The refusal names the flag, and the repair is one line on the update branch. With parallel testing off, the tests of a large suite can take longer; the real run of 4 tests took 153 seconds. Recovery: revert the repair commit.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: `tests/test_swift.py` passed (86 tests). One real run of the iPhone tests command with the flag in an installed project: exit 0, 4 of 4 tests passed, the system log held no "cloned device" line, each boot line named the simulator that the command chose, and macOS saved no new crash report.
Review: the independent review at 456d4da1 found that the rule read only the text `xcodebuild test` in one argument, and that the shared command also turned parallel testing off for the Mac tests. Both are repaired: the rule reads the joined command, and only the iPhone branch sets the flag.
E2E: N/A — no user journey; the real `xcodebuild test` run proves the flag.
Retro: (1) Escaped bug that real use showed: the tests command let Xcode copy the simulator, and the first start of each copy crashed a system service. No gate can see a crash window of macOS, so the prevention is the rule and its tests → `tests/test_swift.py::test_iphone_tests_must_run_on_the_named_simulator_not_on_a_copy`. (2) The first test run used a Python without the project packages → None — one wrong command, corrected at once; the gate file names the right one.

Delivery target: Merge
Delivery: Pending — the full check, then ship.
