# Judge a new branch on its own changes, not later base edits

Status: Complete

## Outcome + scope

Pre-push for a new branch compares from the merge base of the remote base tip and the pushed revision, so edits made on the base after branching no longer count as the branch's changes. Fixes issue #181. Pushes to an existing branch keep comparing with its previous tip, so force-push rewinds still check the reverted files. CI keeps its bases: pull requests test GitHub's merge commit, and pushes compare with the previous tip. Non-goals: other scope rules.

## Repository context

Owners: `.hooks/ship_actions.py` `push_base` passed the remote base tip as `--base`; `.hooks/gate_config.py` `changed_files` diffs against that endpoint.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix the open hard-eng issues.

## Acceptance + steps

- [x] A new branch behind a base that edited a Ready root plan passes pre-push with its own Complete plan → `test_new_branch_behind_its_base_is_judged_on_its_own_changes`.

## Baseline + execution

Result: Passed
Evidence: Main `846ba75`. The new test failed on that code with the issue's error: "PLAN.md: plan is Ready; this check requires Complete".
Execution: One change.

## Risks + recovery

When the base and branch share no history, the merge base is unavailable and the remote tip stays the base. Recovery: revert the commit.

## ux_reference

N/A — gate scope with no visual surface.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base main --plan-stage Complete` → exit 0, 17/17 gates PASS. The first attempt normalised every `--base`. `/codex:adversarial-review --base main` showed that this emptied the diff for a force-push rewind, so the merge base moved into pre-push for new branches only.
E2E: Passed — the regression test runs a real `hard-eng.py pre-push` against a bare remote whose `main` moved on after the branch left it.

Delivery target: Merge
Delivery: Pending — PR checks green, squash merge, main CI green.
