# Develop release gate

Status: Complete

## Outcome + scope

All PRs merge into `develop`. Before `develop` merges into `main`, `release_canary.py` installs the release in four kinds of project and runs one Claude and one Codex session in each. Non-goals: no CI job, no second tool, no branch protection change in this PR.

## Repository context

Owners: [release_canary.py](../../release_canary.py) (the existing release try-out on installed projects); [setup.sh](../../setup.sh) installs from a local source checkout and `--new STACK` creates a scaffold; [agent_hooks.py](../../.hooks/agent_hooks.py) `record_session` + `remember_pass` write `.hard-eng/sessions/<id>.json` with `verified` after a passing Stop check; [AGENTS.override.md](../../AGENTS.override.md) holds the source-only release rule.
Evidence: the old canary only updated installed projects. It never tried a new install, an install into existing code, or an agent session.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked for every change to land on `develop` first and to be tried in a fresh scaffold, a greenfield project, a brownfield project and their installed projects, under Codex and Claude, before `main`. Standing approval to push, open PRs and decide. Private project names and results must never reach this public repository.
Decisions: Extend `release_canary.py`, not a new tool. Scaffold = every `--new` stack. Greenfield = `uv init --app` + `uv lock`. Brownfield = public `pallets/itsdangerous` at a pinned commit, so the target is reproducible and names no private project; only the install's own change is checked, because existing code predates the gates. Agent verdict = the agent changed files and its session file holds `verified`, so a run counts only when Hard Eng's hooks loaded and its Stop check passed. Each agent works in a full copy of the prepared target, deleted afterwards. Leak block = the run fails when commit messages, the diff or PR titles and bodies name any private repository the account can read; the status says so without the name.

## Acceptance + steps

- [x] An agent session passes only when Hard Eng recorded a passing check → `tests/test_release_canary.py::test_an_agent_run_passes_only_when_hard_eng_recorded_a_passing_check`; its copy is deleted.
- [x] A release that names a private project fails and the posted status names no project → `tests/test_release_canary.py::test_a_release_that_names_a_private_project_fails_without_publishing_it`, `tests/test_release_canary.py::test_only_whole_private_names_count_as_leaks`.
- [x] Existing canary guarantees still hold → N/A — the full `tests/test_release_canary.py` suite covers them; no single test owns this line.
- [x] A private repository named after the public upstream owner does not flag that owner's name → `tests/test_release_canary.py::test_a_private_repository_named_after_a_public_owner_is_no_leak`. The first Mac run failed on this before any target ran.
- [x] A cut GitHub reply while reading PR text is retried instead of stopping the run → `tests/test_release_canary.py::test_a_cut_github_reply_is_retried_before_reading_release_text`. About 1 in 130 reads failed on the Mac.
- [x] The leak check reads only added diff lines, so deleting text `main` already published does not fail the release → `tests/test_release_canary.py::test_release_text_holds_added_lines_but_not_lines_main_already_published`.

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
