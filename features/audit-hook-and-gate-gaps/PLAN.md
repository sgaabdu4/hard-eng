# Close the hook and gate gaps the audit found

Status: Complete

## Outcome + scope

Eight gaps from the November audit are closed: four proven defects in the hooks, setup and build text, and four places where a check could be switched off or replaced without a failure.

Non-goals:

- The fail-open ending of the three small Claude Code hooks. On old Python they still allow; the session and stop message now says so.
- `for` loops in the polling hook, which stay allowed.
- Flag pinning for required checks. A command that names its tool but adds a flag that hides findings still loads.
- Basic mode, which still requires no language check.
- Findings a gate reports as a refused configuration, such as a missing performance suite. They stay recordable as debt, as `features/crash-never-debt` decided.
- A rule for added `linguist-generated` markers. The coverage message and setup both tell a project to add them.
- Tool config files other than the Gitleaks one, Ruff per-file ignores and renamed test files.
- The release from `develop` to `main`.

## Repository context

Owners: the Python floor is new at the top of `.hooks/hard-eng.py`; the setup retry is `locked_update` in `.hooks/update_runner.py` with `update` in `.hooks/update.py`; `.hooks/polling.py` owns the Bash hook and loads the new `.hooks/wait_text.py`, which reads the command text, only for a command that holds a wait word (the hot-path rule needs patterns compiled once at module level, and every other command must not pay for them); `.agents/skills/he-build/SKILL.md` owns the time limit command and `tests/agent_checks.py` reads it in transcripts; `validate_gate` in `.hooks/gate_config.py` owns gate loading, with wrapper handling in `.hooks/tool_setup.py`; `judge` in `.hooks/debt.py` owns debt passes; `.hooks/comments.py` owns switch-off markers; `reject_test_filters` in `.hooks/hard-eng.py` owns full-suite filters; `.agents/skills/he-ship/SKILL.md` owns the wait-for-CI text.
Same cause: three causes. (1) A check trusts a name and not the thing named: required roles are matched by role name, and debt entries by key. `features/crash-never-debt` fixed one case of it (helped); searched `validate_group`, `validate_required_checks` and every `judge` caller, and the two places fixed here are the ones left. (2) A marker list misses a tool the gates run: `features/security-marker-switch-offs` added the Semgrep and Gitleaks markers (helped) and left out the other scanners; searched every pattern in `comments.py` against the tools in the four templates and the shared gates. (3) A text match reads words as commands: `features/no-foreground-poll` added the hook (helped) and matched the words anywhere in the command; searched the three small hooks, and only `polling.py` matches free text. The setup retry, the Python floor, the time limit command and the ship wording have no earlier fix.
Single source: the Python floor has one value, the new guard in `.hooks/hard-eng.py`; a test reads `requires-python` in `pyproject.toml` and the README requirement line against it (searched `.hooks/`, `setup.py`, `setup.sh`, `README.md`, `pyproject.toml`). The role-to-tool table has one owner in `.hooks/tool_setup.py`, and the shared-role lookup in `validate_required_checks` reads it instead of its own list. The time limit command has one copy in `he-build/SKILL.md`; the transcript pattern in `tests/agent_checks.py` accepts both forms. Marker patterns stay in `comments.py` and filter flags in `reject_test_filters`; no other copy exists (searched `.hooks/` and `.agents/skills/`).
Escaped bug: the old Python crash, the setup retry, the polling false denials and misses, and the hand-written debt pass are on the base branch. The test gate should have caught each. Each gets a case that fails on `develop` 2218082d before its fix.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Human-loop. The maintainer asked for both groups of audit findings to be fixed, and on 2026-11-10 approved this plan with its three recommendations: build, commit, push, one PR into `develop` and merge when CI is green. The release to `main` is not approved here.
Decided (1): keep the debt record as designed and close only the hand-written entry gap. The earlier plan made refused configurations recordable on purpose, so the audit finding was wrong on that point.
Decided (2): the required-check rule is "the command names its role's tool". It stops a swapped command such as `true`. It does not stop a command that names the tool and hides its result; that needs flag rules per tool, which is a larger change.
Decided (3): leave added `linguist-generated` markers alone. The alternative is to fail a marker added for a file that existed before the change, but that contradicts the fix the coverage message gives.

## Acceptance + steps

- [x] With `python3` older than 3.12, `stop` blocks once with a plain reason and then lets the turn end, `session` prints the reason, and every other command exits non-zero with it, with no traceback → `tests/test_hook_setup.py::test_old_python_gets_a_plain_refusal_before_any_import`.
- [x] The floor in the guard matches `requires-python` and the README line → `tests/test_hook_setup.py::test_python_floor_has_one_value`.
- [x] A setup run retries an update that a background run remembered as refused → `tests/test_update_runner.py::test_setup_retries_a_remembered_refusal`.
- [x] A background run still skips a remembered refusal → `tests/test_update_runner.py::test_background_update_does_not_repeat_a_refusal_until_inputs_change`.
- [x] A command that holds sleep or loop words only as data is allowed: a search for the word, a commit message, a heredoc body that no interpreter runs (also when its start line names an interpreter only inside a quote or a path), and a short sleep before a search for a loop word → `tests/test_polling.py::test_sleep_and_loop_words_as_data_pass`.
- [x] Hidden long waits are denied: sleeps in one command that total 30 seconds or more, in the shell or in inline Python or Perl; a wait in a quote or heredoc that a shell, Python, Perl, Ruby, Node, `ssh` or `eval` runs; a loop inside `$(...)` in double quotes; and a loop after a comment that holds an apostrophe → `tests/test_polling.py::test_foreground_sleep_wait_is_denied`.
- [x] Odd shell text, such as an open quote or an unclosed heredoc, gets a decision and never a crash → `tests/test_polling.py::test_odd_shell_text_never_crashes_the_hook`.
- [x] The documented time limit command exits 127 when its program is missing → `tests/test_skill_links.py::test_documented_time_limit_command_fails_on_a_missing_program`.
- [x] A transcript that runs `check` under the new time limit command still counts as a check run → `tests/test_agent_checks.py::test_workflow_is_judged_from_recorded_actions`.
- [x] A check with no report, in a role its group's language requires, fails to load when its command does not name that role's tool; the message gives the role, the tool and the command. A group with no language is not affected → `tests/test_gate_tools.py::test_required_check_must_name_its_tool`.
- [x] A shared workflows, CI security or shell check with no report must name its tool in the same way → `tests/test_gate_tools.py::test_a_shared_scan_must_name_its_tool`.
- [x] Wrapped commands still load: `uvx` with a version, a Bun script and a shell script that runs the tool → `tests/test_gate_tools.py::test_wrapped_tool_commands_load`.
- [x] This repository's gate file and all four shipped templates load → `tests/test_gate_tools.py::test_own_gates_and_shipped_templates_name_their_tools`.
- [x] A hand-written debt entry for a tests, lockfiles or secrets gate does not pass that gate → `tests/test_debt.py::test_hand_written_debt_never_passes_tests_lockfiles_or_secrets`.
- [x] An added line fails when it holds an inline ignore marker of jscpd, Fallow, ShellCheck or zizmor, a Dart coverage ignore marker, or a skip shape the list missed (unittest skips, a module-level skip or a module switched off for collection, skip-each and skip-if forms, a solo test, a Swift test enabled only on a false condition) → `tests/test_comments.py::test_added_switch_off_fails_naming_file_line_and_pattern`.
- [x] An added entry in a Gitleaks config file fails like an entry in the Gitleaks ignore file → `tests/test_comments.py::test_added_switch_off_fails_naming_file_line_and_pattern`.
- [x] A `skip:` argument counts only in a test file. Dart keeps its present shape there. JavaScript counts `skip:` only with `true` or a text reason and `only:` only with `true`, so a paging value such as `skip: 10` is allowed. Outside test files the argument is allowed in both. A helper class that opts out of collection is also allowed → `tests/test_comments.py::test_skip_argument_counts_only_in_test_files`.
- [x] The full-suite gate refuses flags that leave out test paths or run one shard or one project → `tests/test_test_filters.py::test_path_and_shard_filters_are_rejected`.
- [x] The ship skill no longer tells the agent to turn on auto-merge for a task PR; the wait follows HE-NO-FOREGROUND-POLL → N/A — guidance wording; the proof is the Reader check recorded in Verification.
- [x] The rule text matches the code: the HE-NO-FOREGROUND-POLL and HE-NO-SWITCH-OFF entries in the requirements reference, and the template paragraph in the gates reference → N/A — wording; the proof is the Reader check recorded in Verification, and `check` keeps the registry valid.
- [x] The Bash hook costs less for a command with no wait word, and the Stop and session start hooks show no change beyond noise. A command that holds a wait word costs about 0.5 ms more, and about 1.5 ms more where Python writes no bytecode, because its text is now parsed. The approved plan said no hook gets slower, so the maintainer decides on this cost before the merge → N/A — no test measures hook start time (`tests/test_gate_speed.py` covers gate order, `tests/performance` covers process counts) and timing depends on the machine; before and after medians go in Verification.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on the tree that `main` f9e23e09 and `develop` 2218082d share: exit 0 in 287 s, 20 gates, 2,363 tests. `check --plan-stage Draft --base HEAD` and `check --plan-stage Ready --base HEAD` on this branch: exit 0. Probes on that tree show the defects: the stock Python 3.9 stops at `import tomllib` with a traceback and exit 1; the time limit command exits 0 for a missing program; the loader accepts `true` as the format, lint and types commands; `judge` passes a failing tests gate from a hand-written entry.
Execution: one builder, this session. Slices run in the order above, each with its failing test first and its focused tests after. Skill text changes get a Reader check. A fresh Opus reviewer reads the final diff, and the cross-agent `challenge` runs on the final HEAD before merge, because the change is big.

## Risks + recovery

- An installed project whose required check has no report and does not name its role's tool fails at its next Hard Eng update, until that gate names the tool. Recovery: fix that gate in the project, or revert the commit.
- A project that adds a line to its Gitleaks config file, or adds one of the new markers, now fails. Lines that existed before the change are not flagged. Recovery: fix the finding instead, or revert the commit.
- The polling hook reads shell text with patterns, not a full parser. A miss allows a wait; it cannot block a command by a crash, because the hook ends open. The denial and allow cases above are the proven set.
- A project that runs an equal tool under another name (for example the Flutter analyzer command, the stand-alone Swift formatter or a framework type checker) must change that gate to the template's command. A test gate that leaves a folder out with a path flag must drop the flag.
- A machine with old Python now gets one blocked stop per turn with the reason, where it had a silent pass before. Recovery: put Python 3.12 or later first on `PATH`.

## ux_reference

N/A — hook, gate and command behavior with no visual surface.

## Verification

Result: Passed
Evidence: each new test failed on `develop` 2218082d before its fix and passes after it. Focused runs: `tests/test_hook_setup.py` 22 passed; `tests/test_update_runner.py` 35; `tests/test_polling.py` 35; `tests/test_skill_links.py` with `tests/test_agent_checks.py` 63; `tests/test_gate_tools.py` 17; `tests/test_debt.py` with `tests/test_adoption.py` 78; `tests/test_comments.py` 205; `tests/test_test_filters.py` with the runner and Swift files 214. One whole-suite run after the tool rule: 2,394 passed and 1 fixture failed, which named `biome` with no subcommand and now names it in full. The stock Python 3.9 on the build machine prints the plain reason for `stop`, `session` and `check` with no traceback. Full check on the final tree: `check --plan-stage Complete` exit 0 with 20 gates and 2,462 tests. Three earlier full runs failed, in the switch-off scan, in `security` and in `declarations`; the Retro lists each.
Speed, old code against new, alternating runs. The Bash hook as a whole process, 400 runs, median, with bytecode present for the helper: a command with no wait word 19.86 to 19.62 ms; one that holds a wait word 23.74 to 24.27 ms; a real wait 23.11 to 23.59 ms. The same with no bytecode for the helper, as in a host that tells Python not to write it: 20.13 to 19.92 ms, 21.11 to 22.66 ms and 19.16 to 20.52 ms. Load and decision only, median of 3,000, bytecode present: 302 to 117 microseconds with no wait word and 301 to 580 microseconds with one; the seven patterns cost 335 of those microseconds. Entry start, 300 runs, mean of the lowest quarter: 86.60 to 86.65 ms. Session start median 543 to 540 ms, Stop with nothing changed 269 to 270 ms, Stop loop guard 114.2 to 114.6 ms, all inside the run-to-run noise of about 3 ms. The new tool rule adds 0.09 ms to one load of 20 gates.
Reader check: a reader that did not write the text compared old and new wording in two passes. Pass 1 quoted nine sentences and seven mismatches with the code; pass 2 quoted four sentences and three mismatches. Each was reworded or the code was changed to match. Left as is, with the reason: text after the word `eval` used as an argument is counted (a rare false denial), and a heredoc cannot feed `eval`.
Review: a fresh reviewer read the diff and ran probes. Fixed from its report: a plan line that named a missing test; waits the old hook denied and the first version allowed (an apostrophe in a comment, a loop inside `$(...)` in double quotes, Ruby and Node inline code); a heredoc kept because its start line named an interpreter in a quote or a path; a helper class that opts out of collection; a data value named `only`; a capital `SkipTest` and a bare skip decorator. Left as is, with the reason: `from time import sleep` inside inline Python (rare), and a traceback for `stop` input that is not an object on old Python (the hosts always send an object).
E2E: N/A — no user journey changes; each behavior is a command or hook result that its test runs directly.
Retro: these items, each sorted by HE Learn's Retro rows.

- Stop hook, types: the new test file built a group with the wrong type → fixed at once; step: HE Build's focused checks run the type check on each new file. None further — the check ran at the first stop.
- The wait hook denied two of the builder's own commands that only held wait text → `tests/test_polling.py::test_sleep_and_loop_words_as_data_pass`.
- Whole-suite run: one fixture failed the new tool rule → None — the rule worked as designed and the fixture now names its tool.
- Reader passes: rule text did not match the code → wording fixed, and the code cases are in `tests/test_polling.py::test_foreground_sleep_wait_is_denied`. None further — the existing Reader step caught it.
- Review: the first wait hook version let through waits the old hook denied → `tests/test_polling.py::test_foreground_sleep_wait_is_denied` and `tests/test_polling.py::test_sleep_and_loop_words_as_data_pass` hold each case.
- Review: two patterns flagged ordinary code → `tests/test_comments.py::test_skip_argument_counts_only_in_test_files`.
- Review: a plan line named a missing test → None — the Complete check refuses such a line.
- Lint: an unwrapped two-part string in a test list → fixed at once. None — the focused lint run caught it.
- Planning review: a sentence about other projects in this public plan → removed before the first commit; rule: AGENTS.md publication privacy.
- Speed: the hot-path rule and the hook speed rule pull apart in the wait hook. Patterns compiled at module level cost every command, and patterns compiled on demand fail the hot-path rule → the patterns moved to a helper that loads only for a command with a wait word. None further — no test can hold a budget this small; the numbers are above, and the wait-word cost goes to the maintainer.
- Full check, switch-off rule: a new test row held a marker as plain text → the text is split in the test. None — the rule worked as designed.
- Full check, declarations: the new helper module was missing from the first-party list in `pyproject.toml` → added. None — the check caught it.
- Full check, security: seven hot-path findings in the wait hook, found late because the builder did not run `hot-paths` on the touched files → fixed in the helper; step: HE Build's focused checks already name that command.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, and the maintainer's answer on the wait-word cost before the merge.
