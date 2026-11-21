# UI evidence refusal names the layout; plan check judges plans that name a changed test

Status: Complete

## Outcome + scope

The refusal for missing UI evidence says the body needs a `Before:` line and an `After:` line, each followed by its image or video, and that unlabelled attached images do not count. The ship reference shows the layout for images and videos. The plan check also judges every other Complete plan that names a test in a changed test file, and the browser plan and one other older plan name the tests that replaced removed ones. Non-goals: any change to the parser.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's message of 2026-11-19.

## Repository context

Owners: `.hooks/ship_evidence.py` (`attachment_urls`) owns the message; `.agents/skills/he-ship/references/checks.md` owns the layout text.
Same cause: the message named only the attach command, so a body with unlabelled images looked correct to the writer. The request also said an image reference under a label is refused. It is not: the label pattern uses `\s*`, which spans blank lines, so the documented layout already passes. No parser change was made.
Second cause: a PR that removed a test judged only the plans it edited (`plan_stage` checks missing tests for edited plans only), so an older plan kept naming it until a release range edited that plan and failed. `unchanged_plan_test_problem` in `.hooks/plan_tests.py` now reads each other Complete plan that mentions a changed test file and refuses a missing test in that file; a PR that changes no test file reads no plan.
Single source: N/A — one function holds the message and one holds the new rule.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The coordinator named the message, the docs and the PR; the PR is not merged here.

## Acceptance + steps

- [x] The refusal names `Before:`, `After:` and the attach command → `tests/test_shipping_ui_evidence.py::test_missing_ui_evidence_names_the_labels_and_the_upload_command`
- [x] The layout that GitHub CLI writes for labelled images is accepted → `tests/test_shipping_ui_evidence.py::test_ui_changes_accept_image_video_and_mixed_attachments_that_reject_head`
- [x] A branch that removes a test named by an unchanged plan is refused, and one that removes an unnamed test passes → `tests/test_plan_acceptance.py::test_removing_a_test_that_a_plan_names_is_refused_even_in_a_small_change_with_no_plan_edit`
- [x] Unlabelled images, as an `--attach` with no local reference appends them, are refused → `tests/test_shipping_ui_evidence.py::test_ui_changes_reject_missing_foreign_or_duplicate_evidence`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` the removed-test row for the named test fails (no refusal). On `origin/develop` the message test fails, since the text has no labels. The labelled image row passes there too, which shows the parser was already right.
Execution: One message edit, one docs edit, the test rows.

## Risks + recovery

None: the message text changes; no check changes its outcome. Recovery: revert the commits.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The focused tests, the static gates and the Complete check passed on the head.
E2E: N/A — a refusal text and a docs edit.
Real service: N/A — no service is called.
Retro: Escaped bug: the plan acceptance check on the PR that removed a test judged only edited plans, so the browser plan kept two removed names until the release range; the gate that should catch it is that check, and the new test row proves a removed named test refuses. Timing of the plan check over the develop range: 0.37 to 0.42 s before and 0.37 to 0.53 s after, 3 runs each. One older plan (trello coordinator) still names a removed test; its repair needs fields the plan lacks, so it is left and the new rule refuses it when its test file changes. Ran too late: none. The request's first fault was not real; reading the pattern and a probe showed `\s*` already spans blank lines, so no parser change was made → none: a gate cannot catch a wrong claim in a request.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
