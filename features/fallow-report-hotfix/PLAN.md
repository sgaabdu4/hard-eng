# Fallow report hotfix

Status: Ready

## Outcome + scope

A failed Fallow gate prints every finding, with the complexity and CRAP findings, and CI keeps the Fallow JSON when a check fails; an installed project gets the upload step when its workflow is next generated. Non-goals: the `pr-text` command, the plan scope fix, any Fallow limit, and any other develop change.

## Sources + coverage

Sources: N/A — the request is the only source: the maintainer's request to send the Fallow fix from develop to `main` as a hotfix.

## Repository context

Owners: `.hooks/fallow_report.py` (`finding_lines`, `complexity_line`) reads a Fallow report; `.hooks/reports.py` (`scanner_result`, `print_findings`) prints a failed scanner; `.github/hard-eng.yml` is the CI template that Hard Eng installs; `.github/workflows/hard-eng.yml` is this repository's own workflow; `.hooks/shards.py` (`add_fallow_report`) and `.hooks/ci_setup.py` (`adapt_ci`) add the step to a generated workflow.
Same cause: a check that hides its result where the reader cannot see it. `scanner_result` cut every scanner at 20 findings and printed the path of a report that CI never keeps; all scanners now print every finding, and a scanner that fails on an exit 0 run prints its findings too. No other scanner path hides a report.
Single source: the finding cut at 20 had one owner, `FINDING_LIMIT` in `reports.py`, which is removed with its one use. The upload step has one owner, the template; `add_fallow_report` copies its text from the template and the own workflow is checked against it by the shard workflow tests. Searched `.hooks`, `.github` and `tests`; no other copy.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous mode. The maintainer assigned the Fallow fix and named the hotfix route. Merge: maintainer, chat 2026-11-20, "yes" to sending the Fallow fix to main as a hotfix.

## Acceptance + steps

- [x] A failed Fallow gate prints each complexity and CRAP finding with its scores and the coverage that Fallow reports, in the combined and the audit report → `tests/test_report_findings.py::test_a_failed_fallow_gate_prints_its_complexity_and_crap_findings`
- [x] A Fallow gate that exits 0 but whose report is refused for a complexity finding prints that finding → `tests/test_report_findings.py::test_a_fallow_gate_that_exits_zero_with_a_finding_prints_it`
- [x] A health only or standalone health Fallow report prints its findings → `tests/test_report_findings.py::test_a_health_only_fallow_report_prints_its_complexity_findings`, `tests/test_report_findings.py::test_a_standalone_fallow_health_report_prints_its_findings`
- [x] Every finding of every kind is printed, with no cut at 20 → `tests/test_report_findings.py::test_the_findings_of_all_kinds_are_all_printed`
- [x] The CI template and this repository's workflow upload the Fallow JSON only on failure → `tests/test_shard_workflow.py::test_the_workflow_keeps_the_fallow_report_only_when_a_check_fails`
- [x] A workflow from before the step gains it, in the one job and the split form → `tests/test_shard_workflow.py::test_a_workflow_from_before_the_fallow_report_step_gains_it`
- [x] A workflow that does not end with the check step is left alone → `tests/test_shard_workflow.py::test_a_workflow_that_does_not_end_with_the_check_step_is_left_alone`

## Baseline + execution

Result: Passed
Evidence: `origin/main` is the tip of the release branch; the split check `git diff --quiet "$(git merge-base origin/main origin/develop)" origin/main` exited 0, so `main` holds no change that develop lacks. The seven tests above were run on the unchanged `main` source: 10 cases failed (7 test functions) and 113 others passed in the three test files.
Execution: One builder in this worktree. The change is the Fallow part of four develop commits and two follow-up commits that touch only the Fallow code and tests, taken file by file. One test differs from develop: `main` has no combined health validation, so the exit 0 test uses an audit report, which `main` refuses for complexity findings.

## Risks + recovery

Printing all findings can lengthen a failure log. A custom workflow layout gets no upload step; the migration edits only text that Hard Eng generated. Recovery: revert the merge of the hotfix.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — the change is check output and a workflow step proved by the tests above; no user journey crosses a screen.
Real service: N/A — the change calls no outside service
Retro: Pending

Delivery target: Merge
Delivery: Pending — required remote proof.
