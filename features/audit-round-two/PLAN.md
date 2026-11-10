# Fix the confirmed daily-use bugs, speed up the hooks and remove code nothing reaches

Status: Ready

## Outcome + scope

The open items of the November audit that a reviewer reproduced on the released code, and that cannot turn an installed project red, are closed: the bugs in daily use that the Escaped bug line names, two escapes from decided rules, the measured hook speed gains, the update code no caller can reach, and the texts that disagree with the code.

Non-goals:

- Stricter checks that can change what an installed project must do: instruction files that count as documentation only, the file length rule for Swift, the `Gap:` line for a second language, `sources` cover for JavaScript and Dart, the first-parent walk in the updater, plain-bullet acceptance lines and unreadable freshness tables. They are the next round.
- The worktree that a session start builds when no newer release exists. The up-to-date branch of the updater repairs the hook and reads the old generation inside that worktree. A move of those two steps to the live checkout changes what a session start writes there, so it needs its own plan.
- A license file, a wait before new Hard Eng code installs, and hooks that block on a crash. These are the maintainer's choices.
- The video skills, the Trello skill, the idle Codex broker stop and the 1000-line rule.
- The hook `if` filter. A probe showed it skips a wait in a heredoc that the hook denies.
- Tool hooks for Codex, the shared temporary folder on Linux, the size of skills that a submodule owns, and a secret scan of changed files only at Stop.
- `HE-YAGNI = ultra` in `AGENTS.md`, which is the maintainer's own wording.
- A move of the old root `PLAN.md` under `features/`. The plan check reads a moved Complete plan as edited and applies today's fields to it. The review prompt fix removes the harm: the reviewer reads the plans the diff changes.

The loop that this plan is one round of ends when an audit round finds no reproduced fault in normal use.

## Repository context

Owners: `run` in `.hooks/ship_actions.py` owns the ship stages; `run_check` in `.hooks/agent_hooks.py` owns the Stop check and `session_context` the session start text; `create` in `new_project.py` owns `--new`; `billed_job` in `.hooks/ci_usage.py` owns billed minutes; `preserve` in `.hooks/hook_chain.py` owns a project's own Git hook; `build_update` in `.hooks/update_runner.py` builds an update in a private locked worktree and is the only caller of `update` in `.hooks/update.py`; `commit_install` in `.hooks/update.py` owns the install commit on the live checkout; `generic_problem` in `.hooks/gap_issue.py` owns gap issue text; `managed_command` and `scanner_version` in `.hooks/tool_setup.py` own `uvx` tool runs; `validate_plans` in `.hooks/plans.py` owns plan checks; the three Claude tool hook commands are constants in `.hooks/agent_hooks.py`; `copy_scan_tree` in `.hooks/gitleaks_scan.py` owns the quick secret scan copy; `load_groups` in `.hooks/gate_config.py` owns gate loading.
Same cause: six causes. (1) A guard runs at a stage where it protects nothing: the install freshness check came with #78 for every ship stage, and it blocks `delivered` and `cleanup` after the code is merged; searched every caller of `require_current`, and `run` is the only one. (2) Code written for the live checkout stayed after its only caller moved to a private worktree: `features/canary-update-hang` added `committed_matches` (helped there; removed here, because the install commit check now compares Git's blob IDs and nothing else calls it), and the rollback, staging and signal guards in `commit_update`, the two re-checks in `install_revision` and two inputs of `update_attempt` guard states that worktree cannot have; searched every caller of `update`, `commit_update`, `repair_installation` and `update_attempt`. The same move also cut two checks off from the live checkout they read: the refusal for a local file that Git does not track could no longer fire, and the linked local settings file made every update refuse; a reviewer walked every guard on the update path against the worktree, and these two are the ones that changed a result. (3) A rule was applied to one path and missed its twin: `features/tool-release-age` added the two-day wait for tools that mise and Bun install (helped) and missed `uvx`, and commit ea160cd8 added the wait to the web finish step (helped) and missed the scaffold's own install; searched every `@latest` and every scaffold command in `.hooks/`. (4) Costly work runs before the cheap question that decides if it is needed: the whole repository is listed to find plan files, `load_groups` lists the repository twice, the tool hooks start Git to find a path the host already gives, and the secret scan asks Git once for each link; searched the session start, Stop and tool hook paths with a profile. No earlier fix found for these. The worktree built before the updater asks for a newer release has this cause too and stays; see Non-goals. (5) A text restates a rule that another file owns, and then drifts: `AGENTS.md` restates the wait rule and the update steps, and the review, retro and release texts each have a second copy; searched `AGENTS.md`, the skills, `README.md`, `DESIGN.md` and `DECISION.md` for each rule this plan touches. (6) A reader trusts the shape of a tool's output: `uv_rows` in `.hooks/freshness.py` took the name column as the package name, so a dependency with an extra was looked up under a name PyPI does not have and a dependency in two groups was looked up twice, and `diff_lines` in `.hooks/comments.py` read a `git diff` that a user's external diff tool replaces; searched every row reader in `.hooks/freshness.py` (the Bun reader already cuts the name, the Dart and Poetry readers read JSON) and every `git diff` call that reads a patch (`.hooks/mutation.py` already passes `--no-ext-diff`; `worktree` in `.hooks/debt.py` and `update_attempt` in `.hooks/update_runner.py` only hash the output; `public_text` in `release_canary.py` runs in CI, which has no user Git settings). No earlier fix found for these. The Stop wait, the README-only repository, the self-hosted runner, the linked hook, the rewritten install commit, the project name in a gap issue and the plan stage fallback have no earlier fix.
Single source: the two-day tool age is written five times today: `WAIT` in `.hooks/freshness.py`, a seconds literal and a `2d` text in `.hooks/tool_setup.py`, a seconds literal in `new_project.py` and a `days=2` in `.hooks/ci_jobs.py` (searched `.hooks/`, `setup.py` and `new_project.py` for `172800`, `2d`, `days=2` and `minimum-release-age`). This change gives it one owner, `RELEASE_AGE_SECONDS` in `.hooks/tool_setup.py`; the other four, the workflow migration line in `.hooks/ci_setup.py` and the new `uvx` cutoff read it. The JavaScript gate template and the two workflow files are static text and cannot read it, so `tests/test_tool_execution.py::test_release_age_has_one_value` fails when one of them differs. The tool hook commands have one owner, the constants in `.hooks/agent_hooks.py`; this repository's `.claude/settings.json` holds their output and changes with them. The plan path rule stays in `is_plan_path`; the new scoped listing filters with it. HE-NO-FOREGROUND-POLL text stays in the requirements reference and `AGENTS.md` only names the ID. The update steps stay in the ship checks reference. The big-change review rule stays in the ship checks reference and the code review skill links to it.
Escaped bug: the cleanup lock, the Stop wait, the README-only repository, the self-hosted billing, the frozen hook link, the rewritten install commit, the project name in a gap issue, the `uvx` age, the plan stage fallback, the dependency with an extra, the external diff tool, the replaced local file and the linked local settings file are on the base branch. The test gate should have caught each. Each gets a case that fails on `develop` 4b864c19 before its fix.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. On 2026-11-10 the maintainer told the builder to run autonomously, to make Hard Eng better and faster, to remove unnecessary parts that affect nothing, and to follow Hard Eng and Learn. The same day the maintainer asked for the release to `main` after the merge into `develop`, and allowed this thread to go without the cross-agent review.
Decided (1): the install freshness check runs only for the `ready` and `merge` stages. After the merge no code ships, so the check protects nothing there, and its advised rebase is what makes cleanup refuse.
Decided (2): a Stop that finds another check running in the same checkout does not wait behind it. It blocks the turn once, reports no pass and tells the agent to read that check's result or to start its own check in the background. A review probe showed that a note alone lets a turn end on code that no check passed.
Decided (3): when a project commit hook changes the install commit, setup undoes that commit, writes the planned files again, leaves them uncommitted and names the hook's changed paths. A silent commit makes every later update refuse.
Decided (4): the rollback, staging and signal guards in `commit_update` go only with a new test that proves a failing project commit hook leaves the live checkout, its branch and its worktree list unchanged. If that proof or any other update test fails, this removal is left out of the round.
Decided (5): a self-hosted job is one whose labels hold `self-hosted`. It bills 0 minutes and is counted apart.
Decided (6): the tool hooks keep the shell form and their open ending. Only the path changes, from a Git call to the folder the host gives.
Decided (7): gap issue text is refused when it holds the last folder of a package path, even when that folder is a common word such as `web`. The user rewords the line. No list of allowed words.
Decided (8): `--new` sets the user's files aside in the repository's Git folder, not in a system temporary folder, and the next run puts back what a stopped run left there.
Decided (9): an update is built from tracked content only. The candidate worktree never holds the linked local settings or local instruction file, so a private file cannot refuse an update. An update that would replace a local file Git does not track is refused and names the file, as the in-place update did before the worktree.

## Acceptance + steps

- [ ] After a PR merges and a newer Hard Eng release appears, `ship --stage delivered` and `ship --stage cleanup` still pass → `tests/test_ship_actions.py::test_a_newer_release_after_the_merge_does_not_block_delivered_or_cleanup`.
- [ ] `ship --stage ready` and `ship --stage merge` still refuse a stale install → `tests/test_ship_actions.py::test_shipping_a_stale_install_names_the_update_pr_step`.
- [ ] `--new` in a repository that holds only a README, a license and Git ignore or attribute files builds the project and keeps those files; the user's ignore lines stay → `tests/test_new_project.py::test_new_project_keeps_a_readme_license_and_ignore_file`.
- [ ] `--new` keeps the user's files in the Git folder during the scaffold, so a stop cannot strand them in a system temporary folder → `tests/test_new_project.py::test_kept_files_wait_in_the_git_folder_during_the_scaffold`.
- [ ] An error while `--new` puts the files back deletes none of them → `tests/test_new_project.py::test_an_error_while_putting_files_back_leaves_the_rest_waiting`.
- [ ] The next `--new` run after a stopped run puts the user's files back first → `tests/test_new_project.py::test_an_earlier_stopped_run_gets_its_files_back_first`.
- [ ] That restore never replaces a file the repository now holds; it stops and names both copies → `tests/test_new_project.py::test_a_stopped_run_never_replaces_a_file_the_repository_now_holds`.
- [ ] A kept ignore file with bytes that are not UTF-8 keeps them → `tests/test_new_project.py::test_a_kept_ignore_file_with_odd_bytes_keeps_them`.
- [ ] `--new` refuses a repository whose ignore file is a link, and writes nothing through the link → `tests/test_new_project.py::test_new_project_refuses_a_linked_ignore_file`.
- [ ] The Next.js scaffold installs no package before the age filter runs → `tests/test_new_project.py::test_nextjs_scaffold_installs_nothing_before_the_age_filter`.
- [ ] A self-hosted job bills 0 minutes and is counted as self-hosted → `tests/test_ci_usage.py::test_self_hosted_jobs_are_not_billed`.
- [ ] A project pre-push hook that is a link stays a link after setup, so later edits to the real hook run → `tests/test_hook_chain.py::test_a_linked_project_hook_stays_a_link`.
- [ ] A linked project hook whose target is missing when setup runs again stays in the chain → `tests/test_hook_chain.py::test_a_linked_project_hook_stays_chained_while_its_target_is_missing`.
- [ ] Gap issue text that holds the repository name, its owner, the folder name, a package name or the last folder of a package path is refused before any GitHub call → `tests/test_gap_issue.py::test_text_that_names_the_project_is_refused_before_any_github_call`.
- [ ] Gap issue text with a joined or camelCase spelling of one of those names is refused, and the owner and repository names come from a remote on any host → `tests/test_gap_issue.py::test_joined_spellings_and_any_remote_host_are_refused`.
- [ ] A word that comes from a remote address and is not a name, such as `git` or a parent folder, stays allowed in gap issue text → `tests/test_gap_issue.py::test_words_from_a_remote_that_are_not_names_are_accepted`.
- [ ] A gap issue refusal says which name matched → `tests/test_gap_issue.py::test_the_refusal_says_which_name_matched`.
- [ ] A `uvx` tool run and its version lookup skip a release that is under two days old → `tests/test_tool_execution.py::test_uvx_tools_wait_two_days_after_a_release`.
- [ ] An install commit that a project commit hook changed is undone, the planned files are written again and the message names the changed paths → `tests/test_setup.py::test_install_commit_changed_by_a_project_hook_is_undone_and_reported`.
- [ ] A correct install commit whose files Git stores with other line endings is kept → `tests/test_update_runner.py::test_install_commit_with_crlf_lines_kept_by_git_filters_is_not_undone`.
- [ ] An install commit that a hook rewrote is still found when the hook also changed the commit message → `tests/test_update_runner.py::test_install_commit_rewritten_by_a_hook_is_found_when_the_message_changes`.
- [ ] A failing project commit hook during an update leaves the live checkout, its branch and its worktree list unchanged, and the result names the hook → `tests/test_update_runner.py::test_a_failing_project_commit_hook_leaves_the_checkout_and_worktrees_unchanged`.
- [ ] A background update still skips a remembered refusal until the base tip changes or 24 hours pass, after the inputs that cannot change are removed → `tests/test_update_runner.py::test_background_update_does_not_repeat_a_refusal_until_inputs_change`.
- [ ] An update that would replace a local file Git does not track, ignored or untracked, is refused, names the file, leaves it unchanged, moves no branch and is remembered → `tests/test_update_runner.py::test_an_update_refuses_to_replace_a_local_file_git_does_not_track`.
- [ ] A setup rerun with no newer release refuses the same way → `tests/test_update_runner.py::test_a_setup_rerun_refuses_to_replace_a_local_file_git_does_not_track`.
- [ ] A linked local settings file that holds retired text does not block the update, and the file stays unchanged → `tests/test_update_runner.py::test_a_linked_local_settings_file_does_not_block_the_update`.
- [ ] A Stop while another check runs in the same checkout blocks at once, saves no pass and tells the agent to read that check's result or start its own → `tests/test_agent_hooks.py::test_stop_does_not_wait_behind_a_running_check`.
- [ ] `check --plan-stage Complete` on changed work with no plan of its own fails, and a clean tree keeps the old result → `tests/test_plan_acceptance.py::test_plan_stage_cannot_reuse_an_old_plan_for_changed_work`.
- [ ] Setup replaces each old tool hook entry that is still as installed with the new one; an entry the user edited stays, as for every other installed hook → `tests/test_hook_setup.py::test_setup_replaces_the_old_tool_hook_commands`.
- [ ] An update of an installed project replaces them the same way → `tests/test_update_runner.py::test_an_update_replaces_the_old_tool_hook_commands`.
- [ ] Session start still reports a failed process scan with the same line → `tests/test_agent_hooks.py::test_session_start_reports_a_failed_process_scan`.
- [ ] The scoped plan listing returns the same plans as the full listing for a root plan, a nested plan, an untracked plan, an ignored plan and a linked plan → `tests/test_plan_acceptance.py::test_plan_listing_matches_the_full_listing_filter`.
- [ ] The quick secret scan lists a folder that two links reach once, and still copies it for both links → `tests/test_current_files_gitleaks.py::test_a_folder_reached_by_two_links_is_listed_once_and_copied_twice`.
- [ ] The session and stop entries and the gate loader give the same results after their speed changes → N/A — the reviewer's old against new runs gave the same output and exit code; one difference stays: an error outside the hook handler prints a traceback, not the `Hard Eng:` line, with the same exit code 1. The existing hook and loader tests run the changed code, and the old and new medians go in Verification.
- [ ] The local state refusal inside the update, which the throwaway worktree can no longer reach, is removed → N/A — no behavior on the real path; the update tests run the changed code, and the refusal for a local file that Git does not track now has its own test above.
- [ ] No hook gets slower → N/A — no test can hold a budget this small and timing depends on the machine; old and new medians for each hook go in Verification.
- [ ] The texts match the code: the review rule in the code review skill, the retro in the workflow reference and README, the wait rule and the update step in `AGENTS.md`, the hook entry points in `DESIGN.md`, the canary and tool age lines in `DECISION.md`, the Codex start line in the README, the release line in `AGENTS.override.md`, the freshness stages in the ship checks reference, and the plan the review prompt names → N/A — wording; the proof is the Reader check recorded in Verification, and `check` keeps the links, sizes and registry valid.
- [ ] This repository's lint gate no longer repeats the three rules its complexity gate runs → N/A — configuration of this repository only; `check` runs both gates.
- [ ] A uv dependency listed with an extra, or in two groups, is looked up once under its plain name → `tests/test_freshness.py::test_uv_reads_a_dependency_with_an_extra_once`.
- [ ] A user's external diff tool does not hide an added switch-off comment → `tests/test_comments.py::test_an_external_diff_tool_does_not_hide_an_added_switch_off`.
- [ ] The comment check asks Git once, not once for each changed file, whether the change installs Hard Eng → N/A — no behavior changes; `tests/test_comments.py::test_the_install_change_keeps_older_blocks_in_files_its_tools_fixed` and `tests/test_comments.py::test_the_install_change_compares_each_older_block_whole` run the changed code, and the old and new medians go in Verification.
- [ ] A README change in this repository selects the tests that read the README → N/A — configuration of this repository only; the selection probe result goes in Verification.

## Baseline + execution

Result: Passed
Evidence: the starting tree is `develop` 4b864c19. The pre-push full check on that same tree passed on 2026-11-10 with 20 gates and 2,480 tests, and the `hard-eng` CI check passed on that commit. `check --plan-stage Draft --base HEAD` on this branch: exit 0. Five read-only reviewers reproduced each defect on that tree with a probe before this plan was written; an item with no reproduction is not in this plan.
Execution: four builders on Sonnet, each in its own worktree with its own files: small bugs (`ship_actions.py`, `new_project.py`, `ci_usage.py`, `hook_chain.py`, `gap_issue.py`, `tool_setup.py`); the update path (`update_runner.py`, `update.py`, `setup.py`); hooks and speed (`agent_hooks.py`, `hard-eng.py`, `plans.py`, `gitleaks_scan.py`, `gate_config.py`, the hook settings); texts (the Markdown files, the review prompt, this repository's gate file). Each slice has its failing test first and one commit. The coordinator joins the commits in that order, times each hook old against new, and runs the full check once. A fresh Opus reviewer reads the joined diff, and a reader that did not write the texts runs the Reader check.

## Risks + recovery

- The three tool hooks read the project folder that the host gives. A probe on Claude Code 2.1.321 showed the folder is the checkout the session starts in, a linked worktree included. A session that enters a worktree after it starts keeps the start folder, where the session start saved its state. A host older than Claude Code 1.0.58 does not give the folder, so the three tool hooks do nothing there. The README already needs a much newer host. Recovery: revert the commit.
- A Stop that finds another check running now blocks the turn once. An agent that ends its turn to wait for its own background check takes one more short step. Recovery: revert the commit.
- `check --plan-stage Complete` no longer takes an old plan for changed work. In a repository with no remote, a committed plan with a later fix that is not committed now fails. Recovery: commit the fix, or record it in the plan.
- The session start process scan now runs beside gate validation, so the idle Codex broker stop reads a list that is a fraction of a second older. A Codex job that starts in that time can lose its broker, as it could before in a shorter time.
- In a sparse checkout the quick secret scan now skips tracked files that are not on disk. Before, it stopped with an error. No file on disk is missed.
- Left for the next round: an ignored local file that sits where an update needs a folder is still replaced by a later pull. The earlier in-place update did not check parent paths either.
- A project whose pre-push hook is a link now runs the current version of that hook. A hook that was edited and now fails makes pushes fail, which is correct. Copies that an earlier install froze stay frozen.
- `uvx` tools now lag two days behind a release, like the other tools. A `uvx` tool whose only releases are under two days old cannot run; the six managed tools all have older releases. Recovery: revert the commit.
- The removed update guards change one rare message, which loses its note about kept edits. Recovery: revert that one commit.
- Setup now undoes an install commit that a project hook changed. The files stay in the working tree, uncommitted. Recovery: leave Hard Eng's files out of that hook and commit them.

## ux_reference

N/A — hook, command and text behavior with no visual surface.

## Verification

Result: Pending
Evidence: Pending — filled at the end of the build.
E2E: N/A — no user journey changes; each behavior is a command or hook result that its test runs directly.
Retro: Pending — written at task end.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green, then the release PR from `develop` into `main`.
