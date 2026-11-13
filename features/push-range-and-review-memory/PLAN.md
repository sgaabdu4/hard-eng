# A push judges what CI judges, mutation stops rewriting shared tools, and the review keeps its memory

Status: Ready

## Outcome + scope

Three faults from user feedback. (1) A branch that added a test in one push and deleted it in a later push passed `check` and CI but was refused by the later push, because pre-push counted assertion lines only over the range since the remote tip. (2) Each pre-push Dart mutation run ran `dart pub global activate mutation_test`, which rewrites the command files in the shared pub cache while another checkout may read them. (3) Each `challenge` run started with no memory, so it repeated old findings and contradicted decisions, and a rebase hid the stored reviews from `--base`.

Non-goals: a new `check` option, a changed `check` comparison, a per-test loss rule, a lock or cache for the activation, moving the review store, a fallback reader for old stores, any change to `plans.py`, the project command that activates `coverage` in two packages at once.

## Repository context

Owners: `.hooks/comments.py` (`validate_suppressions`, `assertion_balance`), `.hooks/mutation.py` (`dart`), `.hooks/challenge.py` (`earlier_reviews`, the prompt), `.agents/skills/code-review/references/challenge.md`.
Same cause: Repair 1 sweep of every rule that pre-push runs on the pushed range. `validate_suppressions` counts a net value over the range and reads `Removed test:` lines added inside it: repaired here. The other checks of `validate_suppressions` (switch-off patterns, retry forms, marks) and the comment rule and the UI rule read only added lines, and each earlier push was already checked, so the per-push and the whole-branch answers agree. `validate_plans` reads the plan files, not a range total. Other callers of `diff_base` are listed in the report; none counts a net value. Repair 2: `.hooks/mutation.py` holds the only `global activate` in `.hooks`; the vendored copies under `.agents/skill-sources/` are older snapshots of the same file and are not part of this change. The project command that activates `coverage` stays a project fix.
Single source: the assertion count had one copy in `validate_suppressions`; it moved to `assertion_balance`. The reflog walk and the `Review declined:` reader have one owner, `challenge.py`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer set the three changes and their decisions; the coordinator reviews the commits before any push.

## Acceptance + steps

- [ ] A test added by an earlier push and deleted by a later push loses nothing → `tests/test_comments_push_range.py::test_a_test_the_branch_added_and_a_later_push_deleted_loses_nothing`.
- [ ] A `Removed test:` record from an earlier push still lets a later push pass → `tests/test_comments_push_range.py::test_a_removed_test_recorded_in_an_earlier_push_passes_a_later_push`.
- [ ] Assertions moved between test files across two pushes pass → `tests/test_comments_push_range.py::test_assertions_moved_between_test_files_across_two_pushes_pass`.
- [ ] A real `git push` accepts a test that the branch added and then deleted → `tests/test_comments_push_range.py::test_pre_push_accepts_a_test_the_branch_added_then_deleted`.
- [ ] A net loss from the branch point still fails a later push, and the message names the range → `tests/test_comments_push_range.py::test_a_net_loss_from_the_branch_point_still_fails_a_later_push` and `::test_the_loss_message_names_the_range_it_judged`.
- [ ] An active Dart mutation tool gets no activation call; a missing one gets exactly one → `tests/test_mutation.py::test_an_active_dart_mutation_tool_is_not_activated_again` and `::test_a_missing_dart_mutation_tool_is_activated_once`.
- [ ] A later review run gets the earlier findings and the focus on the new commits → `tests/test_challenge.py::test_a_later_run_gets_the_earlier_findings_and_focuses_on_the_new_commits`.
- [ ] A `Review declined:` plan line reaches the next run with its reason → `tests/test_challenge.py::test_a_declined_finding_in_the_plan_reaches_the_next_run_with_its_reason`.
- [ ] Earlier findings survive a rebase onto a moved base → `tests/test_challenge.py::test_earlier_findings_survive_a_rebase_onto_a_moved_base`.
- [ ] Earlier text sits in a nonce fence it cannot close → `tests/test_challenge.py::test_earlier_review_text_is_fenced_and_cannot_close_the_fence`.
- [ ] The command prints the counts and the focus commit → `tests/test_challenge.py::test_the_command_prints_how_many_earlier_reviews_and_decisions_it_passed`.
- [ ] Records of an earlier task on a reused branch name are not passed, and a huge earlier output keeps the prompt under the byte limit → `tests/test_challenge.py::test_records_of_an_earlier_task_on_a_reused_branch_name_are_not_passed` and `::test_the_prompt_stays_under_the_byte_limit_with_a_huge_earlier_output`.
- [ ] Nothing new loads at session start or at Stop → `tests/test_gate_speed.py`.

## Baseline + execution

Result: Passed
Evidence: `develop` was clean at the branch point. Before the fix, the five push range tests failed with "tests lose 2 assertion lines net"; the guard passed.
Execution: one builder session; tests first for each repair, one commit per repair, then the docs.

## Risks + recovery

A stale `mutation_test` install is no longer upgraded on each run; `dart pub global activate mutation_test` upgrades it by hand. A wrong `Review declined:` line can settle a valid finding; the skill text says the host never writes one for a finding it did not verify. Recovery: revert the commit of the repair.

## ux_reference

N/A — no app screens change.

## Verification

Result: Pending
Evidence: Pending until the Complete check runs.
E2E: N/A — no user journey; the push row runs a real `git push` through the pre-push hook and the review rows run the command with a fake reviewer CLI.
Retro: Pending until the Complete check runs.
Delivery target: Merge
Delivery: Pending — the coordinator reviews the commits, then ships.
