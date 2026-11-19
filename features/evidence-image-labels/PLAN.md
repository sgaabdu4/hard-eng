# UI evidence refusal names the Before and After layout

Status: Complete

## Outcome + scope

The refusal for missing UI evidence says the body needs a `Before:` line and an `After:` line, each followed by its image or video, and that unlabelled attached images do not count. The ship reference shows the layout for images and videos. Non-goals: any change to the parser.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's message of 2026-11-19.

## Repository context

Owners: `.hooks/ship_evidence.py` (`attachment_urls`) owns the message; `.agents/skills/he-ship/references/checks.md` owns the layout text.
Same cause: the message named only the attach command, so a body with unlabelled images looked correct to the writer. The request also said an image reference under a label is refused. It is not: the label pattern uses `\s*`, which spans blank lines, so the documented layout already passes. No parser change was made.
Single source: N/A — one function holds the message.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The coordinator named the message, the docs and the PR; the PR is not merged here.

## Acceptance + steps

- [x] The refusal names `Before:`, `After:` and the attach command → `tests/test_shipping_ui_evidence.py::test_missing_ui_evidence_names_the_labels_and_the_upload_command`
- [x] The layout that GitHub CLI writes for labelled images is accepted → `tests/test_shipping_ui_evidence.py::test_ui_changes_accept_image_video_and_mixed_attachments_that_reject_head`
- [x] Unlabelled images, as an `--attach` with no local reference appends them, are refused → `tests/test_shipping_ui_evidence.py::test_ui_changes_reject_missing_foreign_or_duplicate_evidence`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` the message test fails, since the text has no labels. The labelled image row passes there too, which shows the parser was already right.
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
Retro: Ran too late: none. The request's first fault was not real; reading the pattern and a probe showed `\s*` already spans blank lines, so no parser change was made → none: a gate cannot catch a wrong claim in a request.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
