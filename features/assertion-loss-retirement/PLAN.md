# Let tests retire with the code they cover in the assertion-loss check

Status: Complete

## Outcome + scope

Issue 250. `validate_suppressions` failed any change whose test files lost more assertion lines than they gained, even when the code under test was deleted in the same change, so retiring a migration or a compatibility path could not pass `check`, pre-push or CI. Removed assertions now stop counting when the removed test names a definition (function, class, top-level name) or a deleted module that the same change removed and that no remaining non-test code file still uses. Each removed test is judged on its own, so deleting a mixed test file still counts the tests for kept code. Words in removed strings and comments, and local variables, never count as retired. Names bound by a removed import of a deleted module count across the whole test file. The plan-field alternative from the issue is not added. No new file other than this plan.

## Repository context

Owner: `.hooks/comments.py` `validate_suppressions`, called from `check` in `.hooks/hard-eng.py`, which pre-push and the CI `hard-eng` job both run. Test paths come from `plans._is_test`. The retirement lookup reads remaining code only when the assertion count would otherwise fail, so passing changes do no extra work.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open issues (250 was the only one open) and to run a GPT-6 Astra Codex adversarial review loop before the PR, acting only on genuine, realistic, substantial findings.

## Acceptance + steps

- [x] Deleting a module with its test file, and a removed function with its test in a kept file, passes → `test_removing_tests_with_the_code_they_cover_passes`; failed on main, passes now.
- [x] Deleting tests for code that still exists fails → `test_removing_tests_for_code_still_in_use_fails`, `test_deleting_a_test_file_without_replacement_fails`.
- [x] A deleted test file that also covers kept code still counts those tests → `test_deleting_a_test_file_that_also_covers_kept_code_fails` (Codex round 1).
- [x] Changing an error message does not excuse deleting its test → `test_changing_a_message_does_not_excuse_deleting_its_test` (Codex round 1).
- [x] Inlining a local variable does not excuse deleting a test that uses the same name → `test_inlining_a_local_does_not_excuse_deleting_its_test` (Codex round 2).
- [x] A removed import of a deleted module reaches a removed test in a separate hunk → `test_retired_import_reaches_a_test_in_a_separate_hunk` (Codex round 2).
- [x] Removing a typed Dart constant (`const String legacy`) with its test passes → `test_removing_a_typed_dart_constant_with_its_test_passes` (challenge review).
- [x] Full check passes.

## Baseline + execution

Result: Passed
Evidence: main at 99634e5; its full `check` passed on this branch's first commit before the later review fixes.
Execution: Single session on `fix/assertion-loss-deleted-subject`; three Codex adversarial review rounds on GPT-6 Astra, then `hard-eng.py challenge`.

## Risks + recovery

The exemption is a name match, not a call graph: a removed test for kept code that happens to use a removed, now-unused definition name passes. Left unfixed after Codex round 3 as unrealistic: a test file that imports the same name from both a deleted module (renamed with `as`) and a kept module, then deletes the kept module's test too. Left unfixed after the challenge review as unrealistic or failing safe: Vitest tagged-template `test.each` blocks in a deleted mixed file, test data strings equal to a retired name, an `as` alias of a retired function from a kept module, and a multiline import whose names collide with kept code. A Dart test that reaches a deleted file only through a package import, and whose body names only definitions still used elsewhere, still fails the check (safe direction). Recovery is reverting this branch.

## ux_reference

N/A — check error text only; no product appearance.

## Verification

Result: Passed
E2E: Passed — in a scratch Git project with this branch's `.hooks`, a commit deleting `migrate_users.py` and `tests/test_migrate.py` (while `jobs.py` keeps its own `run`) passed `validate_suppressions` against its parent; the same commit with main's `comments.py` failed with `tests lose 1 assertion lines net`. A following commit deleting the test for kept `app.keep` failed with the same message. The full `check` in that scratch project stopped earlier on its missing plan, so the validator was called directly, the same call `check` makes.
Evidence: `hard-eng.py check --base origin/main` exit 0: 18 checks passed, 1449 tests, 90.71% line coverage. Each new regression failed on the code before its fix.

Delivery target: Merge
Delivery: Passed — PR #251 CI passed; rebase-merged as dd4d846; `ship --stage delivered` passed on merged-main CI; the task branch was deleted locally and on GitHub after confirming main matched it.
