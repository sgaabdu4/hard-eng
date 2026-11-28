# Look and ship: six false findings and false blocks

Status: Complete

## Outcome + scope

Six faults gave a false finding in `look` or a false block in `ship`. Each is fixed at its owner, in its own commit, with a failing test first. (1) A capture moves the pointer off the page before it measures, so a hover fill from an earlier click stays out of the image. (2) The capture record holds the image height and the screen height, and the `look` prompt gives both for each image, so a tall image is not read as a cut one. (4) The capture record holds the verbs of the steps taken on the page since it loaded (never the typed text, which can be personal data), and the prompt names them for an image taken after steps. (3) A `[judgement]` item that says a control is too small to tap is refused and must be written as a `[tap]` item, so code checks it against the measured size; a true small control still fails. (5) Challenge and look records live in the repository's shared Git folder (`git rev-parse --git-common-dir`), so removing the task worktree keeps them. (7) A file that a Hard Eng update installs (`maybe_installed`) is never a screen file for UI evidence, so `ship --stage delivered` asks no Before and After for an update PR. A PR that also changes a project screen file still needs it. The seventh item of the request, a prose fix to an old Complete plan, did not reproduce and changed no code. Non-goals: new check rows, changed measured limits.

## Sources + coverage

Sources: N/A — a read of the code on `main` named seven faults; each was proved red here first, and one did not reproduce.

## Repository context

Owners: `.hooks/browser.py` (`shoot_page`), `.hooks/ui_measure.py` (`write_record`), `.hooks/look.py` (`capture_note`, `NOTES_SECTION`), `.hooks/look_records.py` (`image_keys`), `.hooks/look_facts.py` (`TRIGGER`), `.hooks/look_answer.py` (`CLAIM_NOTES`), `.hooks/challenge.py` (`store`), `.hooks/ui_proof.py` (`matches`, `file_names`).
Same cause: items 2 and 4 share one record and one prompt section. Items 3's trigger joins the three that exist (radius, align, gap). Item 5: every reader of the stores goes through `challenge.store`; `plan_controls` already reads the folder of each worktree, so an older mockup record is still read there. A task in a linked worktree loses carried look records once and runs `look` again; carry, earlier findings and earlier reviews match by image key or by ancestor of the head, so the shared folder leaks no finding to another branch. The ship record (`hard-eng/ship`) stays per worktree, because the merge hook reads it in the checkout that ran `ship ready`; `delivered` does not read it. Item 7: `matches` is the one owner of "a UI file", so the PR text check, `ship` and the local check all agree; the check for an installed path is by path only (`maybe_installed`), not by the proof of a verified update (`update_written`), because the proof needs a network call. The fault shows only when `ui_paths` matches an installed path.
Single source: `maybe_installed` stays the one list of installed paths; `file_names` filters by `matches`, so the import of `update` happens only for a file that already matches `ui_paths`.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The coordinator merges through ship. Hard Eng design calls are the maintainer's agent's (AGENTS.md); this PR changes no check row and no measured limit.

## Acceptance + steps

- [x] After a click, `browser measure` keeps no hover fill in the image → `tests/test_browser_hover.py::test_measure_keeps_no_hover_fill_after_a_click`.
- [x] The capture record holds the image height and the screen height, and the prompt gives both for each image → `tests/test_capture_notes.py::test_a_capture_record_holds_the_image_and_screen_height` and `tests/test_capture_notes.py::test_the_prompt_gives_the_reviewer_each_image_and_screen_height`.
- [x] The record holds the verbs of the steps since the page loaded, a fresh capture holds none, and the prompt names them for an image taken after steps → `tests/test_capture_notes.py::test_a_capture_record_holds_the_steps_taken_on_the_page` and `tests/test_capture_notes.py::test_the_prompt_names_the_steps_that_led_to_a_changed_image`.
- [x] A `[judgement]` tap-size claim on a keyed control is refused, a `[tap]` claim that the size disproves passes, and a true small control still fails → `tests/test_look_claims.py::test_a_tap_size_claim_is_checked_against_the_size_of_its_control`.
- [x] A record made in a task worktree is read from the main checkout after the worktree is removed → `tests/test_record_store_shared.py::test_a_record_made_in_a_task_worktree_outlives_it`.
- [x] A Fail record of another branch gives no recheck item, and a later commit of the same branch does → `tests/test_record_store_shared.py::test_a_fail_record_of_another_branch_is_no_recheck_item`.
- [x] `delivered` asks no screen evidence for an installed file, and still asks it for an installed file with a project screen file → `tests/test_delivered_update_pr.py::test_delivered_asks_no_screen_evidence_for_installed_files_only` and `tests/test_delivered_update_pr.py::test_delivered_still_asks_screen_evidence_for_an_installed_and_a_project_screen_file`.
- [x] A prose fix to an old Complete plan needs no captures → N/A — not reproduced at `validate_plans`, `validate_suppressions`, `validate_local_ui_proof` and `ship_problem`, because the local check returns early when no `ui_paths` file changed; no code changed.

## Baseline + execution

Result: Passed
Evidence: 2026-11-28, develop 5f480ad4 passed CI (`hard-eng`, `hard-eng-checks`, `hard-eng-tests 1` to `6`, `canary`, `pr text`). Before each fix its new test failed: hover pixel was the hover colour; `viewport_height` and `steps` were missing from the record; the tap claim returned `findings`; the record was missing from the shared folder; `delivered` raised the UI evidence refusal for an installed file.
Execution: One builder, this session.

## Risks + recovery

Item 1 undoes a hover reached by a deliberate `hover` step: the capture shows the page at rest, as the reviewer judges it. The pointer moves to (-1, -1), outside every element. Item 4 notes verbs only, not text, because typed text can be personal data. The capture notes join the image key, so a record made before this change no longer carries to a new head once; `look` runs again. A tap trigger that is too wide refuses a note that only mentions tapping; the refusal names the exact form to write. Item 7 treats every path under the installed prefixes as no screen file, for all PRs; a project that keeps its own screen files there would skip UI evidence for them, and the update owns those paths. Undo: revert the PR's commits.

## ux_reference

N/A — check messages and command output only; no visible UI.

## Verification

Result: Passed
Evidence: 628 focused tests passed (the 7 new test files and the look, browser, ship, plan and challenge tests next to them). Static gates pass: format, lint, complexity, annotations, types, dead-code, Semgrep. `hot-paths` reports 0 findings. Item 6 was probed at four entries and not reproduced.
Review: a fresh review of 2d6fdeea found five items. Fixed: the tap trigger matched any note that names a tap target, so a note about an overlap was refused; it now matches only a size claim (`tests/test_look_claims.py::test_a_tap_size_claim_is_checked_against_the_size_of_its_control`). Review declined: (1) carry from a clean record of another branch needs byte-equal images, equal measured values, design and scope, so that verdict judged the same inputs; one worktree could always carry across branches, and a carry after a rebase needs it; (2) moving the pointer off the page is the requested fix, and Risks names the menu that closes on pointer exit; (3) two byte-equal full-page images from different screen heights are far-fetched, and the measured values use the same lookup by image bytes; (5) a failed step still gives only a verb as context, and the action log is the existing owner of that record.
E2E: N/A — no user journey changes; the browser tests drive a real browser through `browser measure`.
Real service: N/A — the change calls no outside service.
Retro: (1) a read of the code with no second check named a fault that did not exist, so each item was proved red first and one was dropped → `tests/test_record_store_shared.py::test_a_fail_record_of_another_branch_is_no_recheck_item` holds the shared-store case that the first read missed.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
