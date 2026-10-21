# Plan size names the file

Status: Complete

## Outcome + scope

When a change needs a plan because it adds, deletes or renames a file, the size message names that file. Before, it said only "it adds, deletes or renames a file", so a stray untracked file took a reproduction to find. Non-goals: the size rules themselves.

## Repository context

Owners: `size_verdict` in `.hooks/change_size.py` builds the reason. Found in the 2026-10-20 timing run on installed projects: a copied, locally ignored file made one project's check ask for a plan with no file named.
Same cause: none found.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked on 2026-10-21 to look into the failing checks from the timing run. Decided: name the first such file in sorted order, so the message stays one line.

## Acceptance + steps

- [x] A new file and a deleted file each name the file in the reason → `tests/test_plans.py::test_big_change_still_needs_a_plan_and_names_why`.
- [x] A binary file beside a Hard Eng update names that file → `tests/test_update_pr.py::test_update_branch_needs_no_plan_for_files_the_update_wrote`.

## Baseline + execution

Result: Passed
Evidence: `develop` eb88231: the two new-file and deleted-file cases failed on the old message.
Execution: One builder; test expectations first, then the reason in `size_verdict`.

## Risks + recovery

None beyond the message text. Revert the one block in `size_verdict` to restore the old message.

## ux_reference

N/A — hook output with no visual surface.

## Verification

Result: Passed
Evidence: Branch full suite 1,857 passed; the same 6 environment failures as `develop` (no Dart or Swift in this container). Ruff format and lint pass. Independent review not done: Codex is not installed in cloud sessions.
E2E: N/A — the tests run the real size check on real Git repositories.

Delivery target: Merge
Delivery: Pending — PR into `develop` with the `hard-eng` CI check green.
