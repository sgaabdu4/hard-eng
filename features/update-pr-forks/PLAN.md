# Update PR forks

Status: Complete

## Outcome + scope

`update-pr` finds only an update PR whose branch lives in the project's own repository. Before, `gh pr list --head hard-eng/update` also returned a fork's PR from a branch with the same name, and the first row was taken. On a public project, a fork could make `update-pr` retitle the fork's PR and never open its own. Non-goals: the PR body.

## Repository context

Owner: `open_pull` in `.hooks/update_pr.py`; `publish` and the merge step use its result. GitHub's `isCrossRepository` field marks a PR whose head is in another repository.
Same cause: one cause, the lookup trusted the branch name alone.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-20 to build the deep-study findings into `develop`, with every decision made by the agent. Decided: a missing `isCrossRepository` field counts as foreign, so the lookup fails closed and opens a new PR.

## Acceptance + steps

- [x] A fork PR on the same branch name is never edited, and `update-pr` opens its own → `tests/test_update_pr.py::test_update_pr_ignores_a_fork_pr_from_a_branch_with_the_same_name`.
- [x] The project's own PR is still reused → `tests/test_update_pr.py::test_update_pr_pushes_opens_one_pr_and_turns_on_auto_merge`.

## Baseline + execution

Result: Passed
Evidence: `develop` fe180a3: the new test failed there; `update-pr` called `pr edit` on the fork's PR and never `pr create`.
Execution: One builder; failing test, then the fix.

## Risks + recovery

An old `gh` without `isCrossRepository` makes `update-pr` open a second PR, which GitHub refuses for the same head; recovery is to update `gh`.

## ux_reference

N/A — command-line change with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1819 passed with the 8 known environment failures plus 2 stale-install rows in `tests/test_ship_actions.py` whose fake PR lacked `isCrossRepository`; with that field the file and `tests/test_update_pr.py` pass except the 2 known signal-timing rows. Ruff, Pyrefly (0 errors), Vulture and jscpd (0 clones) pass.
E2E: N/A — the tests run the real update and push against real Git remotes with a fake `gh`; a live PR needs a project with a fork.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
