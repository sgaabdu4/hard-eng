# Stacked green merges and cheap failures in ci mode

Status: Complete

## Outcome + scope

A typed rebase merge no longer lands a head that is behind its base, and a push in `pre_push_checks: "ci"` mode judges the plan and the changed lines before CI does. Non-goals: a network call in the merge hook; the full quick check in ci mode; any change to squash or release merges.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's message of 2026-11-18, two gaps found in a project retro and checked by an investigator on the base branch.

## Repository context

Owners: `.hooks/merge_guard.py` (`pr_merge_problem`) owns the typed merge rule. `.hooks/ship_actions.py` (`run`, `require_current`) owns the base currency check at the `ready` and `merge` stages. `.hooks/gate_runner.py` (`check_command`) runs `check --commit-secrets`, which `pre_push` already starts in ci mode; the new `.hooks/push_text.py` holds the three judgements it adds.
Same cause: gap 1 and gap 3 share one cause, a check that exists at one stage but is not run at the stage that needs it: base currency was checked by `ship` but a typed merge skipped `ship`, and the plan and text rules ran in the full check but ci mode skipped that check. Searched `.hooks` for other routes to a merge that skip `ship`: `update_pr.py` merges the Hard Eng update PR through `gh` inside Python, which the Bash hook does not see and which the plan exempts; the Codex rule file already refuses every typed `gh pr merge`.
Single source: the merge command text lives in `REBASE_STEP` in `merge_guard.py` and in one docs sentence in `checks.md`; the `--commit-secrets` help and the push message name the same three checks once each.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The coordinator named both gaps, the fix for each, the branch and the proof; the PR is not merged here and lands after release PR 658.

## Acceptance + steps

- [x] A typed `gh pr merge` with a rebase flag is refused even with a passed record, and the message names `ship --stage merge --merge-method rebase` → `tests/test_merge_refusal.py::test_a_typed_rebase_merge_with_a_passed_record_is_refused_and_names_the_ship_merge_command`
- [x] A typed merge for a squash-only repository and for the release route still passes with its record → `tests/test_merge_refusal.py::test_release_and_squash_only_merges_stay_possible`
- [x] The Bash hook loads no new module for an ordinary command or a `gh` read command → `tests/test_merge_refusal.py::test_a_gh_command_that_is_not_a_merge_loads_no_module`, and the module counts under Verification
- [x] In ci mode a Ready plan is refused before the push → `tests/test_push_text_checks.py::test_a_ready_plan_is_refused_before_the_push_when_ci_runs_the_full_check`
- [x] In ci mode a changed-line text finding is refused before the push → `tests/test_push_text_checks.py::test_a_changed_line_text_finding_is_refused_before_the_push_when_ci_runs_the_full_check`
- [x] In ci mode no gate of the full check runs → `tests/test_push_text_checks.py::test_a_complete_plan_and_clean_lines_pass_without_any_gate_of_the_full_check` and `tests/test_push_check.py::test_a_base_that_leaves_checks_to_ci_runs_one_cheap_check_and_no_full_gate_when_mutation_is_off`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` the four typed rebase rows (two forms of the pull request, two flags) fail, and the Ready plan and text finding tests fail; the clean test passes. After the change all pass.
Execution: One builder in this worktree.
Removed tests: two rows of the allowed list in `tests/test_merge_refusal.py` (a typed rebase merge with a passed record) protected "a recorded typed rebase merge passes"; that is now the refusal the new test proves. The old `tests/test_push_check.py` test of ci mode with mutation 0 protected "no full local gate runs": it asserted that pre-push starts only `check --commit-secrets`. It is kept under a new name and still asserts exactly that call list, so the protection stays; the new tests add that the one command runs no gate of the full check (`check` and `run_gates` raise if called).

## Risks + recovery

In ci mode a push with a plan that is not Complete is now refused locally. CI refused it too, so no push that passed before can pass now only locally. A work-in-progress push needs `--no-verify` or a Complete plan. Typed rebase merges that agents ran by hand now go through `ship --stage merge`. Recovery: revert the commit.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Focused tests, the static gates and the Complete check passed on the head. Timing of the ci-mode pre-push work on this repository against `origin/develop` with this change committed, 3 runs each, seconds: the secret scan alone took 3.08, 2.70 and 2.54; `check --commit-secrets` with the new judgements took 5.43, 4.75 and 3.49 (a whole command, so it includes the interpreter start). The new judgements add about 1 to 2.5 s. Module counts of the Bash hook (`polling.decision`, fresh interpreter) for `ls`, `gh pr view`, `gh pr view --json mergeStateStatus` and `git status`: no new module on the base or on the head; the merge command loads the same 25 modules on both.
E2E: N/A — the change is a refusal rule and a call order, proved by the tests above.
Real service: N/A — no service is called.
Retro: Escaped bug (gap 1): the gate that should have caught it is the merge refusal test set, `tests/test_merge_refusal.py`, which proved that a record gates a merge but never that the record can be older than the base; the guard only reads a file, so it cannot see the base moving. Fix at the cause: route rebase merges through `ship`, which checks currency at the moment of the merge. Gap 3: the tests for ci mode asserted the list of started commands and never what the pushed revision still had to pass.

Delivery target: PR
Delivery: Pending — required remote proof.
