# Use PR base SHA for post-merge unchanged capture checks

Status: Complete

## Outcome + scope

Read `base.sha` from the GitHub pull request response in `.hooks/shipping.py` and pass it into `.hooks/ui_proof.py` `merge_base()` so `ship --stage delivered` compares an `N/A — unchanged:` capture pair against the PR's pre-merge base commit instead of `HEAD` after `origin/<base_ref>` advances to include the merge. Non-goals: changing web or native UI proof requirements.

## Sources + coverage

Sources: N/A — live `ship --stage delivered` failure after merging an `N/A — unchanged:` web PR where `git merge-base HEAD origin/main` returned `HEAD`.
Deliverables: None

## Repository context

Owners:
- `.hooks/shipping.py` parses GitHub pull request metadata (`_PullRequest.base_sha`).
- `.hooks/ui_proof.py` resolves the comparison base in `merge_base()` and runs `unchanged_problem()`.
- `tests/test_ui_capture_match.py` tests unchanged capture matching.

Same cause: After merge, `origin/<base_ref>` already contains the PR head, so `git merge-base HEAD origin/<base_ref>` returns `HEAD`, making `unchanged_problem` demand a Before capture taken at `HEAD`. Passing `base.sha` from the PR payload preserves the pre-merge fork point before and after merge.
Single source: `.hooks/shipping.py` (`_PullRequest.base_sha`) and `.hooks/ui_proof.py` (`merge_base`).

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous. Bugfix discovered during maintainer-authorized rollout delivery verification.

## Acceptance + steps

- [x] `shipping.verify(..., "delivered")` parses `base.sha` from the PR response and accepts a clean `N/A — unchanged:` pair after `origin/main` advances to `HEAD`, while rejecting when `base.sha` is absent → `tests/test_ui_capture_match.py::test_unchanged_pair_uses_pr_base_sha_after_merge`.
- [x] Existing shipping and UI quality tests remain green → N/A — `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` is the proof.

## Baseline + execution

Result: Passed
Evidence: Before the fix, moving `refs/remotes/origin/main` to `HEAD` caused `merge_base(root, "main")` to return `HEAD`, failing `unchanged_problem` on a valid pre-merge Before capture. Adding `base_sha` to `_PullRequest` and `merge_base()` makes `test_unchanged_pair_uses_pr_base_sha_after_merge` pass.
Execution: Single builder in isolated worktree: add `base_sha` in `shipping.py`, update `merge_base()` and `ship_problem()` in `ui_proof.py`, add regression test in `tests/test_ui_capture_match.py`, run full check and independent challenge.

## Risks + recovery

If `base_sha` is absent from a test stub or not fetched locally, `merge_base()` falls back to `origin/<base_ref>`, preserving existing behavior. Recovery: revert the merge commit on `develop`.

## ux_reference

N/A — shipping hook Python logic has no user interface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_ui_capture_match.py tests/test_shipping_ui_evidence.py` passed, and full `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` ran on the committed branch.
E2E: N/A — CLI/hook shipping check has no interactive user journey; the regression test exercises real `git merge-base` on a temporary repo with `origin/main` moved to `HEAD`.
Real service: N/A — no changed code calls an outside service (`base.sha` is already present in GitHub's PR payload).
Retro: `ship --stage delivered` failed on a merged web PR using `N/A — unchanged:` because `merge_base()` queried `origin/<base_ref>` after merge → pass `pull.base_sha` into `merge_base()` and keep the regression test in `tests/test_ui_capture_match.py`.
Delivery target: PR
Delivery: Pending — checks, challenge, PR to `develop`, CI, and merge.
