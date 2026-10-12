# Fix the open audit and updater issues

Status: Complete

## Outcome + scope

Fix the four reproduced faults in open issues #270, #275 and #276. A verified update that migrates the CI workflow stays scaffold-only. Submodule checkout output stays off stdout. Admin review bypass refuses when anything besides the review may block the merge. The suppression gate reads tracked paths that Git writes with a trailing tab or C quotes. Non-goals: other merge rules, other diff readers, CI workflow content.

## Repository context

Owners: `release_installed` and `fetch_sources` in `.hooks/update.py`, `_review_bypass_problem` in `.hooks/shipping.py`, `diff_lines` in `.hooks/comments.py`. Tests live in `tests/test_updates.py`, `tests/test_adoption.py`, `tests/test_shipping.py` and `tests/test_comments.py`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix all open issues, run the Codex adversarial review loop and open a PR.

The workflow counts as installed only when the release's setup, run on the base revision, writes the committed workflow. Review bypass reads review threads and base-branch rules in its existing query and fails closed on anything it cannot prove satisfied.

## Acceptance + steps

- [x] A verified update that migrates `.github/workflows/hard-eng.yml` passes the scaffold check; a project edit to that file beside the update does not.
- [x] `git submodule update` output from `fetch_sources` goes to stderr.
- [x] Review bypass refuses an unresolved review thread, unreadable base rules, signature, deployment or lock protection and unknown ruleset rules.
- [x] Suppressions and lost assertions are found in tracked paths with spaces, tabs, quotes and non-ASCII letters.
- [x] Full gate passes.

## Baseline + execution

Result: Passed
Evidence: Each new regression test failed on main 9c56c10c and passes with its fix.
Execution: One builder; one owner change per issue.

## Risks + recovery

The workflow proof runs setup in a temporary worktree of the base revision; a mismatch falls back to the full checks. Recovery: revert the owning commit.

## ux_reference

N/A — hook behaviour with no visual surface.

## Verification

Result: Passed
Evidence: Pending the full gate.
E2E: N/A — real Git repositories in the tests cover the changed paths.

Delivery target: Merge
Delivery: Pending — PR checks, rebase merge, main CI.
