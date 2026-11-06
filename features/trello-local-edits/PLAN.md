# Keep a project's own edits to the Trello coordinator across updates

Status: Complete

## Outcome + scope

A project can commit its own changes to the `trello-coordinator` skill: extra rules, extra script commands, changed text. A Hard Eng update then adds the release's new lines into those files and keeps the project's lines. A change that edits the same lines both sides stops the update and names the file. Non-goals: other skills, `.hooks/`, `hard-eng.gates.json`, workflows and `AGENTS.md` (these stay forced, because they are the checks); uncommitted edits (the update still asks for a commit first); `--replace-scaffold` (still overwrites).
Also: the coordinator runs Hard Eng's `update-pr` itself during project health, so a waiting update does not show up in every run's report.

## Repository context

Owners: `setup.py` `scaffold_changes` (plans each shipped file), new `.hooks/local_edits.py` (the merge; `setup.py` is at its line limit), `.hooks/update.py` `update_plan` and `release_installed` (apply the plan and prove the update PR), `.agents/skills/trello-coordinator/SKILL.md` (own-edits line, `update-pr` exception), `references/run.md` (project health).
Cause: `scaffold_changes` refuses a file when it differs from both the new release and the previous release. It does not check whether the release changed that file. So one committed local line in any skill file blocks every later update, and the replay check on the update PR (`release_installed`, previous = new release) refuses too.
Same cause: every shipped file has this refusal; `tests/test_scaffold_replay.py::test_update_still_refuses_an_edited_skill_file` keeps it for skills outside this scope.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-06 asked that a project can edit and add to the coordinator script and that an update adds the new parts without removing theirs, then answered "yes" to this plan with the `update-pr` rule, merge after green checks.
Decision: three-way merge in place with `git merge-file` (project file, previous release, new release). Clean merge, the merged text is installed. Overlap, the update stops and names the file.
Decision: scope = files under `.agents/skills/trello-coordinator/` only. One path check; widening later is one line.
Decision: a merged `.py` file must still compile; else the update stops and names the file. Kada-style gates do not type-check the skill's Python, so a clean text merge could install broken code.
Rejected: a separate project file beside the skill (like `AGENTS.override.md`). Abid asked to edit the script itself.

## Acceptance + steps

- [x] A committed local line in a coordinator file stays after an update that changes other lines of that file, and the new release lines arrive → `tests/test_scaffold_replay.py::test_update_merges_local_coordinator_edits`.
- [x] The local line stays across two releases in a row → `tests/test_scaffold_replay.py::test_local_coordinator_edits_survive_two_releases`.
- [x] A release that does not touch the edited file leaves it unchanged, with no write → `tests/test_scaffold_replay.py::test_untouched_coordinator_file_keeps_local_edits`.
- [x] Same lines changed both sides → refused, file named, tree unchanged → `tests/test_scaffold_replay.py::test_overlapping_coordinator_edit_is_refused`.
- [x] A merged `.py` file that does not compile → refused, file named → `tests/test_scaffold_replay.py::test_merged_coordinator_script_must_compile`.
- [x] The update PR replay check accepts the merged files → `tests/test_scaffold_replay.py::test_update_merges_local_coordinator_edits` (asserts `check_scaffold_update`).
- [x] The coordinator's project health runs `update-pr` itself, and the core rules allow that one exception → `tests/test_trello_coordinator.py::test_skill_states_scheduling_roles_and_simplify_loop`.
- [x] Edited files in other skills are still refused → `tests/test_scaffold_replay.py::test_update_still_refuses_an_edited_skill_file`.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` exit 0 on `origin/develop` plus this plan.
Execution: one session; the five merge tests failed first; merge called from `scaffold_changes`, which already has the project file, the previous release and the new text, so no second pass in `update.py`.
Uncertainty resolved: `release_installed` replays with previous = new release, so the project file wins and the replay plans no change; the first test's `check_scaffold_update` assertion passes.

## Risks + recovery

A clean text merge can still change meaning; the compile check catches only syntax. Recovery: revert this pull request; projects then get the refusal again and can reset to the shipped file.

## ux_reference

N/A — no app screens change; only updater messages.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Complete` exit 0; 2272 tests passed, including 7 scaffold replay tests and the coordinator skill test.
E2E: N/A — no user journey; the update tests run the real updater on real git repositories. A Kada update after release is a delivery check, not a test.
Delivery target: PR
Delivery: Pending — PR into develop.
