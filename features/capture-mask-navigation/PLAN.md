# Capture refuses a page that changed document after masking, and cleanup removes a worktree with clean submodules

Status: Ready

## Outcome + scope

`browser capture` and `browser measure` keep no image and no record when the page became another document after its emails and phones were hidden. A route change inside the same document still captures. `ship --stage cleanup` removes a clean, fully merged task worktree whose submodules are initialized, and it runs from a checkout that is older than the task. Non-goals: masking again after a navigation, and any change to what cleanup proves about the merge.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's follow-up of 2026-11-25 after PR 736, and the two refused cleanups of earlier builders.

## Repository context

Owners: `require_readable_document` in `.hooks/browser.py` owns the checks of the document around the screenshot. `cleanup_guard` in `.hooks/ship_actions.py` owns what a cleanup keeps. `_policy` in `.hooks/shipping.py` owns the reading of the shipping policy.
Same cause of the capture fault: the page script hides emails and phones in one document only. A navigation after it replaced that document with an unmasked one, and the kind check passed because the new page is HTML. The page script now sets `window.hardEngMasked`; a new document has no such value. The one kind check reads it together with the kind and, after the masking, refuses a document without it. A refusal is smaller than masking again, and it keeps one owner.
Cause one of the cleanup fault: the guard refused every initialized submodule, although the removal already uses `git worktree remove --force` for it. A submodule holds work that no remote has only when it is off its recorded commit, or has a local commit, a stash, or an untracked or ignored file. `submodule_work` checks exactly that, so a clean submodule no longer blocks.
Cause two of the cleanup fault: the main checkout runs the released code, and the task's `hard-eng.gates.json` can hold a key that only develop knows (`ui_library` since 2026-11-25). The strict reader refused it as an unknown key. A cleanup proves only a merge, so `reading_newer_policy_keys` skips unknown keys for that stage alone; every other stage keeps the strict reader.
Single source: one kind check, one submodule check, one policy reader. The shared `delivered_worktree` fixture moved to `tests/conftest.py`, and the submodule tests moved to `tests/test_ship_cleanup_submodules.py`, so the 1000-line limit holds.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; the coordinator set this follow-up on 2026-11-25.

## Acceptance + steps

- [x] A page that navigates to another HTML page with an email on it after masking, before the frame check, keeps no image and no record → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_navigates_after_it_was_masked[before]`
- [x] The same navigation while the screenshot is taken keeps no image and no record → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_navigates_after_it_was_masked[during]`
- [x] A page that does not navigate still captures, also when it changes its route in place → `tests/test_browser_documents.py::test_capture_keeps_the_image_of_a_page_that_changes_its_route_in_place`, `tests/test_browser.py::test_capture_draws_boxes_at_each_width`
- [x] Cleanup removes a clean, merged task worktree that has an initialized submodule → `tests/test_ship_cleanup_submodules.py::test_cleanup_removes_task_with_a_clean_initialized_submodule`
- [x] Cleanup keeps a worktree whose submodule holds an edit, an ignored file, a local commit, a stash or a moved commit → `tests/test_ship_cleanup_submodules.py::test_cleanup_preserves_work_that_only_the_submodule_holds`, `tests/test_ship_cleanup_submodules.py::test_cleanup_preserves_a_submodule_moved_off_the_recorded_commit`
- [x] Cleanup reads a policy with keys of a newer release, and the other stages still refuse them → `tests/test_ship_cleanup.py::test_cleanup_reads_a_policy_that_a_newer_release_gave_more_keys`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (c5ecbc30) the navigation tests fail (`assert 0 == 1`: capture keeps images; commit 06af7bb4, whose `before` trigger never fired and was corrected in the fix commit, then shown red on the old code), and the cleanup tests fail (commit 670d83a2): the clean submodule is refused with "initialized submodules", and the policy with a newer key is refused with "unknown or missing keys". The existing browser, ship and policy tests pass.
Execution: One builder in a worktree off `origin/develop`.

## Risks + recovery

Each screenshot reads the marker in the eval that already read the kind, so no call is added. A page that clears `window.hardEngMasked` can only make the capture refuse. Cleanup now removes a worktree with an initialized submodule: the check needs a remote in the submodule that holds its commit, and refuses when none does. Cleanup ignores keys it does not know only while it proves the merge. Recovery: revert the commits.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Pending
Evidence: Pending the Complete check.
E2E: N/A — the change is a check inside the capture command and the cleanup guard, proved by the real-browser tests and the real Git tests above.
Real service: Required — GitHub and Git: `ship --stage cleanup` removes this task's own worktree, which has initialized submodules, and its remote branch from a checkout of develop, after the merge.
Retro: Pending.

Delivery target: Merge
Delivery: Pending — required remote proof.
