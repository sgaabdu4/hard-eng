# The PR text job no longer cancels a running job

Status: Complete

## Outcome + scope

A change of a PR text seconds after the PR opens no longer cancels the running `pr text` job, and each run judges the text that the PR has at that moment. Non-goals: the other workflows, the `update-pr` and `ship` readers, the code of any runner.

## Repository context

Owners: `.github/workflows/pr-text.yml` (job `pr-text`), which setup installs in each GitHub project; `tests/test_pr_text.py`. Evidence: on 13 November a private project opened two PRs and changed each text 9 seconds later. GitHub cancelled the first run at the moment a self-hosted runner that takes one job took it. The runner left with no job, its host reported a failed job two times, and the second cancel held the next run for 5 minutes (12:15:43Z to 12:20:43Z). The group came in on 11 November only because the workflow scan asks each job for one.
Same cause: the cancelled `pr text` run is the cause of two earlier fixes, and both changed a reader and left the cause. (1) `update-pr` read a cancelled older run beside a newer pass as a failure; the fix judges each check by its newest run — helped for that reader. (2) `ship ready` said "not every head check succeeded" for the same pair; the fix in `features/ship-newest-run-and-stale-flag/PLAN.md` judges by the newest run — helped for that reader. (3) This change stops the cancel. Other places searched: `cancel-in-progress` in `.github/workflows`. `hard-eng.yml`, `canary.yml` and `release-source.yml` keep `true`: each cancels a check of an old commit that runs for minutes, so the cancel saves runner time, and two pushes in a few seconds are rare. The footer job already has `false`.
Single source: N/A — the group and its setting have one owner, the job in `pr-text.yml`; setup copies that file as it is. The text rules stay in `.hooks/pr_text.py`, and this change does not touch them.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer asked for an HE Learn pass on the whole thread and named the failed jobs on the self-hosted runner host. Merge when the checks pass is a standing approval.

Decided:

1. `cancel-in-progress: false`. The job runs for about 8 seconds, so a cancel saves nothing. With `false`, a newer run waits for the running job, and GitHub drops only a run that still waits and has no runner.
2. The step reads the PR from the API and gives that to `event_problem` in the shape of an event file. Without this, an older run that is no longer cancelled would judge the older text and could fail beside a newer pass. If the read fails, the step uses the event file, as before.
3. No change in `.hooks/pr_text.py`: the API gives a PR in the same shape as the `pull_request` part of the event.

## Acceptance + steps

- [x] A new event waits for the running `pr text` job and never cancels it → `tests/test_pr_text.py::test_a_new_event_waits_for_the_running_pr_text_job_and_never_cancels_it`
- [x] The step judges the text that the PR has now, not the text of the event → `tests/test_pr_text.py::test_the_step_judges_the_text_that_the_pr_has_now_not_the_text_of_the_event`
- [x] When the read of the PR fails, the step judges the text of the event → `tests/test_pr_text.py::test_pr_text_workflow_step_fails_a_pr_whose_text_breaks_the_rules`
- [x] The step holds the workflow token, the PR number and the repository name, and no more → `tests/test_pr_text.py::test_pr_text_job_reads_the_pr_files_with_the_workflow_token_and_nothing_more`
- [x] The footer job keeps its own group, and a push run never shares it → `tests/test_pr_text.py::test_each_job_holds_its_own_concurrency_group_so_a_push_cannot_cancel_the_footer`
- [x] On GitHub, a text change seconds after a PR opens leaves no cancelled `pr text` run → N/A — no local test can make GitHub cancel a run; the PR of this change is opened and its text changed in the same minute, and its text records the two runs.

## Baseline + execution

Result: Passed
Evidence: develop 5a8e8e06: the Hard Eng CI run for the push of that commit passed, and `ship --stage delivered` passed on it. This branch starts there.
Execution: One builder, this session. One independent review before the merge.

## Risks + recovery

- One more API read in each `pr text` job, and at most one more job of about 8 seconds for each quick text change.
- A project test that pins the content of this workflow file fails until the project updates its pin.
- A project gets the change only with its next Hard Eng update. Until then a quick text change can still cancel a job there.
- Recovery: revert the commit; the workflow has no state.

## ux_reference

N/A — a CI workflow only; no visible UI.

## Verification

Result: Passed
Evidence: the three new or changed tests failed on the code before the change: the step judged the event text (exit 1 where 0 was expected), the setting was `true`, and the step had one variable. After the change `tests/test_pr_text.py` passed, 63 tests. The format, lint and types commands of the gates file gave exit 0 on the test file. `actionlint`, the workflow scan (`zizmor`, no findings in 4 workflows) and the `shipped-format` command gave exit 0.
E2E: N/A — no app journey changes; the real run on GitHub is the last acceptance line.
Retro: (1) The group was added on 11 November only to pass the workflow scan, and nobody asked what a cancel does to a runner that takes one job → `tests/test_pr_text.py::test_a_new_event_waits_for_the_running_pr_text_job_and_never_cancels_it`. (2) Two earlier fixes changed a reader of the cancelled run and left the cause → None — the `Same cause:` field asks for this search and was filled too narrowly both times; this plan now lists the three sightings.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
