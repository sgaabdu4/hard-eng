# HE-YAGNI names operator content as stored data; one clear finding for a token file outside the app

Status: Complete

## Outcome + scope

HE-YAGNI says content that operators own and change (message text, dates, send windows, prices, audiences) is a current requirement for stored data, not code. The UI token reader reports one finding at a CSS `@import` that points to an existing CSS file outside the app, when the import is added or when it causes undefined-token or `DESIGN.md` weight findings, and drops those findings. The shared rules line for a failing check says that Hard Eng is strict and is broken only when no project change passes, with no more tokens than before. A verified update that changes a project rules file is no longer scaffold only, and CI no longer skips the shared checks for a change to a root file that is not documentation, so a root `AGENTS.md` change in an update runs them. Non-goals: following or accepting the outside import; the planning case that the issue suggests; package import forms.

## Sources + coverage

Sources: N/A — the request is public issue 635 (read in full) and maintainer instructions about the outside-import finding, the failing-check line and the skipped root check; no other source.

## Repository context

Owners: `.agents/skills/he/references/requirements.md` (HE-YAGNI, HE-UI-SOURCE); `.hooks/ui_rules.py` (`ui_findings`, `_css_files`, `_css_import_targets`); `tests/test_ui_outside_tokens.py`; `.hooks/ui_css_imports.py`; `AGENTS.md`; `.hooks/gate_config.py` (`affected_groups`, `shared_for`), `.hooks/ci_jobs.py` (`impact_outputs`), `.hooks/dependency_graph.py` (`DOCS_ROLES`); `tests/test_root_change_checks.py`; `.hooks/update.py` (`check_scaffold_update`); `.hooks/comments.py` (`ui_candidate`).
Same cause: N/A — no earlier fix of this cause. A probe showed that the second caller of `_css_files`, `design_weight_findings` in `.hooks/ui_audit_rules.py`, also reported a missing weight for tokens held outside the app; it now returns the import finding instead. `ui_whole.py` and `ui_tokens.py` never read `@import` targets, so they have no such noise. Escaped bug, two causes. First, `check_scaffold_update` called a verified update scaffold only whenever every changed file is one that an update can write, and `AGENTS.md` is one; the check then ran no gate and `impact_outputs` printed docs_only=true before any selection. A project rules file is merged with project text that project checks read, so it now ends scaffold-only. Second, `packages_for` skips `AGENTS.md` and `.agents/` as package input, so nothing was selected, `shared_only` cut the shared group to the secret scan, and `impact_outputs` read one selected group as docs only; `shared_for` now keeps every shared check unless all changed files are documentation, plan captures or workflows. The only other reader of that selection is the check itself; `update_pr.py` reads only the state of the required CI check, so an update PR now waits for the root checks through the same job. The documentation rule has one owner, `is_documentation` in `plans.py`; it already excludes `AGENTS.md`.
Single source: HE-YAGNI sentence has one owner, the registry entry; the README table holds a short summary of the rule that stays unchanged. The "outside the app" test reuses `_package_dir`, the owner that `_css_files` uses. The CSS import graph moved from `ui_rules.py` to `ui_css_imports.py` (the file passed 1000 lines), and `ui_audit_rules.py` imports it from there. The failing-check line has one copy, in the shared `AGENTS.md`; a search for its other phrases found no other copy outside the submodules. The set of roles that make a change docs only now has one owner, `DOCS_ROLES` in `dependency_graph.py`, used by `shared_only` and by `impact_outputs`. `package_dir`, `CSS_COMMENT`, `BUILD_FOLDERS` and the import reader live in `ui_css_imports.py`; `ui_rules.py` and `ui_audit_rules.py` import them from there.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked to look at the open Hard Eng issues on 2026-11-23, and the user's standing rule: merge each task PR into develop once its checks pass.

## Acceptance + steps

- [x] An app whose CSS imports a token file outside the app gets one finding at the import line, naming file and target, and no undefined-token findings → `tests/test_ui_outside_tokens.py::test_a_token_file_outside_the_app_is_one_finding_at_its_import`; the target above the repository folder → `test_an_import_above_the_repository_is_outside_the_app`.
- [x] The same tokens inside the app, and package imports such as `@import "tailwindcss"`, give no finding → `tests/test_ui_outside_tokens.py::test_the_same_tokens_inside_the_app_pass`; a folder in the app's own `node_modules` is not outside → `test_a_relative_import_into_node_modules_is_not_outside_the_app`.
- [x] The finding appears once for a package, whichever file is a candidate, and a comment above the import does not shift its line → `tests/test_ui_outside_tokens.py::test_the_outside_import_finding_is_one_per_app_and_keeps_its_line`.
- [x] An added import is refused with no `@theme` in the app, with `tailwind.config.*`, and when the outside file holds no token → `tests/test_ui_outside_tokens.py::test_an_outside_import_is_a_finding_whatever_the_app_theme_holds`.
- [x] An old outside import does not fail a class that the app defines, and a generated stylesheet is not judged for its import → `tests/test_ui_outside_tokens.py::test_an_old_outside_import_does_not_fail_a_class_the_app_defines` and `test_a_generated_stylesheet_is_not_judged_for_its_import`.
- [x] A changed `DESIGN.md` with tokens outside the app gets the import finding, not a missing-weight finding → `tests/test_ui_outside_tokens.py::test_an_outside_import_replaces_the_design_weight_finding_it_causes`.
- [x] HE-YAGNI holds the content sentence and `tests/test_skill_links.py` passes → `tests/test_skill_links.py` and `tests/test_requirements.py` results.
- [x] The failing-check line says that Hard Eng is strict and broken only when no project change passes, and the shared rules stay within the released size → `tests/test_agent_hooks.py::test_shared_agent_rules_stay_within_the_released_size`.
- [x] A verified update that changes `AGENTS.md` is not scaffold only → `tests/test_scaffold_replay.py::test_update_that_changes_the_project_rules_file_is_not_scaffold_only`.
- [x] A root `AGENTS.md` change runs the shared checks and prints docs_only=false, while a README, `CLAUDE.md` or docs change stays docs only → `tests/test_root_change_checks.py::test_a_root_file_runs_the_shared_checks_unless_it_is_documentation`.
- [x] The affected check is not slower → N/A — timing, no test can prove it; compiled runs on each version are in Verification.

## Baseline + execution

Result: Passed
Evidence: 2026-11-23, `python3 .hooks/hard-eng.py check --plan-stage Draft --base origin/develop` on develop 4290fb2d plus this plan: exit 0. No package read the plan-only change, so it ran the secret scans only, and both passed.
Execution: One builder, this session; one independent review on the final head.

## Risks + recovery

A project that imports shared tokens from outside the app now gets a finding at the import. The fix is to move the tokens into the app. Revert the commit to undo. The new refusal reaches no new-project flow of `release_canary.py` (`install_new`): the flows install a Python scaffold, a greenfield project or a pinned Python library, none of the steps adds a CSS file, and the starters hold no `@import`.

## ux_reference

N/A — no visible UI; hook and rule text only.

## Verification

Result: Passed
Evidence: 2026-11-23 on this branch. Focused tests passed (912 tests): the UI group (`test_ui_outside_tokens`, `test_ui_rules`, `test_ui_audit_guards`, `test_ui_single_source`, `test_ui_quality`), the affected-selection group (`test_root_change_checks`, `test_affected_selection`, `test_ci_setup`, `test_gate_speed`, `test_shard_workflow`, `test_basic_mode`, `test_ci_blocking`, `test_shipping_policy`), the update group (`test_agent_hooks`, `test_updates`, `test_scaffold_replay`, `test_update_pr_refusal`, `test_update_runner`) and `test_skill_links` and `test_requirements`. `test_shards.py::test_a_worker_count_in_the_pytest_settings_leaves_the_shard_files_exact` fails the same way on develop 4290fb2d when run by hand with `uv run --with pytest`, so it does not come from this change. `hot-paths` on the touched hook files: 0 findings. Static gates run by hand with the commands of `hard-eng.gates.json`: format, lint, complexity, annotations, types, dead-code, declarations, actionlint, shellcheck, secrets-files and security exit 0. `check --plan-stage Ready --base origin/develop` exit 0. The red-first runs: the outside-import test failed on the undefined token `bg-brand` before the change, the root test failed for `AGENTS.md` before the fix, and the scaffold-only test failed before its fix. Timing, compiled modules, interleaved, best of 9 batches: the token reader of one app with 7 CSS files, develop 1.06, 1.06 and 1.05 ms against this branch 1.06, 1.06 and 1.06 ms; the whole `ui_findings` call, develop 9.7 to 10.1 ms against this branch 9.4 to 10.1 ms; loading `ui_rules`, `ui_audit_rules` and `comments` in a fresh process, develop 34.5 to 35.2 ms against this branch 34.8 to 35.2 ms. Token count of the shared `AGENTS.md` with tiktoken (o200k_base and cl100k_base gave the same numbers): develop 929, this branch 928; bytes 3859 to 3874 characters, 3916 bytes against the 3921 cap in `tests/test_agent_hooks.py`.
E2E: N/A — no user journey changes; the hook runs inside the tests through `validate_suppressions` on invented repositories.
Real service: N/A — the change calls no outside service.
Review declined: unquoted `@import url(../x.css)` escapes the outside check :: the shared import reader already reads only quoted forms for every rule and for the import order, so the form was outside the reader before this change, and the Tailwind setups that Hard Eng supports quote their imports.
Retro: (1) Escaped bug: a root `AGENTS.md` change in a Hard Eng update ran only the secret scan, so a root test of the shared group skipped and the project's main failed → `tests/test_root_change_checks.py::test_a_root_file_runs_the_shared_checks_unless_it_is_documentation`; the gate that should have caught it is the `impact` step of the `hard-eng` CI job, which now runs the shared checks. (2) HE-FILE-LENGTH refused `tests/test_ui_rules.py` at 1130 lines in the Ready check → None — the check caught it and the new tests moved to their own file. (3) `tests/test_skill_links.py` refused `gates.md` at 36024 bytes after the commit → the HE Build step that runs it after each reference edit; the later edits ran it first. (4) The independent review found that my first fix missed the scaffold-only shortcut and that the import finding fired on old lines → `tests/test_scaffold_replay.py::test_update_that_changes_the_project_rules_file_is_not_scaffold_only` and `tests/test_ui_outside_tokens.py::test_an_old_outside_import_does_not_fail_a_class_the_app_defines`; the shortcut came from reading the plan's test, not the real update path, so the escaped-bug test now runs the update route. (5) A test that I wrote asserted on the generic rule header, so it passed or failed for the wrong reason → None — the red-first run showed the wrong cause and the assertion now names the token.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
