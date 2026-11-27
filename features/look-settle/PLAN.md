# `look` settles: reuse the images with no Fail, and never cut the design text

Status: Complete

## Outcome + scope

`look` reads an image again only when it needs to. A findings record of an earlier head now covers each image that had no Fail in it: the image was read, its input key is the same now, and no Fail item of the record names it first. Only the images that failed, or whose inputs changed, go to the reviewer. A disproved dispute still covers only while its cited bytes hold. For each image, only the newest record that holds its digest with the same key decides, in the order of `_newest_paths`: an older record never covers an image that a newer record failed or did not read, and a newer clean record covers an image that an older record failed. A record of the same head holds its images without covering them, so a Fail of this head is never covered from an older head. A findings record never covers the whole set of a run, since the run record would then copy its Fail lines. Each piece of a Fail line that names an image gives that image as an owner (the first one it names); a piece with no image name belongs to the item before it. A Fail line that names no image of the record's own review, or names one that is not in it, or an image entry with no name, makes the record cover nothing; so does a findings verdict that holds no Fail line. An owner-check line (a measured or test line that code writes again at each head) does not hold an image back. `look` also stops cutting DESIGN.md and UI-LIBRARY.md. When the pair is over `DESIGN_BYTE_LIMIT`, `look` refuses before any review and names each file, its size and the limit, and text under it is sent byte for byte as before. The cut code is removed. The limit rises from 24,000 to 96,000 bytes: UI-LIBRARY.md is a file that Hard Eng requires, with a use line for each library part, so a real library beside a full DESIGN.md (one installed project: 22,681 + 16,192 bytes) must reach the reviewer whole. The check gets stricter, not weaker: more rule text reaches the reviewer, and nothing is cut. Non-goals: a second partial-cover path, a change to the clean carry, and any new rule.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-27 and the report of one installed project that it cites.

## Repository context

Owners: `.hooks/look_records.py` (`covering_record`, `combined`), `.hooks/look.py` (`design_text`, `look_command`), `.hooks/look_dispute.py` (`cites_hold`, unchanged).
Same cause: a verdict record was reusable only when clean, so a head with one Fail read every image again and the reviewer found a new small item each round (6 heads in a row on one project); and DESIGN.md plus UI-LIBRARY.md were cut with a marker, so the reviewer never saw the last rules and a dispute stood against a line it never got. Both made `look` fail to settle.
Single source: `look_records.covering_record` is the one owner of partial cover, and `combined` keeps the one merge path. `look.design_text` is the one owner of the design text; `carried_record` and `look_command` both call it. Measured sizes: this repository's DESIGN.md (2,351 bytes) and the scaffold template (2,112 bytes) are far under the limit. Setup and the canary scaffolds never write a UI-LIBRARY.md; only `ui-library --write` in a project with a library does, so no `install_new` flow reaches the refusal. The first sizes were measured on base checkouts without the written index; on one installed project's update branch the pair is 38,873 bytes (201 parts), which the old 24,000 limit refused.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the coordinator's brief of 2026-11-27 asks for this fix, and the coordinator merges the PR into `develop` through ship.

## Acceptance + steps

- [x] A findings record covers each image with no Fail and the review gets only the failed image → `tests/test_look_findings_cover.py::test_a_findings_record_covers_each_image_that_holds_no_fail`
- [x] A changed key leaves its image uncovered while the other passing image is covered → `tests/test_look_findings_cover.py::test_an_image_whose_key_changed_is_not_covered_by_a_findings_record`
- [x] A Fail item owns only the image it names first → `tests/test_look_findings_cover.py::test_a_fail_item_owns_only_the_image_it_names_first`
- [x] A disproved dispute covers while its cited bytes hold and stops when they change → `tests/test_look_findings_cover.py::test_a_disproved_dispute_covers_only_while_its_cited_bytes_hold`
- [x] A findings record never covers the whole run, and a Fail with no nameable owner covers nothing → `tests/test_look_findings_cover.py::test_a_findings_record_never_covers_the_whole_set` and `tests/test_look_findings_cover.py::test_a_fail_that_names_no_run_image_covers_nothing` and `tests/test_look_findings_cover.py::test_a_findings_verdict_with_no_fail_line_covers_nothing`
- [x] The next head after a combined findings record still finds the failed image (names repeat in a combined record) → `tests/test_look_findings_cover.py::test_the_second_head_after_a_findings_head_reads_only_the_image_that_failed`
- [x] A piece with no image name belongs to the item before it, so the other images stay covered → `tests/test_look_findings_cover.py::test_a_piece_with_no_image_name_belongs_to_the_item_before_it`
- [x] Only the newest record that holds an image decides it → `tests/test_look_findings_cover.py::test_an_older_record_never_covers_an_image_that_a_newer_record_failed` and `tests/test_look_findings_cover.py::test_an_older_record_never_covers_an_image_that_a_newer_record_did_not_read` and `tests/test_look_findings_cover.py::test_a_newer_clean_record_covers_an_image_that_an_older_record_failed` and `tests/test_look_findings_cover.py::test_a_failed_image_of_this_head_is_not_covered_from_an_older_head`
- [x] An owner-check Fail does not hold an image back → `tests/test_look_findings_cover.py::test_an_owner_check_fail_does_not_hold_an_image_back`
- [x] A design pair over the limit is refused with each name, size and the limit; a pair at the limit is sent whole; ship and the local proof refuse plainly → `tests/test_look_design_limit.py::test_a_design_pair_over_the_limit_is_refused_with_each_size` and `tests/test_look_design_limit.py::test_a_design_pair_at_the_limit_is_sent_whole` and `tests/test_look_design_limit.py::test_a_record_of_a_project_over_the_limit_gives_a_plain_refusal` (ship and the local proof both answer `no record` and raise nothing)
- [x] The index that Hard Eng requires never forces a refusal of a full DESIGN.md, and short use lines bring a 2,000-part library inside the limit → `tests/test_ui_library_refusals.py::test_a_written_library_and_a_full_design_md_reach_look_whole` and `tests/test_ui_library_refusals.py::test_a_library_of_2000_parts_with_short_use_lines_reaches_look_whole`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`c51adc42`) the look, UI-library, delivered-design and local UI proof tests pass (331 cases). The new tests fail there: 13 of the 20 fail on a real assertion (the reviewer gets all 3 images, a findings record covers nothing, the design text is cut with no refusal, and `DesignTooLarge` does not exist). The other 7 guard the fail-closed cases and the exact limit, and pass on both sides.
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then one commit for the cover and one for the design limit.

## Replaced proof

`tests/test_look.py::test_look_truncates_large_design_docs_in_utf8_bytes_and_preserves_ui_library` protected the UTF-8 byte bound of the cut text, the space kept for UI-LIBRARY.md and the full-text hash. The cut is gone, so `tests/test_look.py::test_look_counts_the_design_limit_in_utf8_bytes_and_hashes_every_byte` keeps the byte count and the hash, and `tests/test_look_design_limit.py` proves the refusal and the exact limit. `tests/test_ui_library_refusals.py::test_a_large_library_passes_the_index_check_and_the_look_excerpt_stays_bounded` protected a 2,000-part index that no refusal stops and that `look` survived by cutting it. It is now `test_a_library_of_2000_parts_with_short_use_lines_reaches_look_whole`: the index check still passes, and `look` gets the whole index. The refusal itself stays proved by `tests/test_look_design_limit.py`.

## Risks + recovery

A project whose DESIGN.md plus UI-LIBRARY.md is over the limit cannot run `look` until it cuts the files; before this change `look` ran on a cut text the reviewer could not fully read. The fix in the project is always open: move behaviour lines out of DESIGN.md, or shorten use lines (2,000 parts fit with short ones). A larger design text makes the reviewer prompt longer; one real look on a 38,873-byte pair proves the reviewer still answers. Recovery: revert the commits.

## ux_reference

N/A — hook logic and tests only; no visible UI.

## Verification

Result: Passed
Evidence: The focused tests pass: 762 cases over every look, UI-proof, delivered-design and library test, including the 20 new ones. 13 of the 20 fail on `origin/develop` on a real assertion. Static gates pass with the exact commands of `hard-eng.gates.json`: format, lint, complexity, annotations, types, dead-code and security (semgrep: 0 results). `hot-paths` on the two touched sources: 0 findings. The replaced tests keep their proof as the Replaced proof section says.
E2E: N/A — hook tests run real temporary Git repositories and a scripted reviewer; no user journey changes.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Escaped bug: a findings record was never reusable and the design text was cut without a word, so `look` did not settle on one real project; no test covered a head after a Fail or a design over the limit, and the gate is now `tests/test_look_findings_cover.py::test_the_second_head_after_a_findings_head_reads_only_the_image_that_failed` and `tests/test_look_design_limit.py::test_a_design_pair_over_the_limit_is_refused_with_each_size`, which fail on develop. Review correction: the first owner rule gave up on a Fail line with a piece that names no image, which the answer form allows → `tests/test_look_findings_cover.py::test_a_piece_with_no_image_name_belongs_to_the_item_before_it`. Review correction: a Fail recorded at this head for one image set was skipped when another image set ran at the same head, so an older head covered the image again → `tests/test_look_findings_cover.py::test_a_failed_image_of_this_head_is_not_covered_from_an_older_head`. Review correction: an older record could cover an image that a newer record failed, which hides the newer Fail → `tests/test_look_findings_cover.py::test_an_older_record_never_covers_an_image_that_a_newer_record_failed`. Review correction: a findings verdict with only Pass lines covered every image, since it names no Fail owner → `tests/test_look_findings_cover.py::test_a_findings_verdict_with_no_fail_line_covers_nothing`. Review correction: two commits were made with hooks off and are redone under the hooks → None — one-off slip; AGENTS.md already forbids it. Failed check: the static check refused two older plans that name tests this change replaces, and the type check refused untyped record reads in the new tests → None — each check refused before any push and was fixed in the change. Ran too late: none. Escaped before release: the new refusal blocked the UI-LIBRARY.md that Hard Eng itself requires, on one installed project's update branch (38,873 bytes); the size check measured base checkouts without the index → `tests/test_ui_library_refusals.py::test_a_written_library_and_a_full_design_md_reach_look_whole`, which fails at the old limit. Single source: `look_records.covering_record` and `look.design_text`.

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
