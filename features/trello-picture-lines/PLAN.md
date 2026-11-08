# Every picture in a Trello comment shows

Status: Complete

## Outcome + scope

The board tool's `comment --image` puts one line break between the image lines it adds. Trello then reads two or more images as one broken block and shows "unsupported image" in place of the pictures. A comment with one image shows. Now the tool puts a blank line between image lines, so each picture shows. Non-goals: attachment names, file types, already posted comments.

## Repository context

Owners: `.agents/skills/trello-coordinator/scripts/trello_board/commands.py` (`comment` builds the comment text).
Same cause: the image lines are joined with one line break.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Abid on 2026-11-07 asked why some Trello images show as unsupported; the cause sits in Hard Eng's board tool.
Decision: fix the join only; every uploaded file already reaches Trello with its real image type and previews.

## Acceptance + steps

- [x] A comment with two images has a blank line between them → `tests/test_trello_board.py::test_repeated_image_flags_attach_every_image`.

## Baseline + execution

Result: Passed
Evidence: develop passed required CI at 5cfb8a74; the extended test failed before the change with one line break between the images.
Execution: one session; failing test first, the fix, the full check, PR, release.

## Risks + recovery

Low: only the spacing of image lines changes. Recovery: revert this pull request.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: Trello tests 70 passed; `python3 .hooks/hard-eng.py check --plan-stage Complete` result recorded in the pull request.
E2E: N/A — no user journey.
Delivery target: PR
Delivery: Pending — PR into develop.
