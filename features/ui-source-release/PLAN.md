# Release HE-UI-SOURCE: a true list that every installed project can act on

Status: Ready

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

- [ ] An update leaves `ui_library` to the project, so the pushed policy holds no key that an older release refuses, and a replay of the update plans no change → `tests/test_scaffold_replay.py::test_an_update_leaves_the_ui_library_key_to_the_project`; a first install still writes the `ui` default → `tests/test_scaffold_replay.py::test_a_first_install_writes_the_ui_library_default`.
- [ ] A `components` folder gets no guessed library, because a guess there cut base element findings from 315 to 2 on a real web app → `tests/test_scaffold_replay.py::test_setup_writes_no_library_for_a_components_folder`.
- [ ] An empty `ui_library` refusal names the key and the value form, and the exact value when one `ui` folder holds the shared parts → `tests/test_ui_library_refusals.py::test_the_empty_library_refusal_names_the_key_and_the_value`.
- [ ] A stylesheet or component file outside `ui_paths` names both fixes: add its folder to `ui_paths` when users receive it, or remove a preview from git → `tests/test_ui_library_refusals.py::test_a_file_outside_ui_paths_names_both_fixes`.
- [ ] A library of 2,000 parts passes the index check, and the look excerpt keeps `DESIGN.md` within its byte limit; no refusal and no limit change is needed → `tests/test_ui_library_refusals.py::test_a_large_library_passes_the_index_check_and_the_look_excerpt_stays_bounded`.
- [ ] The text of a failed update push says the rule is intended, has no waiver, and is fixed in the project → `tests/test_update_pr_refusal.py::test_a_refused_push_of_the_update_branch_names_the_next_step`.
- [ ] A real update on a project that sits on the old release pushes past the old pre-push check and reports the true list → `tests/test_scaffold_replay.py::test_an_update_leaves_the_ui_library_key_to_the_project` for the update and its replay; the run on the old release's own hooks is in Verification Evidence.

## Baseline + execution

Result: Passed
Evidence: 2026-11-24, develop 069ccacd. A real `update-pr` run on a fixture installed from the old release (a web project with a `ui` folder) was refused by the old pre-push check: `Pushed commit has an invalid hard-eng.gates.json: shipping policy has unknown or missing keys`, because setup wrote `ui_library`.
Execution: One builder, this session.

## Risks + recovery

A project that updates gets no default library even when its folder is `ui`; its first check names the exact value to add. A tracked preview folder with a stylesheet stays a finding: no repository signal tells a preview from a served page, and a reachability rule would hide a UI folder missing from `ui_paths`. The refusal gives both fixes. Recovery: revert the commits.

## ux_reference

N/A — check messages only; no visible UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — no user journey changes; the real update run of a fixture on main's hooks is recorded in Evidence.
Real service: N/A — the change calls no outside service.
Retro: Pending

Delivery target: Merge
Delivery: Pending — required remote proof.
