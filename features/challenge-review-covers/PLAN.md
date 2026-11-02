# A narrow challenge rerun counts only on top of a full review

Status: Complete

## Outcome + scope

Shipping a big change accepts an independent review only when the reviews together cover the whole branch from its branch point. Before, the record was keyed by HEAD alone. A first run with `--base HEAD~1` reviewed one commit, and ship then printed "Independent review by codex: clean" for the whole branch. Now `challenge` records which branch point a review covers. A `--base` run counts only when that base revision has its own completed review. Non-goals: the documented narrow re-review flow (it keeps working), the `not done` note contract and the reviewer prompt.

## Repository context

Owners: `challenge` and `shipping_note` in `.hooks/challenge.py`; the reference `.agents/skills/code-review/references/challenge.md` tells agents to rerun with `--base <last reviewed SHA>`. `ship_actions.py` is the only caller of `shipping_note`. `default_branch_point` in `.hooks/plans.py` returns `None` when no branch point exists.
Cause: idea from the 2026-11-02 reference repo watch (an eval harness that reused a cached grade for a different selection). Hard Eng had the same class of gap: the review record did not say what range it reviewed.
Same cause: no other stored result is keyed by HEAD alone; the Stop hook already keys on base and file hashes.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the weekly reference repo watch task authorizes adopt/adapt PRs into `develop`, failing test first.
Decided: store `covers` (the branch point) in each record. A run without `--base`, or with `--base` at the branch point, covers it directly. A run with another `--base` inherits `covers` from that revision's completed record, or records `not done` without starting the reviewer. Ship refuses a record whose `covers` differs from the current branch point. When no branch point exists, behavior is unchanged.

## Acceptance + steps

- [x] A first review with a narrow `--base` records `not done`, does not start the reviewer and does not satisfy ship → `tests/test_challenge.py::test_a_narrow_review_without_an_earlier_review_does_not_cover_the_branch`.
- [x] A narrow rerun after a full review still satisfies ship → `tests/test_challenge.py::test_a_narrow_rerun_after_a_full_review_covers_the_branch`.
- [x] A failed rerun replaces a completed record that does not cover the branch, so ship gets the `not done` note instead of a lasting refusal → `tests/test_challenge.py::test_a_failed_rerun_replaces_a_completed_review_that_does_not_cover_the_branch`.
- [x] A rejected narrow rerun keeps the full review of the same revision and its findings → `tests/test_challenge.py::test_a_rejected_narrow_rerun_keeps_the_full_review_of_the_same_revision`.
- [x] The reviewer diffs from the same commit that the coverage check resolved, so a moving ref cannot shift the range → `tests/test_challenge.py::test_the_reviewer_diffs_from_the_base_commit_checked_for_coverage`.

## Baseline + execution

Result: Passed
Evidence: on `develop` 8e666dc the first new test failed (`challenge` returned 0, not 1); the rerun test passed.
Execution: One builder, this session. Failing test first, then the `covers` field in `challenge.py`.

## Risks + recovery

A record written before this change has no `covers`, so ship asks for one new `challenge` run on that revision. Revert the commit to restore the old behavior.

## ux_reference

N/A — hook behavior with no visual surface.

## Verification

Result: Passed
Evidence: `tests/test_challenge.py` and `tests/test_ship_actions.py` pass after the fix. The pre-push gate runs the full suite on this commit.
E2E: N/A — the unit tests drive the real `challenge` and `shipping_note` with a fake reviewer CLI.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
