# Release HE-UI-SOURCE: a true list that every installed project can act on

Status: Complete

## Outcome + scope

An installed project that updates to the release gets a true HE-UI-SOURCE list: the update pushes, the first failed check names the exact key and value to set, and the refusal for a file outside `ui_paths` offers both honest fixes. Non-goals: no folder-name guess for the library, no raised limit, no skip list, no waiver, no repair PR in any project, no new index format.

## Sources + coverage

Sources: N/A — the user's ruling of 2026-11-24 (release Hard Eng; each project meets the new rules on its next update; a false finding or a failure that a Hard Eng default causes blocks the release) and the maintainer's brief for this task, read in full.

## Repository context

Owners: `add_ui_library` in `setup.py` writes the default key; `setting_findings` and `coverage_findings` in `.hooks/ui_whole.py` own the refusal texts; `_policy` in `.hooks/shipping.py` owns the strict key list; `design_text` in `.hooks/look.py` owns the look excerpt.
Same cause: the same trap holds for any key that a release adds to `shipping`: an older release refuses the pushed policy. Only `ui_library` is new in this release; develop holds no other unreleased `shipping` key.
Single source: one owner for each rule: the key list in `shipping.py`, the default in `default_library`, the texts in `ui_whole.py`. No copy found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to release Hard Eng with every project updating on its own next run, and to make Hard Eng correct first.

## Acceptance + steps

- [x] An update leaves `ui_library` to the project, so the pushed policy holds no key that an older release refuses, and a replay of the update plans no change → `tests/test_scaffold_replay.py::test_an_update_leaves_the_ui_library_key_to_the_project`; a first install still writes the `ui` default → `tests/test_scaffold_replay.py::test_a_first_install_writes_the_ui_library_default`.
- [x] A `components` folder gets no guessed library, because a guess there cut base element findings from 315 to 2 on a real web app → `tests/test_scaffold_replay.py::test_setup_writes_no_library_for_a_components_folder`.
- [x] An empty `ui_library` refusal names the key and the value form, and the exact value when one `ui` folder holds the shared parts → `tests/test_ui_library_refusals.py::test_the_empty_library_refusal_names_the_key_and_the_value`.
- [x] A stylesheet or component file outside `ui_paths` names both fixes: add its folder to `ui_paths` when users receive it, or remove a preview from git → `tests/test_ui_library_refusals.py::test_a_file_outside_ui_paths_names_both_fixes`.
- [x] A library of 2,000 parts passes the index check, and `look` sends the design text whole while it fits the byte limit (96,000 bytes), so the index that Hard Eng requires never forces a cut: 200 parts with full use lines beside a 22,700-byte DESIGN.md, and 2,000 parts with short use lines, both reach the reviewer whole; a text over the limit is refused with each file named → `tests/test_ui_library_refusals.py::test_a_written_library_and_a_full_design_md_reach_look_whole` and `tests/test_ui_library_refusals.py::test_a_library_of_2000_parts_with_short_use_lines_reaches_look_whole` and `tests/test_look_design_limit.py::test_a_design_pair_over_the_limit_is_refused_with_each_size`.
- [x] The header of the HE-UI-SOURCE refusal, which the new release prints at the first failed check after an update, says the rule is intended, has no waiver and is fixed in the project → `tests/test_ui_library_refusals.py::test_the_ui_refusal_header_says_the_rule_is_intended_and_fixed_in_the_project`.
- [x] A real update on a project that sits on the old release pushes past the old pre-push check and reports the true list → `tests/test_scaffold_replay.py::test_an_update_leaves_the_ui_library_key_to_the_project` for the update and its replay; the run on the old release's own hooks is in Verification Evidence.

## Baseline + execution

Result: Passed
Evidence: 2026-11-24, develop 069ccacd. A real `update-pr` run on a fixture installed from the old release (a web project with a `ui` folder) was refused by the old pre-push check: `Pushed commit has an invalid hard-eng.gates.json: shipping policy has unknown or missing keys`, because setup wrote `ui_library`.
Execution: One builder, this session.

## Risks + recovery

A project that updates gets no default library even when its folder is `ui`; its first check names the exact value to add. A tracked preview folder with a stylesheet stays a finding: no repository signal tells a preview from a served page, and a reachability rule would hide a UI folder missing from `ui_paths`. The refusal gives both fixes. Recovery: revert the commits.

## ux_reference

N/A — check messages only; no visible UI.

## Verification

Result: Passed
Evidence: 2026-11-25. (1) Real runs of `update-pr` on a web project installed from the old release, with the old hooks as the running code and a fake GitHub API and `gh`: before the fix, the old pre-push check refused the push with `Pushed commit has an invalid hard-eng.gates.json: shipping policy has unknown or missing keys` (fixtures with a `ui` folder). After the fix, the pushed policy passes, the update is read as a verified scaffold update (`Plan: only files the verified Hard Eng update wrote; no plan needed.`) and the new release prints the true list: for a `ui` folder, `Add shipping "ui_library": ["src/ui/*"]`, a missing index, a missing design front matter and the base elements; for a `components` folder with `shared`, `Add shipping "ui_library": ["<folder>/*"]` and the base elements of all three files. Runs: 2 variants. (2) A guessed `components/*` library on one real web app cut the base element findings from 315 to 2, so no guess is written; the guessed `components/shared/*` left 234. (3) `coverage_findings` on two real checkouts: one stylesheet in a preview folder, and 525 files in a second app, a deck site and a video package. All are tracked UI files outside `ui_paths`, so they stay findings with both fixes named. (4) `check --base origin/develop --plan-stage Ready`: 7970 tests passed, all gates passed. Focused tests after the last edit: 103 passed. Static gates: format, lint, complexity, annotations, types, dead-code and duplicates passed. `check --plan-stage Complete --base origin/develop` passed on its fifth run; the first four stopped at the 1800 s limit of the tests gate while other work held the load average at 250 to 460, with no test failing.
Not checked: a full pass of the update branch after a project fixes its own list; the Mac canary (not asked for); a real GitHub run of the update PR.
E2E: N/A — no user journey changes; the real update run is in Evidence.
Real service: N/A — the change calls no outside service.
Retro: (1) the update trap: an older release refuses a new `shipping` key in the pushed policy, and the update replay must plan no change → `tests/test_scaffold_replay.py::test_an_update_leaves_the_ui_library_key_to_the_project`; (2) a text change in the update push wording does not reach the first failure, because the older release prints it → the header of the new check carries the line, held by `tests/test_ui_library_refusals.py::test_the_ui_refusal_header_says_the_rule_is_intended_and_fixed_in_the_project`; (3) the first plan of a key written only when the older release reads it broke the replay and the plan rule → None — the real run caught it before the push.

Delivery target: Merge
Delivery: Pending — required remote proof.
