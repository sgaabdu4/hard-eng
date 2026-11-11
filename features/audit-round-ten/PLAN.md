# Cap a PR at 100 commits, stop repeated CI runs, and fix issues 572 and 573

Status: Ready

## Outcome + scope

`ship` refuses a PR with more than 100 commits, and a full `check` warns from 80. A merge that GitHub cannot rebase prints a step. A CI run does not repeat checks that passed on the same files: a push to any branch, a release PR from the base branch, and the new-project jobs of this repository on `develop`. A project-wide Biome 2.6 run passes with the installed files of issue 572: setup keeps the project's Biome away from `.hooks`, and the workflow file uses the quotes that Biome writes. Also, a finished plan that a formatter changed only in white space counts as unchanged. The root tool configuration files of a JavaScript package are not production code (issue 573), and the CI check of an update PR applies the listed-sources rule.

Non-goals:

- A refusal of the commit cap in `check`. Decided (1) gives the reason.
- Python and Dart files at a package root. Each one can move or holds behavior that a test can prove. `Same cause` (1) names them.
- A canary target that updates a JavaScript project. A project from the last release lists its root configuration files, so that flow does not meet the fault of issue 573.
- The Dart colour pattern that accepts a space. No behavior differs: the first filter mark already needs the written form, and the format gate writes that form.
- The split of the CI tests over shard jobs, trusted code for the CI jobs and the cheaper file walk: later plans.

## Repository context

Owners: `.hooks/change_size.py` owns the size rules of a branch and which plans count as changed. `.hooks/shipping.py` owns the PR facts that `ship` reads, and `.hooks/ship_actions.py` owns the merge. `.hooks/ci_usage.py` gets the rule for a CI run that reuses a pass. `release_canary.py` and `.github/workflows/canary.yml` own the new-project jobs of this repository. `.hooks/coverage_sources.py` owns which files are production code outside the listed sources, and setup reads the same function. `.hooks/update.py` owns the check of an update PR. `.hooks/untrusted_input.py` owns the declaration file and the project settings that leave it out (Fallow today, Biome with this plan). `.github/workflows/hard-eng.yml` and `.hooks/ci_setup.py` own the installed workflow and its migration. `hard-eng.gates.json` owns the gates of the shipped files.
Same cause: seven causes. (1) A file that a tool loads by a fixed name from the package root counts as production code (issue 573). Earlier fix: the starter tests read their configuration files and assert real values; it helped the canary flows and hid the fault for a project with `sources: ["src"]`. Other places, found with a probe of `nonproduction_source`: Python `conftest.py`, `noxfile.py`, `setup.py` and `docs/conf.py`, Dart `tool/`, `bin/`, `hook/` and `build.dart`, and JavaScript dotfile rc files. Not changed: `conftest.py` can move into the tests folder, `setup.py` can become `pyproject.toml`, an rc file can take the `<tool>.config.<ext>` name, and the other names hold behavior that a test can prove. (2) A new refusal first shows on the next unrelated change after an update (issue 573, second half). Earlier fix: none. Other places: each rule that `check` applies after the update shortcut; the listed-sources rule joins the update check, and the gate-time rules (types, coverage) stay out because they need the tools. (3) An installed file fails the formatter or linter of the project (issue 572). Earlier fix: setup adds `.hooks` to the ignore list of Fallow; it helped, and this plan does the same for Biome. Other places, found with a project-wide run in one sealed new project: four lint findings in the declaration file and the quotes of the workflow file; the skill Markdown, the JSON files and the PR text workflow gave no finding. (4) A change with no changed word counts as an edit of a finished plan (comment on issue 572). Earlier fixes of this family: a moved plan is not an edit, and the fields of a later release are soft for a plan from before the update; both helped. Other place: none found in `judged_plans`. (5) A CI run repeats checks that passed on the same files. Earlier fixes: the base-branch push reuses the pass of its merged PR (PR 220), and the release PR skips the new-project jobs; both helped. Other places, searched by workflow and event: three repeats, each fixed here; the two-system jobs, the summary job, the `pr text` job and the local push check are not repeats. (6) GitHub cannot rebase a long PR: first seen on PR 571 with 156 commits; no earlier fix. (7) A refusal with no step: the merge stage printed the raw GitHub error. Earlier fixes: the refusals of round 9 got steps; they helped. Other places, searched: each `gh` call of the merge stage; the merge call is the only one that printed a raw error for a state that the ready stage passes.
Single source: the cap and the warning count have one owner, `.hooks/change_size.py`; `ship` imports the text from it and the requirement entry cites the ID; searched: `100` and `commits` in `.hooks/`. The step for a PR that GitHub cannot rebase has one function in `.hooks/shipping.py`, used by the ready stage and the merge stage. The reuse rule keeps one entry function, `reused_pull_request`, for the push and the release PR; `check` and `impact` call it through `proven_elsewhere`; searched: `reused_pull_request` and `commits/` in `.hooks/`. The new-project reuse has one owner, `ci_failures` in `release_canary.py`, used by the `targets` job, the release gate and the Mac canary. The pattern for a root tool configuration file has one owner, `source_roots`, which the guard and setup both call; `retry_forms.is_config` answers another question (four test runners at any depth, for the retry scan) and is not a copy. The two workflow lines of issue 572 have one owner, the workflow file of this repository, which setup copies; the migration names the same two lines. The entry for the project's Biome settings has one owner, beside the Fallow entry in `.hooks/untrusted_input.py`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run the audit and fix rounds autonomously and to follow Hard Eng and Learn. On 2026-11-11 the maintainer asked for a rule of at most 100 commits for each project, for a fix or a close of each open Hard Eng issue, and for an audit and a fix of repeated CI checks, also in the code that each project installs.

Decided:

1. The commit cap refuses at `ship --stage ready`, and so at `merge`, by the commit count that GitHub reports. That count comes in the PR response that `ship` already reads. A full `check` prints a warning from 80 commits and never refuses. Reason: `check` runs in CI on merge commits and on base-branch pushes, and a refusal there would stop open branches of installed projects that passed before. A quick check, the Stop hook and session start get no new work.
2. No text claims a GitHub limit. GitHub refused a rebase at 156 commits and accepted 78; its documents name no number. The cap of 100 is a Hard Eng rule.
3. A branch above the cap has two ways: ship the finished part in its own PR and continue on a new branch, or join neighbour commits in a task-branch rebase. The proof of a join is an empty `git diff <old head> <new head>`. HE Ship already permits a task-branch rebase, so its sentence stays.
4. The ready stage refuses a PR when GitHub reports `rebaseable: false` (same response, no added call). The merge stage reads the PR one more time only after a failed merge, and prints the step when GitHub cannot rebase. The step does not name a push to the base branch, because the push guard refuses that.
5. Setup adds `!.hooks` as the last entry of `files.includes` in the project's root Biome settings, as it adds `.hooks/**` to the ignore list of Fallow. The declaration file keeps its types. Reason: a sealed new project with Biome 2.6.6 reported four findings, one more than the issue lists: the three `{}` types and `any[]`. Both forms are there on purpose (PR 232), and a type with no `any` could break type checks of installed projects. With the entry, the lint run of that project passed. Where setup cannot edit the settings safely, it prints the step and does not refuse.
6. The format gate of the shipped files covers the two installed workflow files. The lint gate stays as it is.
7. A finished plan counts as unchanged when its words and their order equal the base copy. A table rule line is one word whatever its length. Measured with Biome 2.6.6 at default settings on the 134 finished plans of this repository: 14 changed; 13 kept each word; 1 differed only in the dashes of a table rule.
8. A file directly in a JavaScript package root with the name `<tool>.config.<js|mjs|cjs|ts|mts|cts>` is tool configuration (lowercase letters, digits and hyphens in the tool part). The guard and setup leave it out. A project that lists such a file keeps its coverage and type demands. A usual update does not rewrite `sources`; setup computes them only for a first install, a new package and the old families format.
9. The update check runs the listed-sources rule only in CI, after it has proven the update. Reason: no hook of the update branch gets slower, and the `impact` step runs it with plain Python.
10. The reuse rule accepts a push to any branch. For a release PR (head is the shipping base of the same repository, base is another branch) it reuses when the merge tree equals the head tree and the newest completed run of each required check on the head commit passed. A run in progress and a cancelled run prove nothing and are left out.
11. The two reuse functions move from `.hooks/shipping.py` to `.hooks/ci_usage.py`, because the file limit of 1,000 lines leaves no room. No new installed file: each one adds work to each session start.
12. The new-project jobs on a `develop` push are skipped when the merged PR head has the same files and each new-project job passed there. The release gate and the Mac canary follow the same rule through `ci_failures`.

## Acceptance + steps

Slice 1, commit cap (`.hooks/change_size.py`, `.hooks/shipping.py`, `.hooks/hard-eng.py`, `.agents/skills/he/references/requirements.md`):

- [ ] The ready stage passes a PR with 100 commits and refuses 101 with the two ways out → `tests/test_ship_commits.py::test_ready_refuses_a_pr_over_the_commit_cap`
- [ ] The ready stage refuses a PR whose commit count is missing or is not a whole number → `tests/test_ship_commits.py::test_ready_refuses_a_pr_with_no_usable_commit_count`
- [ ] A full check prints the warning at 80 and at 101 commits, prints none at 79, on the base branch and with no base, and never fails for it → `tests/test_change_size.py::test_a_full_check_warns_from_80_commits_and_never_refuses`
- [ ] A full check starts one Git command for the count and a quick check starts none → `tests/test_gate_speed.py::test_only_a_full_check_counts_the_branch_commits`
- [ ] A new requirement entry for the commit cap states the cap, the warning, the two ways out and the exempt PRs → N/A — rule text; the registry check refuses an entry with no test that names its ID

Slice 2, a step when GitHub cannot rebase (`.hooks/shipping.py`, `.hooks/ship_actions.py`, `.agents/skills/he-ship/references/checks.md`):

- [ ] The ready stage refuses a PR that GitHub reports as not rebaseable, with the step → `tests/test_ship_commits.py::test_ready_refuses_a_pr_github_cannot_rebase`
- [ ] A failed merge of such a PR prints "nothing was merged" and the step, and names no push to the base → `tests/test_ship_commits.py::test_merge_names_a_step_when_github_cannot_rebase`
- [ ] A rebase answer that GitHub gives between the two reads of the PR does not count as a changed PR → `tests/test_ship_commits.py::test_a_rebaseable_value_that_arrives_late_is_no_change_in_the_pr`

Slice 3, a CI run reuses a pass on the same files (`.hooks/ci_usage.py`, `.hooks/shipping.py`, `.hooks/hard-eng.py`):

- [ ] The two reuse functions are in `.hooks/ci_usage.py` → N/A — a move; the proof is that the reuse tests of `tests/test_shipping.py` and `tests/test_ci_usage.py` pass with only import and patch lines changed
- [ ] A push to a branch other than the shipping base reuses the pass of its one merged PR on the same tree → `tests/test_ci_usage.py::test_a_push_to_another_branch_reuses_the_merged_pr_checks`
- [ ] A release PR reuses the passed checks of its head commit, also with its own run in progress and with an earlier cancelled run → `tests/test_ci_usage.py::test_a_release_pr_reuses_the_passed_checks_of_the_base_commit`
- [ ] A release PR runs the checks when a required check has no completed run, when the newest completed run failed, when the merge tree differs, and when the head comes from a fork → `tests/test_ci_usage.py::test_a_release_pr_runs_the_checks_when_no_pass_covers_it`
- [ ] An ordinary PR prints no line, starts no Git command and makes no API call for the reuse rule → `tests/test_ci_usage.py::test_an_ordinary_pr_prints_nothing_and_asks_nothing`

Slice 4, the new-project jobs of this repository (`release_canary.py`, `.github/workflows/canary.yml`):

- [ ] A commit with no new-project runs of its own is proven by the head of its merged PR when both hold the same files and each job passed there → `tests/test_canary_reuse.py::test_a_develop_push_reuses_the_new_project_jobs_of_the_merged_pr`
- [ ] The jobs still run when the PR head has no runs, has a failed job or holds other files, when no merged PR is found, and when the lookup fails (one line on stderr, none on stdout) → `tests/test_canary_reuse.py::test_a_push_runs_the_new_projects_when_the_pr_did_not_prove_them`
- [ ] The release gate passes for a `develop` commit that reused the jobs of its PR → `tests/test_canary_reuse.py::test_the_release_gate_follows_a_reused_push_to_the_pr_head`
- [ ] A new JavaScript project in CI runs its own lint script after its full check, and a project with no lint script gets no such step → `tests/test_release_canary.py::test_a_new_javascript_project_in_ci_also_runs_its_own_lint_script`
- [ ] The `targets` job writes an empty list and names the PR head on such a push → N/A — workflow wiring; the proof is the first push run on `develop` after this PR merges, recorded in Verification

Slice 5, issue 572 (`.hooks/untrusted_input.py`, `setup.py`, `.github/workflows/hard-eng.yml`, `.hooks/ci_setup.py`, `hard-eng.gates.json`):

- [ ] Setup makes `!.hooks` the last entry of `files.includes` in a root `biome.json` or `biome.jsonc`, keeps comments and other `includes` keys, and changes nothing when the entry is there → `tests/test_untrusted_input.py::test_setup_keeps_the_project_biome_run_away_from_the_hooks_folder`
- [ ] Setup adds the entry in a project with no TypeScript package at its root → `tests/test_untrusted_input.py::test_setup_adds_the_biome_entry_when_no_typescript_package_is_at_the_root`
- [ ] Setup changes nothing in a project with no Biome settings → `tests/test_untrusted_input.py::test_setup_leaves_a_project_without_biome_settings_alone`
- [ ] Setup prints the step and goes on when it cannot edit the settings safely → `tests/test_untrusted_input.py::test_setup_prints_a_step_when_it_cannot_edit_the_biome_settings`
- [ ] The format gate of the shipped files covers each installed workflow → `tests/test_gate_tools.py::test_the_shipped_format_gate_covers_each_installed_workflow`
- [ ] The two workflow lines use double quotes → N/A — the gate `shipped-format` fails on the base and passes on this change
- [ ] An installed workflow with the single-quoted lines gets the double-quoted lines at the next update → `tests/test_bun_workflow_migration.py::test_an_old_workflow_gets_double_quoted_mise_switches`
- [ ] The four reproduction steps of issue 572 fail on the base and pass on this change in one sealed new project → N/A — a real project run with Biome 2.6.6, recorded in Verification

Slice 6, a finished plan with changed white space (`.hooks/change_size.py`):

- [ ] An old finished plan with added empty lines, or with a longer table rule, counts as unchanged → `tests/test_planning_handoffs.py::test_a_reformatted_old_complete_plan_counts_as_unchanged`
- [ ] A changed word, and a new plan, still need the fields of today → `tests/test_planning_handoffs.py::test_a_word_change_or_a_new_plan_still_needs_todays_fields`
- [ ] A reformatted old plan does not count as the plan of new code → `tests/test_planning_handoffs.py::test_a_reformatted_old_plan_does_not_cover_new_code`
- [ ] A changed finished plan that passes starts no word comparison → `tests/test_planning_handoffs.py::test_a_passing_changed_complete_plan_starts_no_word_comparison`

Slice 7, issue 573 (`.hooks/coverage_sources.py`, `.hooks/update.py`, `.agents/skills/he/references/gates.md`):

- [ ] Setup of a package with `src` and root tool configuration files lists only `src`, and the check passes → `tests/test_greenfield.py::test_setup_and_check_leave_root_tool_configs_out_of_the_sources`
- [ ] A build script folder, a runtime file with a dot in its tool part, `middleware.ts` and a configuration file in a subfolder still need listing → `tests/test_greenfield.py::test_runtime_files_beside_tool_configs_still_need_listing`
- [ ] A listed root tool configuration file stays a production file → `tests/test_runner.py::test_a_listed_root_tool_config_keeps_its_coverage_demand`
- [ ] An update leaves a listed root tool configuration file in `sources` → `tests/test_scaffold_replay.py::test_an_update_keeps_a_listed_root_tool_config_in_the_sources`
- [ ] The CI check of an update PR refuses code outside the listed sources, and a local check of the same update does no added work → `tests/test_scaffold_replay.py::test_scaffold_update_check_refuses_code_outside_the_sources`

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 22e85390, the rebase merge of PR 571. On that commit the required CI checks passed on 2026-11-11 (the push run reused the pass of the PR head on the same tree, and the canary run passed). `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on this branch, with this plan as the only change: exit 0.
Execution: five builders on Sonnet, each in its own worktree with its own files, each with a failing test before each behavior and each static gate command in its brief: (A) slices 1 and 2, (B) slice 3, (C) slice 5, (D) slices 6 and 7, (E) slice 4. A and B both change `.hooks/shipping.py` in separate parts; B moves the reuse functions first. The coordinator joins the commits in the order B, A, C, D, E and runs the static gates and the whole suite on the joined branch. Then a new Opus reviewer reads the joined change, the independent review runs on the final commit, and the Complete check runs once.

## Risks + recovery

- An installed project has an open PR above 100 commits when it updates. `ship` then refuses it. Recovery: the refusal names the two ways out, and `check` does not refuse.
- The reuse rule skips a check that should run. Recovery: it reuses only a completed pass on the same tree, each other case runs the checks, and the first real release after this change is watched.
- A real module at a package root has a name like `site.config.ts`. It then gets no coverage demand. Recovery: the rule text says to list such a file, and a listed file keeps its demands.
- The update PR of a project fails where it passed before. That is the purpose: the fault shows on the PR that causes it, with the step.

## ux_reference

N/A — rule text, check rules, CI files and messages with no visual surface.

## Verification

Result: Pending
Evidence: Pending — the commands and results of the build.
E2E: N/A — no user journey changes; each behavior is a hook, command, CI or setup result that its test runs directly.
Retro: Pending — written at task end.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` and `canary` CI checks green, then the release into `main`.
