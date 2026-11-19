# PR text before CI, the quick check on a committed plan, and every Fallow finding on failure

Status: Ready

## Outcome + scope

A builder can run the PR text rules of CI before and after a PR opens, the quick check judges a committed plan when no base branch is known, and a failed Fallow gate prints every finding and keeps its JSON in CI. Non-goals: any other PR text rule, any other plan rule, any change to the Fallow limits.

## Sources + coverage

Sources: N/A — the request is the only source: the maintainer's message of 2026-11-19 that names the three faults reported from an installed project.

## Repository context

Owners: `.hooks/pr_text.py` owns the PR text rules and gets the one function both CI and `ship` call; `.hooks/shipping.py` (`_ready_state`) calls it; `.hooks/gate_runner.py` and `.hooks/ci_jobs.py` hold the command line; `.hooks/change_size.py` (`released_plans`) owns which plans a check judges; `.hooks/fallow_report.py` (`finding_lines`) and `.hooks/reports.py` (`scanner_result`) own the failure output of a scanner; `.github/hard-eng.yml` is the CI template that Hard Eng installs.
Same cause: F21 and F23 share one cause: a check that runs in one place and hides its result in another. Other checks found that run only in CI: `release-source.yml` runs only in this repository, installs nowhere, and `ship ready` already refuses the same heads through `route`, so it needs no local step. `.github/workflows/pr-text.yml` is the one installed CI-only check; it gets the command. Other gates that hide findings: `scanner_result` cut every scanner at 20 findings and printed the path of a report that CI never keeps; all scanners now print every finding. A scanner whose report fails on an exit 0 run printed one sentence and no finding; that path prints its findings too.
Single source: the PR text rules had one owner, `body_problem`, and `event_problem` held a second list of rules (the UI part) that `ship` did not call. The new `pull_problem` holds the whole list; CI, the new command and `ship` call it. Searched `.hooks`, `.github` and `tests` for other `body_problem` callers: only `shipping.py` and `pr_text.py`. The 20-finding limit has one owner, `FINDING_LIMIT` in `reports.py`, which is removed with its one use.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous mode. The maintainer assigned these three faults, named the branch and the checks; the PR is not merged here.

## Acceptance + steps

- [ ] The `pr-text` command fails on a body that lacks the Undo line, the Mermaid diagrams or the Not checked line, and on a UI path PR with no pictures or note → `tests/test_pr_text.py::test_the_pr_text_command_refuses_a_body_that_lacks_a_part`
- [ ] The `pr-text` command passes a good body and a UI path PR with the unchanged note → `tests/test_pr_text.py::test_the_pr_text_command_passes_a_good_body`
- [ ] `ship --stage ready` refuses a UI path PR with no pictures, which `body_problem` alone let pass → `tests/test_pr_text.py::test_ready_refuses_a_ui_change_without_pictures_or_a_note`
- [ ] The quick check judges a plan that the branch changed and committed when no branch point is found, in a clean tree → `tests/test_quick_plan_scope.py::test_the_quick_check_judges_a_committed_plan_when_no_base_branch_is_known`
- [ ] A failed Fallow gate prints each complexity and CRAP finding and every other finding past 20 → `tests/test_report_findings.py::test_a_failed_fallow_gate_prints_its_complexity_and_crap_findings`
- [ ] The CI template uploads the Fallow JSON only on failure → `tests/test_ci_setup.py::test_the_workflow_keeps_the_fallow_report_only_when_a_check_fails`

## Baseline + execution

Result: Passed
Evidence: The Hard Eng push run on the branch point a7909cdb of develop completed with success, so the starting code passes every gate; the failed pull request run of that commit was a rerun of the same tree. Before the edits, the F22 probe in a single branch clone printed a pass for `check --quick` and a refusal for `--plan-stage Complete`; in a clone with the base branch, quick refused as well.
Execution: One builder in this worktree. Order: F21 tests and code, F22 reproduction then test and code, F23 tests and code, then the gates.

## Risks + recovery

`ship ready` now calls GitHub once more for the PR and for its file list on a UI path PR; a failed call refuses with the cause. Printing all findings can lengthen a failure log. A plan check with no branch point now judges every plan file, which can refuse an old plan in a clone with no base branch. Recovery: revert the commit.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — the change is a command and check rules proved by the tests above; no user journey crosses a screen.
Real service: Required — GitHub: the `pr-text` command reads this PR once through `gh api repos/<repo>/pulls/<n>` after the PR opens; the tests fake GitHub.
Retro: Required on Complete plans; written at task end.

Delivery target: PR
Delivery: Pending — required remote proof.
