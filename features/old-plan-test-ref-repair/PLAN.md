# Allow repairing acceptance test references in old Complete plans

Status: Complete

## Outcome + scope

Extend `reformatted_plans` in `.hooks/change_size.py` so repairing only acceptance test references in an old `Complete` plan (one that fails newer plan-format rules such as `Same cause:`) treats that plan as unchanged after verifying every edited or affected test reference exists. Non-goals: exempting prose edits, checkbox changes, not-applicable weakening, or missing test references in old plans.

## Sources + coverage

Sources: N/A — escaped-bug fix for repairing acceptance test references in older `Complete` plans; no external specification.

## Repository context

Owners: `.hooks/change_size.py` (`normalize_acceptance_line`, `words_without_acceptance_refs`, `held_text`, `verified_test_ref_repair`, `reformatted_plans`) and `tests/test_planning_handoffs.py`.
Same cause: `reformatted_plans` compared full raw word lists (`held_words == plan_words`), so any change to a renamed test reference in an old `Complete` plan broke word equality and triggered full modern-plan validation on a historical file.
Single source: `.hooks/change_size.py` owns the old-plan reformat and test-ref-repair exemption; `.hooks/plan_tests.py` (`missing_tests`) owns test reference verification.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous maintenance — authorized post-release bug fix.

## Acceptance + steps

- [x] Repairing only acceptance test references in an old `Complete` plan that fails newer plan fields counts as unchanged (both on a plan-only edit and alongside a current branch `PLAN.md`), while an unbacked code/test change still requires its own plan → `tests/test_planning_handoffs.py::test_repairing_only_acceptance_test_refs_in_an_old_complete_plan_counts_as_unchanged`.
- [x] Repairing an old `Complete` plan with a missing test reference, weakening a test reference to not-applicable, or editing acceptance outcome wording is still refused → `tests/test_planning_handoffs.py::test_old_plan_test_ref_repair_still_refuses_missing_tests_na_or_word_edits`.

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`a2410e8b`), adding the two tests in `tests/test_planning_handoffs.py` reproduced the failure (`plan needs one 'Same cause:' field, found 0`) before editing `.hooks/change_size.py`.
Execution: Single builder in a linked worktree off `origin/develop`.

## Risks + recovery

An old plan could have an acceptance line with unusual punctuation between test references; `REF_CONNECTORS` handles standard prose connectors (`and`, `or`, commas, punctuation) and fails closed otherwise. Recovery: revert the commit in `.hooks/change_size.py` and the tests.

## ux_reference

N/A — Python hook validation logic and unit tests only; no visible UI.

## Verification

Result: Passed
Evidence: Failing-first reproduction failed on `Same cause:` before the fix; after the fix, `uv run pytest tests/test_planning_handoffs.py tests/test_plan_acceptance.py -q` passed (221 passed) and `python3 .hooks/hard-eng.py check --quick --base origin/develop --plan-stage Complete` passed.
E2E: N/A — hook unit tests exercise real temporary Git repositories with base and branch commits.
Real service: N/A — local Git and Python tests call no outside service.
Retro: Escaped bug — when a check tells a user to update a test reference in an older `Complete` plan, `reformatted_plans` must verify and allow test-reference-only repairs without demanding newer plan sections.

Delivery target: Merge
Delivery path: PR into develop.
Delivery: Pending — PR checks green, independent review complete, and merged into develop.
