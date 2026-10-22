# Keep the fast path when an update rewrites agent hook settings

Status: Complete

## Outcome + scope

A release can change the hooks that setup writes into `.claude/settings.json` and `.codex/hooks.json`. A project's update then changed those files, and the scaffold-only check refused them, so every update ran the project's full checks. Now those files count as installed when they hold exactly what the release's setup writes from the base tree. A project edit in the same files still gets the full checks. Non-goals: other project-owned files, changing which releases count as verified.

## Repository context

Owner: `.hooks/ci_setup.py` (`setup_installed`, was `workflow_installed`), `.hooks/update.py` (`INSTALLED_FILES`); `preserved_instructions` moves to `.hooks/agent_hooks.py` to keep `update.py` under the file length limit. Test in `tests/test_adoption.py`.
Same cause: the CI workflow had the same problem, and `setup_written` already proves it. This change applies that proof to every setup-owned file.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The user asked on 2026-10-22 to fix the CI failures across projects at their source in Hard Eng.
Decided: reuse `setup_written`, which runs the new release's setup on a worktree of the base. No new file list; the hook files come from `agent_hooks.HOOK_FILES`.

## Acceptance + steps

- [x] An update that only rewrites hook settings is scaffold-only; a project edit beside it is not → `tests/test_adoption.py::test_update_that_migrates_setup_files_is_scaffold_only_unless_edited`.

## Baseline + execution

Result: Passed
Evidence: the new settings case failed (`check_scaffold_update` returned False) before the change and passes after it.
Execution: One builder, this session.

## Risks + recovery

The proof runs setup once more on a temporary worktree, the same cost the workflow proof had. Recovery: revert this commit.

## ux_reference

N/A — no visible UI change.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/develop` in the cloud container; PR CI runs it with every toolchain.
E2E: N/A — no user journey; the test drives a real update and the real `check_scaffold_update`.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
