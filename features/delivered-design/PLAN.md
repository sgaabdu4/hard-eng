# Judge a merged UI PR against its own design, and let cleanup remove the proof it needs

Status: Ready

## Outcome + scope

`ship --stage delivered` compares a PR's look record with the design documents at the PR's own head, not with the checkout that runs it, and `ship --stage cleanup` removes the proof folder itself instead of telling the user to delete it before delivered has proof to read. Non-goals: the other checkout reads in `ship_problem` (visible file text, guidelines, generated sources), the local pre-push proof, and any change to what a look record holds.

## Sources + coverage

Sources: N/A — a client report relayed in the task brief: delivered fails for a merged UI PR after DESIGN.md changed on the base, and cleanup removed the capture and look records before delivered ran.
Deliverables: None

## Repository context

Owners:
- `.hooks/look.py` `design_hash`, `design_text` and `_raw_design_sections` read the design documents; they gain an optional revision.
- `.hooks/ui_proof.py` `look_record_problem` compares a record with that hash for `ship`.
- `.hooks/look_records.py` `carried_record`, `record_files` and `records_for` build the design key of a carried record.
- `.hooks/ship_actions.py` `unchanged_checkout` is the cleanup guard.
- `.hooks/local_ui_proof.py` `_local_look_problem` stays on the disk on purpose: the local proof judges the working tree before a push.

Same cause: Related earlier fix: `features/post-merge-unchanged-base-sha` (the unchanged-pair check used the base after the merge; helped for that check only). Searched for other delivered readers of the checkout's DESIGN.md: `look_record_problem` and the carried-record key, both fixed here. Two other delivered readers of checkout files are left out because the brief limits this change to the design hash: the text of new visible files in `ship_problem`, and `guideline_problem`.
Single source: The design hash of a PR is computed only by `look.design_hash(root, revision)`. Its readers are `ui_proof.look_record_problem` (ship, at the PR head), `look_records.carried_record` through `records_for` (ship, at the PR head) and `local_ui_proof._local_look_problem` (disk, local). No other copy of the hash found by searching `.hooks` and `tests` for `design_hash`, `design_text` and `design_doc`.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; a client's merged UI PR could not pass delivered.

## Acceptance + steps

Cleanup choice: cleanup already runs the delivered check before it removes anything, and Hard Eng owns `.hard-eng/` (captures, sessions, update state). The fault is that the guard counted `.hard-eng/` as foreign ignored work and told the user to delete it first, so the next delivered run had no capture records. Treating the proof, session and update files in `.hard-eng/` as Hard Eng's own is a small change in the one guard; other files there, such as a client report, still block cleanup. The other choice, a new proof store that cleanup cannot remove, changes every reader of `.hard-eng/browser`.

- [ ] A PR whose DESIGN.md changed on the base after its merge still passes the look check → `tests/test_delivered_design.py::test_a_merged_pr_still_passes_after_the_base_changes_design_md`.
- [ ] A record carried from an earlier head still backs the PR head after the base changes DESIGN.md → `tests/test_delivered_design.py::test_a_carried_record_still_backs_the_head_after_the_base_changes_design_md`.
- [ ] Near miss: a record that judged another design than the PR head holds still fails → `tests/test_delivered_design.py::test_a_record_that_judged_another_design_than_the_pr_head_still_fails`. It replaces the last three lines of `test_look_includes_design_docs_in_prompt_record_and_block`, which changed DESIGN.md on the disk after the look and expected a failure; that case now passes by design, and the replacement keeps the stale-record protection.
- [ ] The design hash of a revision reads the commit, and an unknown commit raises → `tests/test_delivered_design.py::test_the_design_hash_of_a_revision_ignores_the_checkout`.
- [ ] Cleanup removes `.hard-eng/` without asking for its deletion, and still refuses other ignored work → `tests/test_ship_cleanup.py::test_cleanup_removes_the_proof_folder_instead_of_asking_for_its_deletion`.
- [ ] Cleanup still refuses private files that other skills keep in `.hard-eng/` → `tests/test_ship_cleanup.py::test_cleanup_keeps_private_files_that_other_skills_put_in_the_proof_folder`.
- [ ] The design hash reads CRLF text the same from the disk and from a commit → `tests/test_delivered_design.py::test_the_design_hash_reads_crlf_text_the_same_from_the_disk_and_a_commit`.
- [ ] Cleanup removes nothing while delivered does not pass → `tests/test_ship_cleanup.py::test_cleanup_keeps_the_proof_when_delivered_does_not_pass`.

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` 4b8f3a45 the new tests fail as intended: three design tests and the cleanup test (two fixture variants) fail, the near miss and the delivered-first guard pass. Static gates and the Ready check are recorded in Verification.
Execution: One builder in a separate worktree of the repository: tests first, then `look.py`, `look_records.py`, `ui_proof.py`, `ship_actions.py`, then challenge and the Complete check.

## Risks + recovery

A PR head missing from the checkout now raises "commit ... is not in this checkout" in the look check instead of reading another design; delivered runs where the PR was built, so the head is present. Cleanup now removes the proof, session and update files of `.hard-eng/` in a merged, delivered task; any other file in that folder still blocks cleanup. Recovery: revert the merge commit on `develop`.

## ux_reference

N/A — hook Python logic has no user interface.

## Verification

Result: Pending
Evidence: Pending — focused tests, static gates, challenge and the Complete check.
E2E: N/A — CLI shipping check with no interactive journey; the tests build real git repositories and worktrees.
Real service: N/A — no changed code calls an outside service.
Retro: Pending

Delivery target: PR
Delivery: Pending — checks, challenge, PR to `develop`, CI and merge.
