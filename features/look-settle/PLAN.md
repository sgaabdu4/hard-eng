# `look` settles: reuse the images with no Fail, and never cut the design text

Status: Ready

## Outcome + scope

`look` reads an image again only when it needs to. A findings record of an earlier head now covers each image that had no Fail in it: the image was read, its input key is the same now, and no Fail item of the record names it first. Only the images that failed, or whose inputs changed, go to the reviewer. A disproved dispute still covers only while its cited bytes hold. A findings record never covers the whole set of a run, since the run record would then copy its Fail lines. A Fail item that names no image of the record, or an image entry with no name, makes the record cover nothing. An owner-check line (a measured or test line that code writes again at each head) does not hold an image back. `look` also stops cutting DESIGN.md and UI-LIBRARY.md. When the pair is over `DESIGN_BYTE_LIMIT`, `look` refuses before any review and names each file, its size and the limit; the limit is the same, and text under it is sent byte for byte as before. The cut code is removed. Non-goals: raising the limit, a second partial-cover path, a change to the clean carry, and any new rule.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-27 and the report of one installed project that it cites.

## Repository context

Owners: `.hooks/look_records.py` (`covering_record`, `combined`), `.hooks/look.py` (`design_text`, `look_command`), `.hooks/look_dispute.py` (`cites_hold`, unchanged).
Same cause: a verdict record was reusable only when clean, so a head with one Fail read every image again and the reviewer found a new small item each round (6 heads in a row on one project); and DESIGN.md plus UI-LIBRARY.md were cut with a marker, so the reviewer never saw the last rules and a dispute stood against a line it never got. Both made `look` fail to settle.
Single source: `look_records.covering_record` is the one owner of partial cover, and `combined` keeps the one merge path. `look.design_text` is the one owner of the design text; `carried_record` and `look_command` both call it. Measured sizes: this repository's DESIGN.md and the scaffold template are about 2 KB and no scaffold writes a UI-LIBRARY.md, so no `install_new` flow reaches the refusal.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the coordinator's brief of 2026-11-27 asks for this fix, and the coordinator merges the PR into `develop` through ship.

## Acceptance + steps

- [ ] A findings record covers each image with no Fail and the review gets only the failed image → `tests/test_look_findings_cover.py::test_a_findings_record_covers_each_image_that_holds_no_fail`
- [ ] A changed key leaves its image uncovered while the other passing image is covered → `tests/test_look_findings_cover.py::test_an_image_whose_key_changed_is_not_covered_by_a_findings_record`
- [ ] A Fail item owns only the image it names first → `tests/test_look_findings_cover.py::test_a_fail_item_owns_only_the_image_it_names_first`
- [ ] A disproved dispute covers while its cited bytes hold and stops when they change → `tests/test_look_findings_cover.py::test_a_disproved_dispute_covers_only_while_its_cited_bytes_hold`
- [ ] A findings record never covers the whole run, and a Fail with no nameable owner covers nothing → `tests/test_look_findings_cover.py::test_a_findings_record_never_covers_the_whole_set` and `tests/test_look_findings_cover.py::test_a_fail_that_names_no_run_image_covers_nothing`
- [ ] The next head after a combined findings record still finds the failed image (names repeat in a combined record) → `tests/test_look_findings_cover.py::test_the_second_head_after_a_findings_head_reads_only_the_image_that_failed`
- [ ] An owner-check Fail does not hold an image back → `tests/test_look_findings_cover.py::test_an_owner_check_fail_does_not_hold_an_image_back`
- [ ] A design pair over the limit is refused with each name, size and the limit; a pair at the limit is sent whole; ship and the local proof refuse plainly → `tests/test_look_design_limit.py::test_a_design_pair_over_the_limit_is_refused_with_each_size` and `tests/test_look_design_limit.py::test_a_design_pair_at_the_limit_is_sent_whole` and `tests/test_look_design_limit.py::test_a_record_of_a_project_over_the_limit_gives_a_plain_refusal`

## Baseline + execution

Result: Pending
Evidence: Pending
Execution: One builder in a linked worktree off `origin/develop`: red tests first, then one commit for the cover and one for the design limit.

## Risks + recovery

A project whose DESIGN.md plus UI-LIBRARY.md is over the limit cannot run `look` until it cuts the files; before this change `look` ran on a cut text the reviewer could not fully read. A generated UI-LIBRARY.md index for a very large part library is the case that reaches it. An older record can still cover an image that a newer record failed with the same key; `--all` already allows this today. Recovery: revert the two commits.

## ux_reference

N/A — hook logic and tests only; no visible UI.

## Verification

Result: Pending
Evidence: Pending
E2E: N/A — hook tests run real temporary Git repositories and a scripted reviewer; no user journey changes.
Real service: N/A — local Git and Python only; no outside service is called.
Retro: Pending

Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
