# The PR text check reaches every GitHub project and checks UI pictures

Status: Complete

## Outcome + scope

A project with many pull requests had no `Undo:` line, no Mermaid diagrams and no before and after pictures in them, and nothing stopped it. Two causes. Setup installed `pr-text.yml` only beside `hard-eng.yml`, and a project with its own check workflow gets no `hard-eng.yml`. The remote `pr text` job also did not apply the UI evidence rule; only the local `ship` command did. Now setup installs `pr-text.yml` when the project has any workflow file of its own, and the remote job refuses a PR that changes a `ui_paths` file with no Before and After pictures or `UI appearance: unchanged` note.

Non-goals: fetching the attachment URLs in the remote job (the local `ship` step still does that), a second pipeline, `add_workflow_checks`.

## Repository context

Owners: `.hooks/ci_setup.py` (`project_workflows` lists the workflow files of the project, without `pr-text.yml`; `adapt_ci` and `configure_github_ci` both read it). `.hooks/pr_text.py` (`event_problem`). `.hooks/shipping.py` (`changed_paths` pages the files of a PR). `.hooks/ship_evidence.py` (`attachment_urls`). `.github/workflows/pr-text.yml`.
Same cause: Earlier fix: none; searched `hard-eng.yml` in `setup.py`, `release_canary.py` and `.hooks/`. Other places: `add_workflow_checks` adds gates only for a workflow that setup creates, so it needs no change. `update.py` lists `pr-text.yml` in `INSTALLED_FILES` and `missing` names `hard-eng.yml` for the rewrite of a changed file; both are path lists, so they do not depend on `hard-eng.yml` being present. `release_canary.py` reads `hard-eng.yml` only when it exists, for its shard check. `adapt_ci` counted `pr-text.yml` as a workflow of the project; that would now block a maintenance-only project from ever getting `hard-eng.yml`, so `project_workflows` leaves it out.
Single source: the workflow listing had one copy in `adapt_ci`; it moved to `project_workflows`, and the files query has one owner, `changed_paths`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The maintainer reported the fault and set the change; the coordinator reviews the commits before any push.

## Acceptance + steps

- [x] A project with its own workflow (`.yml` or `.yaml`) and no `hard-eng.yml` receives `pr-text.yml`; no workflow file, only `pr-text.yml`, a non-workflow file and an unchanged copy give no change → `tests/test_ci_setup.py::test_pr_text_check_is_installed_beside_any_workflow_of_the_project`.
- [x] A maintenance-only project with `pr-text.yml` beside its nightly workflow still receives `hard-eng.yml` → `tests/test_ci_setup.py::test_maintenance_only_workflow_receives_a_quality_owner`.
- [x] Through the real `setup.sh`, a target with its own workflow receives `pr-text.yml` and no `hard-eng.yml` → `tests/test_husky_setup.py::test_shell_bootstrap_installs_verified_main`.
- [x] A UI change with no pictures gives the UI evidence problem with the edit hint → `tests/test_pr_text.py::test_remote_check_refuses_a_ui_change_without_pictures`.
- [x] Pictures, or one unchanged note, give no problem → `tests/test_pr_text.py::test_remote_check_accepts_a_ui_change_with_pictures_or_an_unchanged_note`.
- [x] A file outside `ui_paths` gives no problem; a rename from inside `ui_paths` gives one → `tests/test_pr_text.py::test_remote_check_matches_ui_paths_on_new_and_old_names`.
- [x] With empty `ui_paths` the files query never runs → `tests/test_pr_text.py::test_remote_check_runs_no_files_query_without_ui_paths`.
- [x] A failed files query gives a one-line problem → `tests/test_pr_text.py::test_remote_check_fails_with_one_line_when_the_files_query_fails`.
- [x] A text fault comes before missing pictures, with no query → `tests/test_pr_text.py::test_remote_check_reports_the_text_fault_before_missing_pictures`.
- [x] The `pr-text` job holds `pull-requests: read` and the step holds `GH_TOKEN` → `tests/test_pr_text.py::test_pr_text_job_reads_the_pr_files_with_the_workflow_token_and_nothing_more`.

## Baseline + execution

Result: Passed
Evidence: `develop` was clean at the branch point; the install rows, the rename row, the failed query row and the setup row failed before their change and pass after it.
Execution: one builder session; tests first, then the install rule, then the remote rule and workflow, then docs.

## Risks + recovery

A PR whose files query fails now fails the check until the PR text is edited or the check is rerun. The job token needs `pull-requests: read`, which the workflow now asks for. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: focused runs of `tests/test_ci_setup.py`, `tests/test_husky_setup.py`, `tests/test_pr_text.py`, `tests/test_agent_hooks.py`, `tests/test_release_canary.py`, `tests/test_runner_variable.py`, `tests/test_shipping.py`, `tests/test_shipping_ui_evidence.py` and `tests/test_skill_links.py` passed. The result of `python3 .hooks/hard-eng.py check --plan-stage Complete --base origin/develop` is recorded in the pull request.
E2E: N/A — no user journey; the setup row runs the real `setup.sh` on a target project and the remote rows run `event_problem` on event files with the files query replaced at the `gh` boundary.
Retro: (1) Hard Eng fault that real projects showed: a project with its own check workflow got no PR text check, and the remote check skipped the UI evidence rule → `tests/test_ci_setup.py::test_pr_text_check_is_installed_beside_any_workflow_of_the_project` and `tests/test_pr_text.py::test_remote_check_refuses_a_ui_change_without_pictures`. (2) Found while reading the callers: the new `pr-text.yml` would have counted as a project workflow and blocked a maintenance-only project from getting `hard-eng.yml` → `tests/test_ci_setup.py::test_maintenance_only_workflow_receives_a_quality_owner` holds it with a `pr-text.yml` beside the nightly workflow.
Delivery target: Merge
Delivery: Pending — the PR checks pass, `ship` passes its ready stage and the rebase merge into `develop` is done.
