# Check an update candidate against the branch's own changes

Status: Complete

## Outcome + scope

The updater's candidate check compares against the merge base with the remote base branch, not its tip. A branch behind its base is no longer charged with files that only the base changed, matching pre-push since #182.

## Repository context

`verify_candidate` in `.hooks/update.py` passed the remote base tip to `check`, whose `changed_files` diffs two-dot against it. When the base had edited files the branch still holds at older versions, those files counted as the branch's own, and changed-file rules such as the comment rule failed the update. The failing update also left the Stop-hook fix from #171 out of reach.

## Decisions + authorization

Blockers: None
The user asked for the stuck worktree to be updated; this fixes the updater defect that blocked it at its owner. `check` keeps its endpoint diff for explicit bases; only the candidate call resolves the merge base, as pre-push does.

## Baseline + execution

Result: Passed
Evidence: `test_candidate_ignores_base_changes_the_branch_lacks` failed before the fix with "shared.py:1 holds a 3-line comment block" for a file only the base changed.

## Acceptance + steps

- [x] An update candidate on a branch behind its base passes when only the base changed a file holding a comment block → `test_candidate_ignores_base_changes_the_branch_lacks`.
- [x] Candidate checks still run the application gates with the remote task scope → `test_candidate_uses_remote_task_plan_scope`.

## Risks + recovery

With no merge base, for example unrelated histories, the check falls back to the remote base tip as before.

## ux_reference

N/A — updater behaviour with no product UI.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed; the full suite passed with 990 tests.
E2E: N/A — covered by the real-Git candidate regression.

Delivery target: Merge
Delivery: Pending — PR merge, main CI, and native Delivered verification.
