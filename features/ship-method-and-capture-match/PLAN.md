# Two escaped-bug checks on the ship record and the capture match

Status: Complete

## Outcome + scope

The After-image check judges every capture set that holds the image and was taken at the head, and the merge-method check is proved against GitHub's real field. Non-goals: any other ship rule; a change to the merge method code.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's message of 2026-11-18 naming two possible bugs.

## Repository context

Owners: `.hooks/ui_proof.py` (`measured_problem`, `_set_problem`) owns the After-image match; `.hooks/ship_record.py` (`merge_method`) owns the recorded merge method.
Same cause: `measured_problem` took the first record with the image hash. Searched `.hooks` for other lookups by hash or first match: `unchanged_problem` keys records by image name and `look_record_problem` compares hash sets, so neither shares the cause.
Single source: N/A — one function owns each rule; no copy was found.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: The coordinator asked for both checks and a fix where a test is red; this PR is not merged until the main-into-develop join lands.

## Acceptance + steps

- [x] An earlier clean capture set with the same image does not hide a later set that has findings → `tests/test_ui_capture_match.py::test_an_earlier_clean_capture_with_the_same_image_does_not_hide_findings`
- [x] A capture set of an older commit with the same image does not refuse the set taken at the head → `tests/test_ui_capture_match.py::test_a_capture_of_an_older_commit_with_the_same_image_does_not_refuse_the_current_one`
- [x] A set refreshed at one width with a finding is not hidden by a clean set → `tests/test_ui_capture_match.py::test_a_set_refreshed_at_one_width_with_a_finding_is_not_hidden_by_a_clean_set`
- [x] A capture set of an older commit alone is still refused → `tests/test_ui_capture_match.py::test_a_capture_of_an_older_commit_alone_is_still_refused`
- [x] A repository that forbids rebase merges records its other method when GitHub reports the PR as not rebaseable → `tests/test_merge_refusal.py::test_release_and_squash_only_merges_stay_possible`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` the first, second and fourth new tests fail (the first returns no problem, the second refuses the current set as not taken at the head) and the third passes. After the change all four pass, with 156 UI tests.
Execution: One builder; the merge-method check needed no code change.

## Risks + recovery

Two sets at the head with the same image and different findings now refuse the After image, where the first record used to decide. Recovery: revert the commit.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Merge method: a throwaway draft PR in a private repository that forbids rebase merges reported `rebaseable` false on the real API (merged PRs of that repository report null, and ship refuses a null `mergeable` before it records a method), the value that the existing squash-only test feeds, so that bug is not reproduced and the decline stays. The throwaway PR was closed and its branch deleted. Capture match: the red and green results above.
E2E: N/A — the change is a pure check of local records, proved by the tests above.
Real service: Passed — GitHub: one read of the real `rebaseable` field on an open PR in a repository that forbids rebase merges returned false; the changed code calls no other service.
Retro: Escaped bug: the gate that should have caught it is the ship UI evidence test set in `tests/test_ui_quality.py`, which tested one capture set at a time; the failing cases `tests/test_ui_capture_match.py::test_an_earlier_clean_capture_with_the_same_image_does_not_hide_findings` and `tests/test_ui_capture_match.py::test_a_capture_of_an_older_commit_with_the_same_image_does_not_refuse_the_current_one` were added first and fail on the base revision. The possible merge-method bug is not reproduced: None — the real field is false.

Delivery target: PR
Delivery: Pending — required remote proof.
