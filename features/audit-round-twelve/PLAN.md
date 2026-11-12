# Make the hook script a small launcher, refuse shard settings that the merge cannot follow, and audit round twelve

Status: Ready

## Outcome + scope

Each hook event and each command starts faster: the hook script becomes a small launcher, and its body moves to a module that Python loads from its cache. A shard gate refuses a test path in the pytest settings, and each option or variable that moves the settings of pytest or coverage.py, so the merge cannot skip a project's own coverage minimum. Then a new audit of the released code runs in sealed copies of real projects, and each fault that it reproduces in normal use gets a slice in this plan. Non-goals: a time weight for the shard split; a deal of files to shards that moves few files after an edit; a copy check of JavaScript, Dart and Swift test files; a settings load with no Git start for attributes (measured and rejected, see Decisions).

## Repository context

Owners: `.hooks/hard-eng.py` stays the entry point that each hook, workflow and installed command names; after slice 1 it holds only the Python floor refusal, the early exit of a `session` or `stop` event and the start of the module. `.hooks/gate_runner.py` (new) owns `check`, the gate runs and the command line. `.hooks/ship_actions.py` owns `push_check`, which reads the text of a pushed revision for two options. `.hooks/shards.py` owns each refusal of a shard gate. `.agents/skills/he/references/gates.md` names the owner of the test filter list. Evidence: Python compiles a script on each run and never caches it: 2.81 ms at 877 lines, 2.94 ms at 935 lines; a compiled module of the same code loads in 0.10 ms. A prototype of the launcher gave 4.0 to 5.8 ms less for each session start and each clean Stop, with each timing copy equal to its base. The independent review of round eleven reported the two shard faults on its final commit.
Same cause: two causes. (1) Code that runs on each hook event sits in a file that Python cannot cache. Earlier fix: the small own scripts of the tool hooks (`failures.py`, `polling.py`, `previews.py`) and the early exit of the hook script for a `session` or `stop` event; they helped, but Python still compiles the whole script before its first line runs. Other places, searched: each file that a hook command or an installed command starts by path; slice 1 lists them with their line counts, and each one above 100 lines gets the same form or a stated reason. (2) A shard gate follows settings that it does not read. Earlier fix: round eleven refused a test path in the tests command and read `addopts` from the one settings file that pytest reads; that helped for the command and for the default files only. Other places, searched: each option and variable that moves the settings file or the arguments of pytest, or the settings file of coverage.py; slice 2 refuses each one, so no reader of a moved file exists.
Single source: the list of refused shard options and variables has one owner, a constant in `.hooks/shards.py`; the refusal text names the option from that list. The names of the two options that `push_check` looks for stay in `.hooks/ship_actions.py`; it reads the launcher text and the module text of the pushed revision through one helper. The line limit of the launcher has one owner, its test. Paths searched for other copies: `.hooks/*.py`, `tests/*.py`, `setup.py`, `.agents/skills/he/references/*.md`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn. On 2026-11-11 the maintainer said that speed is important, that each change is timed old against new, and that the builder makes the decisions.

Decided:

1. The path `.hooks/hard-eng.py` does not change. Each hook, workflow, Git hook and installed step names it.
2. The launcher keeps the syntax of Python 3.9 and loads no other file before the floor check, so an old `python3` still gets the plain refusal.
3. The launcher starts the module only when it runs as a program. A load of the launcher as a module runs nothing; each test that needs the functions loads `gate_runner`.
4. A shard gate refuses a moved setting; it does not read it. A reader would copy more of pytest, pytest-cov and coverage.py, and each allowed value would need a comparison with the real tools. The refused set: `-c` and `--config-file`, `-o addopts` and `--override-ini addopts`, `--cov-config`, `--cov-precision`, and the variables `PYTEST_ADDOPTS` and `COVERAGE_RCFILE`. Local count on 2026-11-12: none of 40 checkouts uses one of them.
5. A test path in `addopts` is refused with the same text as a path in the command, and the text names the settings file.
6. No settings load without the Git attribute lookup. Measured on this repository: the lookup takes 9.5 ms, of which 7.1 ms is the Git start. A skip is correct only when no attribute source exists, and Git has at least five: a `.gitattributes` file in each folder, the index, `info/attributes` of the common folder, the file that `core.attributesFile` names, and a system file whose path depends on the Git build. A wrong skip changes which files count as generated.
7. No change to the shard split in this plan. Three reviews read it in round eleven. Local test times show that file size is a weak weight, but a time weight needs stored data.

## Acceptance + steps

Constraints: the limit is 1,000 lines for each file. `.hooks/hard-eng.py` has 935 lines before slice 1; after it, the launcher has at most 45 lines and `.hooks/gate_runner.py` at most 935. `.hooks/shards.py` has 535 lines before slice 2. Each hook path gets no added work: slice 1 is timed old against new, two passes, each timing copy equal to its base.

Slice 1, the launcher (`.hooks/hard-eng.py`, `.hooks/gate_runner.py`, `.hooks/ship_actions.py`, `pyproject.toml`, `tests/conftest.py`, `.agents/skills/he/references/gates.md`):

- [ ] The hook script holds at most 45 lines and defines no function → `tests/test_hook_setup.py::test_the_hook_script_is_a_small_launcher`
- [ ] An old `python3` still gets the plain refusal for each event and for a command, and the launcher parses as Python 3.9 → `tests/test_hook_setup.py::test_old_python_gets_a_plain_refusal_before_any_import`
- [ ] A `session` or `stop` event loads no gate module → `tests/test_hook_setup.py::test_a_hook_event_loads_no_gate_module`
- [ ] A command still runs through the script path, and an error still prints one `Hard Eng:` line with exit 1 → `tests/test_hook_setup.py::test_a_command_runs_through_the_launcher`
- [ ] A load of the launcher as a module runs no command → `tests/test_hook_setup.py::test_a_load_of_the_launcher_runs_nothing`
- [ ] The push check gives the two narrow options to a pushed revision that holds them in the module → `tests/test_push_check.py::test_a_pushed_revision_with_the_runner_module_gets_the_narrow_options`
- [ ] The push check still gives the two options to a pushed revision that holds them in the script, and none to a revision older than the options → `tests/test_push_check.py::test_an_older_pushed_revision_keeps_its_own_options`
- [ ] An update from the last release installs the launcher and the module, and its first check passes → `tests/test_updates.py::test_an_update_from_a_release_with_the_long_script_installs_the_launcher_and_the_module`

Slice 2, refusals of a shard gate (`.hooks/shards.py`):

- [ ] A test path in the `addopts` of the pytest settings is refused, and the text names the settings file and the path → `tests/test_shards.py::test_a_test_path_in_the_pytest_settings_is_refused`
- [ ] `addopts` that holds only options, and an option value that is a folder in the `--option=value` form, pass → `tests/test_shards.py::test_addopts_with_options_only_pass_the_path_check`
- [ ] Each option that moves the settings is refused in the tests command and in `addopts`, and the text names the option and a step → `tests/test_shards.py::test_an_option_that_moves_the_settings_is_refused`
- [ ] `PYTEST_ADDOPTS` or `COVERAGE_RCFILE` in the environment of a shard run is refused, and the text names the variable → `tests/test_shards.py::test_a_variable_that_moves_the_settings_is_refused`
- [ ] `-o` with another key than `addopts`, and a tests command with none of the refused options, pass → `tests/test_shards.py::test_other_options_pass_the_settings_check`
- [ ] The merge part refuses the same options and variables, so a gate job cannot pass with a minimum that it did not read → `tests/test_shard_coverage_minimum.py::test_the_merge_refuses_a_moved_setting`

Slice 3, the audit of the released code: the coordinator starts audit agents in sealed copies of real projects after slices 1 and 2. Each fault that an agent reproduces in normal use gets its slice here, with a failing test before its fix.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 8d16d8cf, the rebase merge of PR 579. On that commit the required CI checks passed on 2026-11-12: each push run reused the pass of the PR head on the same files, and that head passed the checks job, each of the six shard jobs, the merge of their reports and each new-project job, two times. `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on this branch, with this plan as the only change: exit 0.
Execution: one builder on Sonnet in its own worktree builds slice 1, then slice 2, with a failing test before each behavior and each static gate command in its brief. The coordinator reviews each slice and times slice 1. Audit agents on Opus then run in sealed copies. A new reviewer on Opus reads the joined change, the independent review runs on the final commit, and the Complete check runs once.

## Risks + recovery

- An installed project updates from a release with the long script. Its update copies each hook file, so the launcher and the module arrive together. Recovery: the update test of slice 1 and the canary's update project, which installs the last release and updates to the candidate.
- A pushed revision older than the launcher has its options in the script. Recovery: the push check reads both files of the pushed revision; the second push check test proves the old form.
- A tool or a person loads `.hooks/hard-eng.py` by path for its functions. Recovery: decision 3 makes such a load run nothing; the functions are in `gate_runner`.
- A project already uses a refused option on its shard gate. Recovery: the refusal names the option and the step (put the value in the tests command or in a default settings file, or remove the `shards` field); the local count found no such project.
- The module is one more file for Python to find on each command. Recovery: the timing of slice 1 covers a command start as well as the two hook events.

## ux_reference

N/A — hook start, check rules and printed lines with no visual surface.

## Verification

Result: Pending
Evidence: Pending.
E2E: N/A — no user journey changes; each behavior is a hook start, a check or a printed refusal that its test runs directly.
Retro: Pending.

Delivery target: Merge
Delivery: Pending — the PR checks pass on the final commit, `ship` passes its ready stage, the rebase merge into `develop` and the release merge into `main` pass their runs.
