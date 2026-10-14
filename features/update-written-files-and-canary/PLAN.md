# Update-written files and release canary

Status: Draft

## Outcome + scope

1. An update PR needs no PLAN.md for files the verified update wrote: scaffold files and the project files setup itself edits during the update (issue sgaabdu4/hard-eng#299). The packages those setup edits touch still run their checks.
2. `release_canary.py` (source-only) tries a release on every installed project before it merges: each project's own updater applies the release, the project must then be on that release, and both its update PR check and a full check of every gate must pass. Results and project names stay on the maintainer's machine; GitHub gets a `canary` commit status with counts only.
Non-goals: no change to the package scope of setup edits; no required status or branch protection change; no CI job.

## Repository context

Owners: [plans.py](../../.hooks/plans.py) `size_verdict` (counts the branch change); [ci_setup.py](../../.hooks/ci_setup.py) `workflow_installed` (already proved one setup-written file from a base worktree); [update.py](../../.hooks/update.py) `installed_update_paths` (scaffold proof). `release_canary.py` sits beside `new_project.py`; setup installs neither.
Evidence: In a Flutter project the update wrote the Flutter skill files and raised the lint pin in a package's `analysis_options.yaml`; the CI check printed that the update matches its release, then demanded a PLAN.md because `.agents/skills/...` always needs one. A trial run of the consumer's own updater on a small Dart project failed the same way: setup edits `.claude/settings.json`, so the scaffold-only proof fails and the whole diff is sized.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix every open Hard Eng issue and to test each release on all projects that use Hard Eng before it ships, choosing a local run on this Mac (option 1). The user ruled that a project failure is fixed in that project by its own PR, never by loosening Hard Eng. Codex adversarial review loop (gpt-6-astra) before the PR; merge when green.
Decisions: Generalize `workflow_installed` into `setup_written` rather than adding a second base-worktree proof. Exempt setup-written files only from plan sizing, not from package scope, so a raised lint pin still runs its package's gates. The canary runs each project's installed updater (patched only to treat the candidate as the newest verified release), because that old code is what really applies a release; it needs the candidate's CI to have passed, so it runs on the PR head after CI. Projects are found with GitHub code search across the user and their organisations; archived ones are skipped. Clones live in `~/Library/Caches/hard-eng-canary`, push is disabled in each clone, passing clones are deleted and the previous run is removed at the next start. The rule lives in `AGENTS.override.md`, which is never installed.

## Acceptance + steps

- [x] An update branch whose only other change is a file setup wrote is small; a project edit to a protected file, or a binary file, beside it still needs a plan → `test_update_branch_needs_no_plan_for_files_the_update_wrote`, red before with the issue's exact message (the binary case crashed before; review round 1).
- [x] Existing workflow proof keeps passing through `setup_written` → `test_update_that_migrates_the_ci_workflow_is_scaffold_only_unless_edited` and the CI setup tests.
- [x] Only changes to installed files need a canary run; the posted status names no project → `tests/test_release_canary.py`.
- [ ] Real canary run on the PR head across every installed project.
- [ ] Full `python3 .hooks/hard-eng.py check` passes.

## Baseline + execution

Result: Passed
Evidence: The base commit passed required CI on main.
Execution: Red test, fix, focused tests; canary script, unit tests and a one-project trial; full check; Codex loop; push; PR CI; full canary on the PR head; fix any project failures in their own repositories; merge.

## Risks + recovery

GitHub code search can lag for a newly set-up repository, so a run may miss it; the run prints how many projects and owners it covered. A project whose own main branch is already failing blocks the run until that project is fixed. Recovery is reverting this branch.

## ux_reference

N/A — plan sizing and a maintainer script; no product appearance.

## Verification

Result: Pending
Evidence: Pending
E2E: Pending

Delivery target: Merge
Delivery: Pending
