# Keep installed projects on runnable, current gates and exclude generated Dart from coverage

Status: Draft

## Outcome + scope

Fix [#166](https://github.com/sgaabdu4/hard-eng/issues/166) and [#167](https://github.com/sgaabdu4/hard-eng/issues/167): setup commits the files it installs when those paths were clean; update names untracked Hard Eng files instead of calling them local edits; setup/update migrate an old `families` gate configuration to the current templates; a Python package without `uv.lock`/`poetry.lock` fails setup with an actionable message; SessionStart states whether the gate configuration is valid; Dart setup marks `*.g.dart`, `*.freezed.dart` and `*.gr.dart` generated in `.gitattributes`, and the coverage failure says how to mark generated files. Non-goals: generating lockfiles, requirements.txt-driven gates, carrying old `families` commands into the new config, and a tool-availability probe at session start.

## Repository context

Owners: `setup.py` (`plan_install`, `install`, `configure_dart`, `gate_config`), `.hooks/update.py` (`update`), `.hooks/gate_config.py` (`parse_config`, `load_groups`, `generated_sources`), `.hooks/project_setup.py` (`dependency_command`, `javascript_manager` precedent), `.hooks/agent_hooks.py` (`session_context`), `.hooks/reports.py` (`line_coverage`). Update commits only through `commit_update` (`git add --force` + `git commit --only`); its `git status --porcelain --untracked-files=all --ignored` guard treats `??` as an edit. The old format (`schema_version`, `families`, `phases`) was retired in 083643e (#45); its commands reference retired paths, so they are reported, not carried. `generated_sources` reads only `linguist-generated`/`linguist-vendored` attributes; setup already accepts the three generated Dart patterns as analyzer exclusions.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all open issues (#166, then #167), run an adversarial GPT-6 Astra review, merge once satisfied, keep checks fast and cover edge cases.

## Acceptance + steps

- [ ] Setup on a repository whose install paths are clean creates one local commit of exactly the installed paths; a dirty or ignored install path, or a failing commit, leaves the files installed, uncommitted and names the paths to commit → `tests/test_setup.py`.
- [ ] Update with untracked installed files names them and asks for a commit; a modified path still reports local edits; ignored paths still block → `tests/test_updates.py`.
- [ ] An old `families` configuration is regenerated from templates on setup/update, the dropped family commands are reported, a rerun is stable, and `check` on an unmigrated config says to rerun setup → `tests/test_setup.py`.
- [ ] A Python package with no `uv.lock`/`poetry.lock` fails setup naming `uv lock`/`uv add -r requirements.txt`; a uv workspace member without its own lock still installs → `tests/test_setup.py`.
- [ ] SessionStart adds `Gates: configuration valid` or `Gates: not runnable — <reason>` and untracked Hard Eng files are named → `tests/test_agent_hooks.py`.
- [ ] Dart setup merges generated-file attributes into `.gitattributes` without duplicating or overriding existing lines; `generated_sources` then excludes those files; the coverage error names the fix → `tests/test_setup.py`, `tests/test_reports.py`.
- [ ] A real Flutter app with freezed + riverpod_generator passes the coverage gate after setup.
- [ ] Full gate passes; runtime compared with baseline 1m39s.
- [ ] GPT-6 Astra adversarial review findings reproduced and resolved.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `bc92b48` → exit 0; 17/17 gates PASS, 817 tests passed; 1m39s wall.
Execution: One builder, one commit per gap; then GPT-6 Astra (high) adversarial review of the branch diff.

## Risks + recovery

Setup's commit lands on the current branch; it is local and skipped unless every install path was clean. Recovery: `git reset HEAD~1` keeps the files. Projects relying on untracked `uv run` lock creation now fail setup until they lock. Recovery: run `uv lock` and commit it.

## ux_reference

N/A — installer, hook and gate-message change with no visual surface.

## Verification

Result: Pending
Evidence: Pending
E2E: Required — real Flutter app with freezed + riverpod_generator through setup and `check`; disposable Python repository through setup without a lock and with an old `families` config.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
