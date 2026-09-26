# Scan only current files for deployment configuration and name an empty Trivy scan

Status: Complete

## Outcome + scope

Fix [#193](https://github.com/sgaabdu4/hard-eng/issues/193). (1) The `deployment` gate scans the same current files as the `secrets-files` gate (tracked plus untracked, not ignored), so ignored directories such as linked worktrees under `.claude/worktrees/` or `.terraform/` no longer change the local result compared with pre-push and CI. (2) A Trivy report with no configuration results (Trivy omits `Results` when it finds nothing) fails with a message that says no deployment configuration was found and the gate should be removed, instead of "incomplete or malformed". Non-goals: removing a stale deployment gate automatically, changing which files count as deployment configuration, other scanners.

## Repository context

Owners: `.hooks/gitleaks_scan.py` `run_gate_command` and its current-files snapshot (`copy_scan_tree`), already used for `secrets-files`; `.hooks/reports.py` `validate_trivy`. Tests in `tests/test_current_files_gitleaks.py` and `tests/test_reports.py`.
Evidence: `trivy config` walks ignored directories; with no IaC it exits 0 with a report holding `SchemaVersion`, `ArtifactName` and `ArtifactType` but no `Results` (issue reproduction, trivy 0.74.0). Pre-push already scans a fresh worktree of the pushed commit.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked to fix open issues, test for regressions, run one limited adversarial review and merge into main.
Decisions: Reuse the `secrets-files` snapshot copy (`copy_scan_tree`) rather than a Trivy skip list, so both gates share one definition of current files. Trivy keeps running from the package directory and only its `.` target points at the snapshot, so relative `--output`, `.trivyignore` and `trivy.yaml` paths resolve as before. An empty scan stays a failure: a gate that checks nothing proves nothing.

## Acceptance + steps

- [x] Deployment gate through `run_gate` → Trivy sees tracked and untracked files, not an ignored directory's files → `test_deployment_gate_scans_current_files_from_the_package_directory` (also proves Trivy still runs from the package directory).
- [x] Report without `Results` or with `Results: []` → failure naming the missing deployment configuration and the gate to remove → `test_trivy_scan_without_configuration_names_the_cause`; a non-list `Results` still fails as malformed.
- [x] Existing Trivy report and snapshot tests still pass → `uv run pytest tests/test_reports.py tests/test_current_files_gitleaks.py`.
- [x] Real Trivy, issue reproduction → `check` and pre-push agree → synthetic E2E below.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --base main --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: Unchanged `897f84b` → `python3 .hooks/hard-eng.py check` all gates PASS, 937 tests, 90.51% line coverage; the branch was then rebased onto `f0c7bb3`, whose main CI (Hard Eng) passed. Issue reproduced with real Trivy on that revision: synthetic repository with a tracked `Dockerfile`, then a linked worktree under ignored `.claude/worktrees/x` and `git rm Dockerfile` → local `check` → `PASS trivy-config` with the only target `.claude/worktrees/x/Dockerfile`; `check` in a fresh detached worktree of the same commit → `FAIL trivy-config: Trivy report is incomplete or malformed`.
Execution: One builder at the existing owners.

## Risks + recovery

The deployment gate now copies current files once per run, as `secrets-files` does. A customized Trivy target other than `.` keeps scanning its directory in place. Recovery: revert the commit.

## ux_reference

N/A — gate behavior with no visual surface.

## Verification

Result: Passed
Evidence: Both new tests fail on the previous code (report messages mismatch; the runner test sees `.claude/worktrees/x/Dockerfile`) and pass now. `uv run pytest tests/test_reports.py tests/test_current_files_gitleaks.py` → 188 passed. `python3 .hooks/hard-eng.py check --base main --plan-stage Ready` → all gates PASS, 994 tests, 90.31% line coverage.
Review: Codex adversarial review (`codex-companion adversarial-review --base main`, limited to correctness regressions in this diff) → approve, no findings. Own review: Lint's complexity limit caught an extra type check in `validate_trivy`; a falsy `Results` now fails as no configuration and any other non-list still fails as malformed.
E2E: Passed — synthetic uv project with a tracked `Dockerfile`, installed from this revision with real `setup.py`, which generated the `trivy-config` gate; real Trivy through `check`. Tracked `Dockerfile` → `PASS trivy-config`, report targets only `Dockerfile`. After adding a linked worktree under ignored `.claude/worktrees/x` and `git rm Dockerfile`: local `check` and `check` in a fresh detached worktree of the commit (what pre-push runs) both → `FAIL trivy-config: Trivy found no deployment configuration in current files; remove the deployment gate if the project has none`. Before the fix, the same steps gave local PASS on the worktree's file and clean-checkout "incomplete or malformed".

Delivery target: Merge
Delivery: Pending
