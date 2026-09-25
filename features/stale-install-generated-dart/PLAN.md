# Keep installed projects on runnable, current gates and exclude generated Dart from coverage

Status: Complete

## Outcome + scope

Fix [#166](https://github.com/sgaabdu4/hard-eng/issues/166) and [#167](https://github.com/sgaabdu4/hard-eng/issues/167): setup commits the files it installs when those paths were clean; update names untracked Hard Eng files instead of calling them local edits; setup/update regenerate an old `families` gate configuration from the current templates, keep its runnable commands as `legacy-<name>` shared checks and report the rest; a Python package without `uv.lock`/`poetry.lock` fails setup and validation with an actionable message; SessionStart states whether the gate configuration is valid; Dart setup marks `*.g.dart`, `*.freezed.dart`, `*.gr.dart` and exact gen-l10n outputs generated in `.gitattributes`, the coverage failure says how to mark generated files, and setup accepts `flutter create`'s comment-only lint rules. Non-goals: generating lockfiles, requirements.txt-driven gates, and a tool-availability probe at session start.

## Repository context

Owners: `setup.py` (`plan_install`, `install`, `configure_dart`, `gate_config`), `.hooks/update.py` (`update`), `.hooks/gate_config.py` (`parse_config`, `load_groups`, `generated_sources`), `.hooks/project_setup.py` (`dependency_command`, `javascript_manager` precedent), `.hooks/agent_hooks.py` (`session_context`), `.hooks/reports.py` (`line_coverage`). Update commits only through `commit_update` (`git add --force` + `git commit --only`); its `git status --porcelain --untracked-files=all --ignored` guard treats `??` as an edit. The old format (`schema_version`, `families`, `phases`) was retired in 083643e (#45); its commands may reference retired paths, so only commands whose program exists are carried. `generated_sources` reads only `linguist-generated`/`linguist-vendored` attributes; setup already accepts the three generated Dart patterns as analyzer exclusions.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix all open issues (#166, then #167), run an adversarial GPT-6 Astra review, merge once satisfied, keep checks fast and cover edge cases.
Declined review finding: a nonzero setup exit when the install commit is skipped. Files are installed at that point; setup names the uncommitted paths, and every SessionStart status line repeats them.

## Acceptance + steps

- [x] Setup on a repository whose install paths are clean creates one local commit of exactly the installed paths, including a Husky launcher, and a reinstall with nothing new creates none; a dirty or ignored install path, or a failing commit, leaves the files installed, uncommitted and names the paths to commit → `tests/test_updates.py::test_install_commits_only_clean_installed_paths`.
- [x] Update with untracked installed files names them and asks for a commit; ignored paths still block as local edits → `tests/test_updates.py`.
- [x] An old `families` configuration is regenerated from templates on setup/update; a runnable family becomes `legacy-<name>`, a template duplicate is not repeated, an unrunnable one is reported; a rerun is stable; an unmigrated config says to rerun the installer → `tests/test_setup.py`, `tests/test_agent_hooks.py`.
- [x] A Python package with no `uv.lock`/`poetry.lock` fails setup and gate validation naming `uv lock`/`uv add -r requirements.txt`, including an existing configuration; a uv workspace member without its own lock still installs → `tests/test_setup.py`.
- [x] SessionStart adds `Gates: configuration valid` or `Gates: not runnable — <reason>` and untracked Hard Eng files are named → `tests/test_agent_hooks.py`.
- [x] Dart setup prepends generated-file attributes to `.gitattributes`, so project overrides keep precedence, an unrelated attribute does not block the marker, only real gen-l10n outputs match, and paths with spaces are quoted; `generated_sources` then excludes those files; the coverage error names the fix → `tests/test_dart_config.py`, `tests/test_reports.py`.
- [x] Setup installs into an untouched `flutter create` app whose `linter: rules:` holds only comments → `tests/test_dart_config.py`, real `flutter create` app.
- [x] A real Flutter app with freezed + riverpod_generator passes the coverage gate after setup.
- [x] Full gate passes; runtime compared with baseline 1m39s.
- [x] GPT-6 Astra adversarial review findings reproduced and resolved.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check` on unchanged `bc92b48` → exit 0; 17/17 gates PASS, 817 tests passed; 1m39s wall.
Execution: One builder, one commit per gap; then GPT-6 Astra (high) adversarial review of the branch diff.

## Risks + recovery

Setup's commit lands on the current branch; it is local and skipped unless every install path was clean. Recovery: `git reset HEAD~1` keeps the files. Projects relying on untracked `uv run` lock creation now fail setup until they lock. Recovery: run `uv lock` and commit it.

## ux_reference

N/A — installer, hook and gate-message change with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on 95e2a4c → exit 0; 17/17 gates PASS, 830 tests passed; 1m40s wall against the 1m39s baseline. The SessionStart gate status adds about 0.1–0.3s. Earlier full runs caught a C901 overrun in `update` and `configure_dart`, an implicit-any container and `tests/test_setup.py` passing 1000 lines; each was fixed. GPT-6 Astra (high) reviewed the branch three times: 8, then 5, then 1 confirmed findings; all were fixed with tests except the declined exit-code finding above. New tests were confirmed to fail without their fixes where noted in commits. `/codex:adversarial-review --base main` then found retired interpreter families kept although their script was missing; fixed in 4c8768c with a regression case, and `check` on that commit → exit 0, 17/17 gates PASS, 830 tests passed (timing not comparable: load average 65 from a parallel build). A second review found interpreter options (`python3 -u scripts/gone.py`) still hid a missing script; fixed in 083645d by reading the script operand after interpreter options, treating `-c`/`-m`/`-e` as inline code or modules, with Python and Node cases.
E2E: Passed — Flutter 3.47.5 app with freezed 4.0.2 + riverpod_generator 4.0.9: after setup, `tests` PASS at 92.86% line coverage; with `.gitattributes` removed it FAILs naming `lib/claim.freezed.dart` plus the new hint. An untouched `flutter create` app now installs (previously `Dart linter.rules must be an object`). Disposable Python repo with `requirements.txt`, no lock and a `families` config: setup refused with the `uv lock`/`uv add -r requirements.txt` message and wrote nothing; after `uv add -r requirements.txt`, setup regenerated the config, reported the families and committed `Install Hard Eng`; `check` then ran every gate (lockfile PASS; remaining failures were the fixture's own findings).

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge to main, main CI green.
