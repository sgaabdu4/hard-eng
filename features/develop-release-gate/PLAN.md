# Develop release gate

Status: Complete

## Outcome + scope

All PRs merge into `develop`. Before `develop` merges into `main`, `release_canary.py` installs the release in four kinds of project and runs one Claude and one Codex session in each new project (changed by [canary speed](../canary-speed/PLAN.md): installed projects run their checks only). Non-goals: no CI job, no second tool, no branch protection change in this PR.

## Repository context

Owners: [release_canary.py](../../release_canary.py) (the existing release try-out on installed projects); [setup.sh](../../setup.sh) installs from a local source checkout and `--new STACK` creates a scaffold; [agent_hooks.py](../../.hooks/agent_hooks.py) `record_session` + `remember_pass` write `.hard-eng/sessions/<id>.json` with `verified` after a passing Stop check; [AGENTS.override.md](../../AGENTS.override.md) holds the source-only release rule.
Evidence: the old canary only updated installed projects. It never tried a new install, an install into existing code, or an agent session.
Same cause: one cause, the canary had never run end to end on the Mac; each first-run failure (owner-name leak match, cut GitHub reply, deleted-line leak match, missing project documents, underscore folder names, skipped project lock files) is fixed in `release_canary.py` with its own test.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for every change to land on `develop` first and to be tried in a fresh scaffold, a greenfield project, a brownfield project and their installed projects, under Codex and Claude, before `main`. Standing approval to push, open PRs and decide. Private project names and results must never reach this public repository.
Decisions: Extend `release_canary.py`, not a new tool. Scaffold = every `--new` stack. Greenfield = `uv init --app` + `uv lock`. Brownfield = public `pallets/itsdangerous` at a pinned commit, so the target is reproducible and names no private project; greenfield and brownfield get no check before the agents, because a bare `uv init` project has no tests and an install into existing code needs a plan; the agents' passing Stop check is their proof (changed after the first Mac run). Agent verdict = the agent changed files and its session file holds `verified`, so a run counts only when Hard Eng's hooks loaded and its Stop check passed. Each agent works in a full copy of the prepared target, deleted afterwards. Leak block = the run fails when commit messages, the diff or PR titles and bodies name any private repository the account can read; the status says so without the name.

## Acceptance + steps

- [x] An agent session passes only when Hard Eng recorded a passing check → `tests/test_release_canary.py::test_an_agent_run_passes_only_when_hard_eng_recorded_a_passing_check`; its copy is deleted.
- [x] A release that names a private project fails and the posted status names no project → `tests/test_release_canary.py::test_a_release_that_names_a_private_project_fails_without_publishing_it`, `tests/test_release_canary.py::test_only_whole_private_names_count_as_leaks`.
- [x] Existing canary guarantees still hold → N/A — the full `tests/test_release_canary.py` suite covers them; no single test owns this line.
- [x] A private repository named after the public upstream owner does not flag that owner's name → `tests/test_release_canary.py::test_a_private_repository_named_after_a_public_owner_is_no_leak`. The first Mac run failed on this before any target ran.
- [x] A cut GitHub reply while reading PR text is retried instead of stopping the run → `tests/test_release_canary.py::test_a_cut_github_reply_is_retried_before_reading_release_text`. About 1 in 130 reads failed on the Mac.
- [x] The leak check reads only added diff lines, so deleting text `main` already published does not fail the release → `tests/test_release_canary.py::test_release_text_holds_added_lines_but_not_lines_main_already_published`.
- [x] New targets get filled PRODUCT.md and DESIGN.md, so a fresh install can pass its first check → `tests/test_release_canary.py::test_new_targets_get_the_project_documents_the_check_requires`.
- [x] Target folders are valid create-cloudflare project names → `tests/test_release_canary.py::test_a_target_folder_is_a_valid_cloudflare_project_name`.
- [x] Project lock files such as pubspec.lock reach the agent copy; only Git's own lock files are skipped → `tests/test_release_canary.py::test_project_lock_files_reach_the_agent_copy`.
- [x] The agent task lets agents commit on a local branch, never push, and leave failures that predate their change → N/A — task text only; the Claude trial on the Mac failed Vite (Stop hook blocked on an unfinished plan) and brownfield (agent stopped to ask about old failures) under "do not commit", and the next Mac canary run is the proof.
- [x] An interrupted pre-push still counts its killed gate as stopped where the container never reaps zombies → `tests/test_ship_actions.py::test_interrupted_pre_push_removes_its_snapshot`; it failed in the cloud container before.
- [x] Installed hooks spell no literal Claude address, so a project's email privacy scan passes; the main comparison showed this project failing on develop only → `tests/test_agent_hooks.py::test_installed_hooks_spell_out_no_claude_email_address`, red before the fix.
- [x] The shared AGENTS.md stays within the size the main release already held, because one project's test caps it and develop pushed it 153 tokens over; restated rules now name their HE- ID → `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`, red on the develop file.
- [x] Codex runs the release's project hooks in the canary; without the hook-trust bypass it lists them but runs none → N/A — only a real `codex exec` run can prove it; a throwaway repo showed SessionStart and Stop ran only with the flag.
- [x] Pushes to `develop` run the `hard-eng` check here, so installed projects accept a develop release; projects get only their base branch → `tests/test_ci_setup.py::test_workflow_runs_once_per_change`.
- [x] An update PR check does not demand that an unrelated open plan is Complete when the branch holds only files the verified update wrote; project work beside it still needs its plan → `tests/test_update_pr.py::test_update_branch_check_skips_an_unrelated_draft_plan`, red before the fix. One installed project failed on develop only for this reason.
- [x] A new Next.js project moves its Biome config to the installed Biome, formats its files and titles its images, so its first check passes on Biome 2.6 → `tests/test_new_project.py::test_nextjs_moves_the_scaffold_to_the_installed_biome`.
- [x] The Next.js and OpenNext starter tests define the font stubs at module level, so Biome's noComponentHookFactories rule passes → N/A — Biome 2.6.2 lint of the starter test and `bun test` passed on a fresh Next.js scaffold in the cloud; the OpenNext template cannot be cloned here, and the next Mac canary run is the proof.
- [x] The OpenNext starter replaces the glob 10.3.3 that its minifier pins (GHSA-5j98-mcp5-4vw2) → `tests/test_new_project.py::test_opennext_replaces_the_vulnerable_glob_its_minifier_pins`; the minifier only calls `globSync`, which glob 13.0.6 keeps.
- [x] `develop` merged with `main` keeps `tests/test_runner.py` under the 1000-line limit, so PR 327's check passes and installed projects accept the release → N/A — the file-length gate on the merge ref proves it; no unit test can.

## Baseline + execution

Result: Passed
Evidence: `uv run pytest tests/test_release_canary.py` on main: 6 passed, 1 failed in the cloud container only. The failing test saw a killed child as alive because the container's first process never reaps zombies (`/proc/<pid>/status` showed `Z`). Fixed in its own commit.
Execution: One builder. The full run needs the maintainer's Mac, through Remote Control.

## Risks + recovery

Agent CLIs change flags. A run that fails on a flag shows in the target's log; fix `agent_command`. Agent runs cost tokens; `--kind` and `--agent` limit reruns.

## ux_reference

N/A — command-line tool with no visual surface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_release_canary.py`: 11 passed. Full `python3 .hooks/hard-eng.py check`: see PR.
E2E: N/A — the full Mac run is the end-to-end proof and is recorded in the PR as counts only.

Delivery target: PR into `develop`; Delivery: Pending — CI `hard-eng` check, then the full canary run on the maintainer's Mac against the `develop` head before `develop` merges into `main`.
