# The join merge runs its protection step inside ship

Status: Ready

## Outcome + scope

`ship --stage merge` merges a join pull request into `develop` by itself, lifting only the linear history rule for the merge and putting the saved protection back; this repository also leaves its full pre-push check to CI. Non-goals: any change to rebase merges, releases or hotfixes; turning the GitHub setting off for good; copying review or push restrictions, which the step refuses instead.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's message of 2026-11-20 with the maintainer's standing approval. It points to a saved example of the manual step (the full protection body, the same body with the rule off, a compare script); that example is evidence for the converter, not a requirement.

## Repository context

Owners: `.hooks/ship_record.py` (`route`, `merge_method`) names the join route and the method. `.hooks/ship_actions.py` (`merge`) owns the merge call at the `merge` stage. The new `.hooks/join_merge.py` owns the protection read, lift, restore and compare. `.hooks/merge_guard.py` owns the refusal of a typed merge. `hard-eng.gates.json` holds the shipping policy; `.agents/skills/he-ship/references/checks.md` holds the `"ci"` rules.
Same cause: the manual off and on step lived in `AGENTS.override.md` and in a coordinator's habit, so each join risked a forgotten restore. Searched the docs and skills for other copies of the typed join step (`command grep -rni` over `.agents`, `docs`, `README.md`): only `AGENTS.override.md` names it.
Single source: the join route decision stays in `ship_record.route`; the new module reuses the method the record names and the record reader of `merge_guard.record_for`; the protection field names live once in `join_merge.py`. No other copy found.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Decision record: `docs/adr/0004-join-merges-keep-linear-history.md`.
Authority: Autonomous. The maintainer approved on 2026-11-20: keep develop's linear history rule and move the join merge's off and on step into Hard Eng; and "ok" to the "ci" pre-push setting for this repo after release 658. Merge: after release 658, by the coordinator.

## Acceptance + steps

- [x] A join merge lifts only `required_linear_history`, merges with `--merge` and the exact head, and puts the saved protection back → `tests/test_join_merge.py::test_the_join_merge_lifts_only_the_linear_history_rule_and_puts_the_protection_back`
- [x] The protection is put back when the merge fails → `tests/test_join_merge.py::test_the_protection_is_put_back_when_the_merge_fails`
- [x] A failed put back is tried again; one that never works fails loudly and says the join was merged → `tests/test_join_merge.py::test_a_failed_put_back_is_tried_again_and_the_merge_stays_done`, `::test_a_put_back_that_never_works_fails_loudly_with_the_saved_protection`
- [x] A protection that differs after the put back fails loudly → `tests/test_join_merge.py::test_a_protection_that_differs_after_the_put_back_fails_loudly`
- [x] A pull request that is not a join, or a join that fails ship verification (the merge stage runs the same checks as `ship ready` and writes the record), is refused with no call → `tests/test_join_merge.py::test_a_pull_request_that_is_not_a_join_is_refused_with_no_call`, `::test_a_join_that_fails_ship_verification_makes_no_github_call`
- [x] A base without the rule, or with no protection, merges with no protection write → `tests/test_join_merge.py::test_a_base_without_the_rule_is_merged_with_no_protection_write`, `::test_a_base_with_no_protection_is_merged_with_no_protection_write`
- [x] A failed read, or a protection the write cannot copy (reviews, restrictions, signatures, an unknown field, a status check list that is not exactly the known shape), stops before any write → `tests/test_join_merge.py::test_a_failed_protection_read_stops_before_any_write`, `::test_a_protection_that_the_put_cannot_copy_stops_before_any_write`
- [x] `ship --stage merge` sends a join through the step and a release around it → `tests/test_join_merge.py::test_ship_merge_sends_a_join_through_the_protection_step_and_a_release_around_it`
- [x] `ship ready` records the method `join` for a join → `tests/test_ship_routes.py::test_a_release_or_join_passes_ship_with_a_merge_commit_beyond_the_commit_limit`
- [x] Only a join keeps its own error when GitHub cannot rebase the pull request; other methods keep the rebase advice → `tests/test_join_merge.py::test_only_a_join_keeps_its_own_error_when_the_pull_request_cannot_be_rebased`
- [x] A stop signal during the merge still puts the protection back → `tests/test_join_merge.py::test_a_stop_signal_during_the_merge_still_puts_the_protection_back`
- [x] A stop signal during the put back waits until the protection is back, then ends the process → `tests/test_join_merge.py::test_a_stop_signal_during_the_put_back_waits_until_the_protection_is_back`
- [x] An interrupt (Ctrl+C) during the put back waits too, and a stop never hides a put back that failed → `tests/test_join_merge.py::test_an_interrupt_during_the_put_back_waits_until_the_protection_is_back`, `::test_a_stop_signal_does_not_hide_a_put_back_that_failed`
- [x] A typed `gh pr merge` for a join is refused and names the ship command → `tests/test_merge_refusal.py::test_a_typed_merge_of_a_join_is_refused_and_names_the_ship_merge_command`
- [x] `shipping.pre_push_checks` is `"ci"` in this repository and `check --quick` accepts it → N/A — a setting; the `check --quick` run under Verification reads it
- [x] `AGENTS.override.md` says that `ship --stage merge` does the join merge → N/A — a sentence; read in the diff

## Baseline + execution

Result: Passed
Evidence: Before the code, `tests/test_join_merge.py` failed to import `join_merge`; the route and guard rows failed on the old method. After the code the four test files pass (505 tests).
Execution: One builder in this worktree.
Changed test: the join row of `tests/test_ship_routes.py` asserted the method `merge`; it protected "a join passes ship with a merge commit" and now asserts `join`, the method that sends the merge through the protection step. The release row still asserts `merge`.

## Risks + recovery

A write that fails half way leaves `develop` without its rule: the step retries the put back, then fails with the body to put back by hand. The step refuses a protection that holds review or push restrictions, signatures or an unknown field, because the write replaces the whole protection. Recovery: revert the commit; a join then needs the manual step.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The focused tests (`tests/test_join_merge.py`, `test_ship_routes.py`, `test_merge_refusal.py`, `test_ship_actions.py`) pass. `ruff format --check`, `ruff check`, `pyrefly` and `vulture` pass with the commands of the gates file, and `jscpd` found 0 clones in 305 files. `python3 .hooks/hard-eng.py check --quick --plan-stage Ready --base origin/develop` exits 0 with `pre_push_checks` set to `"ci"`; its config load runs `load_checked_policy`, and a direct call accepts this repository and refuses it with the `secrets-history` gate removed. Converter against the saved real example of the manual step: 1 saved protection, 2 bodies (rule on, rule off), both equal the saved bodies byte for byte as data. Limits, not compared with GitHub: a null `app_id` becomes `-1` from the documented PUT field; a protection with reviews, restrictions, signatures or an unknown field is refused, not copied. Review declined: restoring over a protection change that a maintainer made during the seconds of the join :: the window is seconds long and only a maintainer can edit the protection; a compare before the put back would add a read for a case that has not happened.
Not run: `check --plan-stage Complete`, which refuses this plan on the Real service line only, because Complete accepts no `Required` and no `Pending` there.
E2E: N/A — the change is a merge step with a fake `gh`; the real round trip is the Real service line.
Real service: Required — GitHub branch protection API: the first real join after release 658 runs the protection read, the lift, the merge and the put back, and the read back must equal the saved copy
Retro: Escaped bug: none; the manual step was a known gap, not a defect.

Delivery target: Merge

Delivery: Pending — required remote proof.
