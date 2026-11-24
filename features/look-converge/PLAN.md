# Make the look review converge

Status: Ready

## Outcome + scope

`look` gives the same Fail list on every run of one image set, so a set that has faults reaches a clean verdict in one fix round. In scope, one commit each:
1. The prompt and the parser require every frame and element for each failing rule, and the next run gets each earlier Fail as a numbered item to recheck ("still shown" or "gone", with the frame).
2. An earlier Fail is listed as an earlier finding with no claim that it was fixed.
3. A Fail whose `Fix:` sits on an indented line, a sub-bullet or after a blank line in the same rule block counts as having a fix; a block with no `Fix:` is still refused.
4. A second run at the same head with the same inputs keeps the first clean or findings verdict and is refused.
5. Rules that the measure record can decide (accent count, button groups, edges, text sizes and corner radii against the `DESIGN.md` tokens) become code verdicts that the reviewer cannot overrule.
Out of scope: gaps against spacing tokens (the measure holds arbitrary gaps for `space-between` rows and 0 for touching items, so no truthful verdict exists), any other `look` change, and any other project.

## Sources + coverage

Sources: N/A — found by real client pull requests that could not finish `look` (the carry reset after a `DESIGN.md` or scope edit, a new genuine Fail in each run, a flip on byte-equal images). The maintainer's evidence logs stay outside this public repository.

## Repository context

Owners: `.hooks/look.py` (prompt, reviewer answer parser, run record), `.hooks/look_records.py` (carried records, earlier findings, owner lines; the proof-kinds owner), `.hooks/ui_measure.py` (measure script, `PROOF_KINDS`, limits), `.hooks/ui_tokens.py` (`DESIGN.md` front matter reading). No second owner is added; the finding-to-rule table sits beside `PROOF_KINDS`, and the token verdict sits in `look_records.py` beside `owner_lines`.
Data flow: `look_command` reads the images, keys each one (`image_keys`), asks `review`, then `with_owner_lines` swaps in the owner lines. Items 1 to 3 change `review` and `judge`; item 4 changes `look_command`; item 5 changes `owner_lines`.
Same cause: items 1, 2 and 3 share one cause, which is that the run keeps no list of earlier Fails and the parser reads one line for each rule; they stay separate commits in the same two files. Items 4 and 5 have other causes (a record path that a rerun overwrites, and measured values that only the reviewer reads) and other owners.
Single source: one finding-to-rule table beside `PROOF_KINDS` and the `DESIGN.md` tokens read by `ui_tokens.py`; the earlier-findings list and its recheck items come from one function in `look_records.py`.
Any edit of the prompt changes every image key, so each project's clean records stop carrying once after this release. The PR says so.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked on 2026-11-24 to make Hard Eng correct before the release; client pull requests cannot finish `look`.

## Acceptance + steps

- [ ] A Fail whose `Fix:` is on an indented continuation line, a sub-bullet or after a blank line is read as having a fix; a Fail with no `Fix:` in its block, or whose only `Fix:` belongs to the next rule, is still refused → `tests/test_look.py::test_a_fail_with_its_fix_on_a_continuation_line_is_read_whole`.
- [ ] A Fail that persists across two heads is listed as an earlier finding, never as fixed → `tests/test_look_carry.py::test_the_prompt_lists_an_earlier_fail_without_calling_it_fixed`.
- [ ] A Fail line must name a frame of the run (`image-N.png`) and its element; an answer that names none is refused → `tests/test_look.py::test_a_fail_line_must_name_the_frame_it_shows`.
- [ ] The next run holds each earlier Fail as a numbered item, also when the image bytes did not change; the answer must say "still shown" or "gone" for each item with a frame, and "still shown" needs a Fail line for the rule → `tests/test_look_carry.py::test_each_earlier_fail_is_rechecked_one_by_one`.
- [ ] A second run at the same head and inputs keeps the first clean or findings record, prints it again and starts no reviewer; a run that ended `not done`, and a run with other inputs, still run → `tests/test_look.py::test_a_second_run_at_the_same_head_keeps_the_first_verdict`.
- [ ] A measure finding of a mapped rule (accent count, button groups, edges, secondary text) is a code Fail that the reviewer's Pass cannot overrule; a code Pass never replaces a reviewer Fail → `tests/test_look_proof_kinds.py::test_a_measure_finding_fails_its_judged_rule_in_code`.
- [ ] A measured text size or corner radius that no `DESIGN.md` token holds is a code Fail on Design system; a clamped radius, a token set that is missing and an old record without the clamp field give no verdict → `tests/test_look_proof_kinds.py::test_a_size_or_radius_outside_the_tokens_fails_design_system_in_code`.
- [ ] 5 `look` runs on one frozen invented fixture give the same Fail set; a run after the fixture's faults are fixed is clean → N/A — real model runs, not a test; the records are in the `Real service:` line.

## Baseline + execution

Result: Passed
Evidence: 2026-11-24, develop 069ccacd; `uv run --frozen pytest -q tests/test_look.py tests/test_look_carry.py tests/test_look_proof_kinds.py tests/test_look_px.py`: 79 passed.
Execution: One builder, this session.

## Risks + recovery

A stricter parser refuses a real reviewer answer that names no frame; the prompt gives the exact form, and the run is `not done`, never a wrong verdict. A wrong code Fail blocks a project that cannot overrule it, so each code rule decides only what the measure holds exactly: clamped radii, unknown tokens and old records give no verdict, and gaps stay with the reviewer. Recovery: revert the commit of the item.

## ux_reference

N/A — no visible screen; the change edits the look review's prompt, parser and records.

## Verification

Result: Pending
Evidence: Pending — red tests fail first, then pass at the final head.
E2E: N/A — no user journey of an installed project changes; the real `look` runs are in the `Real service:` line.
Real service: Required — model reviewers (claude and codex through `look`): 5 runs on one frozen invented fixture with known faults, then one run after the fixes.
Retro: Pending
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
