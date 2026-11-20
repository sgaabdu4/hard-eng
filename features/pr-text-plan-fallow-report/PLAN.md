# PR text before CI, the quick check on a committed plan, and every Fallow finding on failure

Status: Complete

## Outcome + scope

A builder can run the PR text rules of CI on a PR after it opens and after each edit, the quick check judges a committed plan when no base branch is known, and a failed Fallow gate prints every finding and keeps its JSON in CI. Non-goals: any other PR text rule, any other plan rule, any change to the Fallow limits.

## Sources + coverage

Sources: N/A — the request is the only source: the maintainer's message of 2026-11-19 that names the three faults reported from an installed project.

## Repository context

Owners: `.hooks/pr_text.py` owns the PR text rules and gets the one function both CI and `ship` call; `.hooks/shipping.py` (`_ready_state`) calls it; `.hooks/gate_runner.py` and `.hooks/ci_jobs.py` hold the command line; `.hooks/change_size.py` (`released_plans`) owns which plans a check judges; `.hooks/fallow_report.py` (`finding_lines`) and `.hooks/reports.py` (`scanner_result`) own the failure output of a scanner; `.github/hard-eng.yml` is the CI template that Hard Eng installs.
Same cause: F21 and F23 share one cause: a check that runs in one place and hides its result in another. Other checks found that run only in CI: `release-source.yml` runs only in this repository, installs nowhere, and `ship ready` already refuses the same heads through `route`, so it needs no local step. `.github/workflows/pr-text.yml` is the one installed CI-only check; it gets the command. Other gates that hide findings: `scanner_result` cut every scanner at 20 findings and printed the path of a report that CI never keeps; all scanners now print every finding. A scanner whose report fails on an exit 0 run printed one sentence and no finding; that path prints its findings too.
Single source: the PR text rules had one owner, `body_problem`, and `event_problem` held a second list of rules (the UI part) that `ship` did not call. The new `pull_problem` holds the whole list; CI, the new command and `ship` call it. Searched `.hooks`, `.github` and `tests` for other `body_problem` callers: only `shipping.py` and `pr_text.py`. The 20-finding limit has one owner, `FINDING_LIMIT` in `reports.py`, which is removed with its one use.

## Decisions + authorization

Blockers: None
Handoff: Approval
Review declined: A draft body cannot be checked before the PR opens :: the maintainer asked for a `--pr` command, and the body rules also run in `ship ready` and CI; a body file option is an extra feature.
Review declined: `ship ready` loses the dependency bot exemption :: `ship ready` refused such a PR before this change too, through `body_problem`, which stays in the same expression; nothing new is refused.
Review declined: Existing Swift and JavaScript four job workflows miss the upload :: those layouts have their own jobs and the migration only edits the one job and split layouts that it can prove it generated; a project with that layout gets the step when its workflow is next generated. Stated limit.
Review declined: Reports with a custom filename are lost :: the upload takes any `fallow.json` in any folder, which is the name that setup writes; a custom file name is the project's own choice. Stated limit.
Review declined: A workflow with a step after the check or a trailing outputs block gets no upload :: the migration edits only the workflow text that Hard Eng generates and leaves a customised one as it is, as the shard split does with its own note; adding a step inside any custom layout risks breaking a working workflow. Stated limit.
Review declined: the merge approval in Authority cannot be confirmed from the review evidence :: the maintainer gave it in chat on 2026-11-20 ("yes" to merging PR 665 and PR 666 into `develop` and to the Fallow hotfix into `main`); a review cannot read the chat, and `ship ready` still checks the PR, its head and its CI before the merge.
Authority: Autonomous mode. The maintainer assigned these three faults, named the branch and the checks. Merge: maintainer, chat 2026-11-20, "yes" to the request to merge PR 665 and PR 666 into `develop` and to send the Fallow fix to `main` as a hotfix; this PR merges into `develop` by rebase after CI passes.

## Acceptance + steps

- [x] The `pr-text` command fails on a body that lacks the Undo line, the Mermaid diagrams or the Not checked line, and on a UI path PR with no pictures or note → `tests/test_pr_text.py::test_the_pr_text_command_refuses_a_body_that_lacks_a_part`
- [x] The `pr-text` command passes a good body and a UI path PR with the unchanged note → `tests/test_pr_text.py::test_the_pr_text_command_passes_a_good_body`
- [x] `ship --stage ready` reads the PR text, including the UI form, before the check results; a UI path PR with no pictures and a failing check was refused for the check before → `tests/test_pr_text.py::test_ready_refuses_a_ui_change_without_pictures_or_a_note`
- [x] The quick check judges a plan that the branch changed and committed when no branch point is found, in a clean tree → `tests/test_quick_plan_scope.py::test_the_quick_check_judges_a_committed_plan_when_no_base_branch_is_known`
- [x] A failed Fallow gate prints each complexity and CRAP finding with its scores and the coverage that Fallow reports (percent and source from a coverage file, or the tier of a static estimate), in the combined and the audit report, and every other finding with no cut at 20 → `tests/test_report_findings.py::test_a_failed_fallow_gate_prints_its_complexity_and_crap_findings`
- [x] A health only Fallow report prints its findings; a PR URL of another repository is refused; a base that resolves keeps the plan check off untouched plans; a workflow from before the step gains it → `tests/test_report_findings.py::test_a_health_only_fallow_report_prints_its_complexity_findings`, `tests/test_pr_text.py::test_the_pr_text_command_refuses_a_url_of_another_repository`, `tests/test_quick_plan_scope.py::test_a_base_that_resolves_keeps_the_check_off_untouched_plans`, `tests/test_shard_workflow.py::test_a_workflow_from_before_the_fallow_report_step_gains_it`
- [x] The CI template uploads the Fallow JSON only on failure → `tests/test_shard_workflow.py::test_the_workflow_keeps_the_fallow_report_only_when_a_check_fails`

## Baseline + execution

Result: Passed
Evidence: The Hard Eng push run on the branch point a7909cdb of develop completed with success, so the starting code passes every gate; the failed pull request run of that commit was a rerun of the same tree. Before the edits, the F22 probe in a single branch clone printed a pass for `check --quick` and a refusal for `--plan-stage Complete`; in a clone with the base branch, quick refused as well.
Execution: One builder in this worktree. Order: F21 tests and code, F22 reproduction then test and code, F23 tests and code, then the gates.

## Risks + recovery

`ship ready` now calls GitHub once more for the PR and for its file list on a UI path PR; a failed call refuses with the cause. Printing all findings can lengthen a failure log. A plan check with no branch point now judges every plan file, which can refuse an old plan in a clone with no base branch. Recovery: revert the commit.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The ship-ready test failed on the old code (refused for the failing check) and passes now. The F22 tests failed before the fix (DID NOT RAISE, both base forms) and pass. F22 probe: in a single branch clone, `check --quick` and `--quick --base HEAD` passed and `--plan-stage Complete` refused; after the fix all three refuse. With the base branch present, quick refused before and after. A local base branch moved onto HEAD with `--base HEAD` passes by design (nothing is changed since the base). Quick check timing, 5 interleaved runs each, compiled modules, before 2.71 to 3.08 s, after 1.95 to 3.14 s: no slowdown. Focused suites: ship and PR text 345 passed, plans 719 passed, reports 541 passed, CI setup 161 passed. Static gates on the changed files: ruff format, check, complexity, annotations, pyrefly, vulture passed; semgrep 0 findings.
E2E: N/A — the change is a command and check rules proved by the tests above; no user journey crosses a screen.
Real service: Passed — GitHub: `pr-text --pr` ran against a real merged PR of this repository by number and by URL and printed PASS for both.
Retro: Escaped bug: ship ready ran only part of the CI text rules and the quick check judged no plan when no branch point existed. The tests gate lacked a row for each; the new rows are in `tests/test_pr_text.py::test_the_pr_text_command_refuses_a_body_that_lacks_a_part` and `tests/test_quick_plan_scope.py::test_the_quick_check_judges_a_committed_plan_when_no_base_branch_is_known`. Prevention: one function for the text rules and the branch-point rule that treats a missing point as no proof.

Delivery target: Merge
Delivery: Pending — required remote proof.
