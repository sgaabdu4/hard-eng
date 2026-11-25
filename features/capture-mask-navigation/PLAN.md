# Capture refuses a page that changed document after masking, cleanup removes a worktree with clean submodules, and the UI proof names every bad image

Status: Complete

## Outcome + scope

`browser capture` and `browser measure` keep no image and no record when the page became another document after its emails and phones were hidden. A route change inside the same document still captures. `ship --stage cleanup` removes a clean, fully merged task worktree whose submodules are initialized, and it runs from a checkout that is older than the task. `ship` and the local check name every After image that matches no measured capture, in one message and through one owner, and `look` refuses a stale copy of an older capture. Non-goals: masking again after a navigation, and any change to what cleanup proves about the merge.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's follow-up of 2026-11-25 after PR 736, and the two refused cleanups of earlier builders.

## Repository context

Owners: `require_readable_document` in `.hooks/browser.py` owns the checks of the document around the screenshot. `cleanup_guard` in `.hooks/ship_actions.py` owns what a cleanup keeps. `_policy` in `.hooks/shipping.py` owns the reading of the shipping policy.
Same cause: the capture fault and the cleanup faults come from checks that read one document or one checkout only. The page script hides emails and phones in one document only. A navigation after it replaced that document with an unmasked one, and the kind check passed because the new page is HTML. The page script now sets `window.hardEngMasked`; a new document has no such value. The one kind check reads it together with the kind and, after the masking, refuses a document without it. A refusal is smaller than masking again, and it keeps one owner.
First cleanup fault: the guard refused every initialized submodule, although the removal already uses `git worktree remove --force` for it. A submodule holds work that no remote has only when it is off its recorded commit, or has a local branch commit, a stash, or an untracked or ignored file. The recorded commit itself is not tested against the remotes: a shallow submodule of a Hard Eng worktree has no remote ref for it. `submodule_work` checks exactly that, so a clean submodule no longer blocks.
Second cleanup fault: the main checkout runs the released code, and the task's `hard-eng.gates.json` can hold a key that only develop knows (`ui_library` since 2026-11-25). The strict reader refused it as an unknown key. A cleanup proves only a merge, so `reading_newer_policy_keys` skips unknown keys for that stage alone; every other stage keeps the strict reader.
Fourth fault: `measured_problem` stopped at the first After image that matches no capture, and the local check never looked at opened images that match no record, so a client saw one of eight bad images only at `ship`. `measured_digest_problem` in `.hooks/ui_proof.py` is the one owner: it names all of them, `measured_problem` calls it with the PR images, and the local check calls it with the images of the newest clean `look` record of each changed route, and of each refused record of the head that is newer than all of those, so a later `look` on the clean captures replaces an earlier one that held strays. A rerun of `look` that keeps its verdict refreshes the record time, so it counts as the later run. A mockup that is opened in a `look` run with no capture is an After image for this check; `ship` judges the PR images only, and `look` takes After images. A dirty tree counts its own capture set at the head. Fifth fault: `look` opened a copy of an older capture; `stale_problem` in `.hooks/look_records.py` refuses it and names the capture at the head with the same route and width. The Stop hook runs `check --quick`, which never reaches the local UI proof, so no hook time is added.
Single source: one kind check, one submodule check, one policy reader. The shared `delivered_worktree` fixture moved to `tests/conftest.py`, and the submodule tests moved to `tests/test_ship_cleanup_submodules.py`, so the 1000-line limit holds.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; the coordinator set this follow-up on 2026-11-25.

## Acceptance + steps

- [x] A page that navigates to another HTML page with an email on it after masking, before the frame check, keeps no image and no record → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_navigates_after_it_was_masked[before]`
- [x] The same navigation while the screenshot is taken keeps no image and no record → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_navigates_after_it_was_masked[during]`
- [x] A page that does not navigate still captures, also when it changes its route in place → `tests/test_browser_documents.py::test_capture_keeps_the_image_of_a_page_that_changes_its_route_in_place`, `tests/test_browser.py::test_capture_draws_boxes_at_each_width`
- [x] Cleanup removes a clean, merged task worktree that has an initialized submodule → `tests/test_ship_cleanup_submodules.py::test_cleanup_removes_task_whose_submodule_holds_nothing_else[initialized]`
- [x] Cleanup keeps a worktree whose submodule holds an edit, an ignored file, a local commit, a stash or a moved commit → `tests/test_ship_cleanup_submodules.py::test_cleanup_preserves_work_that_only_the_submodule_holds`, `tests/test_ship_cleanup_submodules.py::test_cleanup_preserves_a_submodule_moved_off_the_recorded_commit`
- [x] A page that navigates to the same URL again after masking is refused too, so the check compares the document and not its URL → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_navigates_after_it_was_masked[same url-before]`
- [x] `ship` names all eight After images that match no capture, and the single-image message stays → `tests/test_ui_capture_match.py::test_every_unmatched_after_image_is_named_in_one_message`, `tests/test_ui_capture_match.py::test_one_unmatched_after_image_keeps_the_single_image_message`
- [x] The local check gives the same verdict as `ship` for the same captures, and fresh captures at the head still pass → `tests/test_local_ui_proof.py::test_local_complete_check_names_every_opened_image_that_matches_no_capture`
- [x] Cleanup removes a worktree whose shallow submodule has no remote ref for its recorded commit → `tests/test_ship_cleanup_submodules.py::test_cleanup_removes_task_whose_shallow_submodule_has_no_remote_branch_ref`
- [x] A later `look` on the clean captures replaces an earlier record that held strays → `tests/test_local_ui_proof.py::test_local_complete_check_passes_again_after_look_runs_on_the_clean_captures_only`
- [x] A refused `look` older than the clean one is ignored, and a newer one is named → `tests/test_local_ui_proof.py::test_local_complete_check_ignores_a_refused_look_that_an_older_clean_look_outlasts`
- [x] A refused `look` older than a later clean `look` of another route is ignored → `tests/test_local_ui_proof.py::test_local_complete_check_ignores_a_refused_look_that_a_later_clean_look_of_another_route_outlasts`
- [x] A rerun of `look` that keeps its verdict refreshes the record time → `tests/test_look.py::test_a_second_run_at_the_same_head_keeps_the_first_verdict`
- [x] A dirty tree counts its own capture set although an older set holds the same image → `tests/test_local_ui_proof.py::test_local_complete_check_counts_the_dirty_capture_when_an_older_set_has_the_same_image`
- [x] The quick check, which the Stop hook runs, never runs the local UI proof → `tests/test_local_ui_proof.py::test_the_quick_check_never_runs_the_local_ui_proof`
- [x] `look` refuses a stale copy and names the newer capture, and a mockup with no record stays allowed → `tests/test_look_stale.py::test_a_stale_copy_is_refused_and_the_newer_capture_is_named`, `tests/test_look_stale.py::test_every_stale_image_is_named_in_one_message`, `tests/test_look_stale.py::test_a_mockup_with_no_capture_record_is_still_reviewed`
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

Result: Passed
Evidence: The focused files for capture, look, the local UI proof, cleanup and the shipping checks passed on each fix. The static gates (ruff format, lint, complexity, annotations, pyrefly, vulture, deptry) passed. The independent review found five real faults over four rounds, each with a red test first: a shallow submodule blocked cleanup, an older refused `look` or a dirty capture set blocked the local check, a kept `look` verdict kept its old time, and the cutoff used the oldest route. Round four was clean at ff6032d8. A mockup opened in a `look` run counts as an After image for the local check; that case was declined, as the plan says. The Complete check result is in the pull request.
E2E: N/A — the change is a check inside the capture command and the cleanup guard, proved by the real-browser tests and the real Git tests above.
Real service: Required — GitHub and Git: `ship --stage cleanup` removes this task's own worktree, which has initialized submodules, and its remote branch from a checkout of develop, after the merge. Its result is in the pull request.
Retro: A capture check that read one document missed a navigation, and cleanup guards that read one checkout missed shallow submodules and newer policy keys. Each check now reads the state it judges, and each new defect has a red test. Escaped bug: found on the base branch; the red tests above are its repro and its fix is in this PR.

Delivery target: Merge
Delivery: Pending — required remote proof.
