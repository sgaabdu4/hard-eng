# Update PRs merge past a review only their author could give

Status: Complete

## Outcome + scope

`update-pr` merges a green update PR whose only blocker is a required review that nobody but the author could give, with the same checks `ship` already uses for that case. `ship` also stops refusing the bypass when the rule asks for a code-owner review and CODEOWNERS names only the author for every file. Non-goals: reviews another person can give, team code owners, partial CODEOWNERS patterns, merge queues and every other merge rule.

## Repository context

Owners: `_review_bypass_problem` in `.hooks/shipping.py` allows an admin merge only when every other blocker is absent and no other collaborator can push. `settle` in `.hooks/update_pr.py` always asked for auto-merge.
Cause (seen on 2026-11-02 in a project installed from this repository): the base branch ruleset requires one approving code-owner review, and CODEOWNERS is `* @<owner>`. The update PR author is that owner, so nobody can approve it. A second collaborator with write access exists, so `ship` refused the bypass, though their approval cannot satisfy a code-owner rule. `update-pr` asked for auto-merge on every rerun and the PR never merged. Every earlier update PR in that project was merged by hand with an admin merge.
Same cause: none found; `ship` and `update-pr` are the only merge paths.
File length: `shipping.py` was at 996 of 1000 lines (HE-FILE-LENGTH), so the review-bypass group (query, rule checks, `bypass_problem`, the code-owner check and `author_only_review_block`) moves unchanged into `.hooks/review_bypass.py`, beside the existing `tests/test_review_bypass.py`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: the user asked on 2026-10-31 for every Hard Eng update to land in each project without asking, and for gaps found on the way to be fixed here, failing test first.
Decided: count the code-owner case only when CODEOWNERS has a `*` rule and every rule names exactly the author. Any other shape (team owners, extra owners, an unowned pattern, no file) keeps the old collaborator check, which refuses when someone else can push. `update-pr` asks for the bypass only when GitHub reports the PR as blocked, and runs the same review, check, thread and rule checks as `ship` before using `--admin`.

## Acceptance + steps

- [x] `ship` bypasses a code-owner review that only the author could give → `tests/test_review_bypass.py::test_ready_bypasses_a_code_owner_review_only_the_author_can_give[codeowners0-True-None]`.
- [x] `ship` still refuses when someone else could review: extra owner, no code-owner rule, unowned pattern, no `*` rule, team owner or no CODEOWNERS → `tests/test_review_bypass.py::test_ready_bypasses_a_code_owner_review_only_the_author_can_give[codeowners3-True-another]`.
- [x] The public check refuses an unresolved conversation, another reviewer and a PR that is not blocked → `tests/test_review_bypass.py::test_author_only_review_block_reads_the_open_pull_request[blocked-threads1-others1-conversation]`.
- [x] `update-pr` uses `--admin` only when the PR is blocked and nobody else can review; otherwise it keeps auto-merge and prints why → `tests/test_update_pr.py::test_update_pr_merges_past_a_review_only_its_author_could_give[BLOCKED-None---admin]`.

## Baseline + execution

Result: Passed
Evidence: on `develop` 1252bc8 the code-owner cases failed with `PR mergeability is not clean: another collaborator can give the review`, and the other new tests failed because `author_only_review_block` did not exist.
Execution: One builder, this session. Failing tests first, then the code-owner check, the public helper and the `update-pr` merge flag, then the move to `review_bypass.py`.

## Risks + recovery

An admin merge skips the review rule, so the code-owner case accepts only the narrowest CODEOWNERS shape and keeps every other `ship` precondition. A misread falls back to auto-merge, which waits as before. Revert the commit to restore the old behavior.

## ux_reference

N/A — command behavior with no visual surface.

## Verification

Result: Passed
Evidence: before the move, `tests/test_shipping.py` and `tests/test_update_pr.py`: 141 passed. After the move, the six shipping, review-bypass, ship-action and update-pr test files: 233 passed. The full `check` runs before the push.
E2E: Passed — read-only run against the real GitHub API on the project's blocked update PR (merged by hand before this fix): the extended query parsed, the rule reported `requireCodeOwnerReview: true`, `_sole_code_owner` returned true and `_other_merge_requirement` found nothing else. No merge was attempted.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
