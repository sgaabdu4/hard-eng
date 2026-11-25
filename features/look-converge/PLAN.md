# Make the look review converge

Status: Complete

## Outcome + scope

`look` gives the same Fail list on every run of one image set, so a set that has faults reaches a clean verdict in one fix round. In scope, one commit each:
1. The prompt and the parser require every frame and element for each failing rule, and the next run gets each earlier Fail as a numbered item to recheck ("still shown" or "gone", with the frame).
2. An earlier Fail is listed as an earlier finding with no claim that it was fixed.
3. A Fail whose `Fix:` sits on an indented line, a sub-bullet or after a blank line in the same rule block counts as having a fix; a block with no `Fix:` is still refused.
4. A second run at the same head with the same inputs keeps the first clean or findings verdict and is refused.
5. Rules that the measure record can decide (accent count, button groups, edges, secondary text and corner radii against the `DESIGN.md` tokens) become code verdicts that the reviewer cannot overrule.
Out of scope: gaps against spacing tokens (the measure holds arbitrary gaps for `space-between` rows and 0 for touching items) and text sizes against typography tokens (fluid type and a changed root size make a rendered size inexact), so the reviewer keeps both and no truthful code verdict exists; any other `look` change, and any other project.

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

- [x] A Fail whose `Fix:` is on an indented continuation line, a sub-bullet or after a blank line is read as having a fix; a Fail with no `Fix:` in its block, or whose only `Fix:` belongs to the next rule, is still refused → `tests/test_look_answer.py::test_a_fail_with_its_fix_on_a_continuation_line_is_read_whole`.
- [x] A Fail that persists across two heads is listed as an earlier finding, never as fixed → `tests/test_look_carry.py::test_the_prompt_lists_an_earlier_fail_without_calling_it_fixed`.
- [x] A Fail line must name a frame of the run (`image-N.png`) and its element; an answer that names none is refused → `tests/test_look_answer.py::test_a_fail_line_must_name_the_frame_it_shows`.
- [x] The next run holds each earlier Fail as a numbered item, also when the image bytes did not change; the answer must say "still shown" or "gone" for each item with a frame, and "still shown" needs a Fail line for the rule → `tests/test_look_carry.py::test_each_earlier_fail_is_rechecked_one_by_one`.
- [x] A second run at the same head and inputs keeps the first clean or findings record, prints it again and starts no reviewer; a run that ended `not done`, and a run with other inputs, still run → `tests/test_look.py::test_a_second_run_at_the_same_head_keeps_the_first_verdict`.
- [x] A measure finding of a mapped rule (accent count, button groups, edges, secondary text) is a code Fail that the reviewer's Pass cannot overrule; a code Pass never replaces a reviewer Fail → `tests/test_look_proof_kinds.py::test_a_measure_finding_fails_its_judged_rule_in_code`.
- [x] A measured corner radius that no `DESIGN.md` token holds is a code Fail on Design system; a clamped radius, a missing token group, a token that is not a plain length, a text size outside the tokens, and an old record without the clamp field or the root size give no verdict → `tests/test_look_proof_kinds.py::test_a_radius_outside_the_tokens_fails_design_system_in_code`.
- [x] 5 `look` runs on one frozen invented fixture report the rate of the same Fail set (not a promise of 5 of 5: the reviewer still judges), and each later run holds the earlier Fails as items; a run after the fixture's faults are fixed is clean → N/A — real model runs, not a test; the records are in the `Real service:` line.

## Baseline + execution

Result: Passed
Evidence: 2026-11-24, develop 069ccacd; `uv run --frozen pytest -q tests/test_look.py tests/test_look_carry.py tests/test_look_proof_kinds.py tests/test_look_px.py`: 79 passed.
Execution: One builder, this session.

## Risks + recovery

A stricter parser refuses a real reviewer answer that names no frame; the prompt gives the exact form, and the run is `not done`, never a wrong verdict. A wrong code Fail blocks a project that cannot overrule it, so each code rule decides only what the measure holds exactly: clamped radii, tokens that are not plain lengths and old records give no verdict, and gaps and text sizes stay with the reviewer. A judged rule that a frame shows only half can still flip between runs; a later run holds each reported Fail as a recheck item, but it cannot hold a Fail that no run reported. Recovery: revert the commit of the item.

## ux_reference

N/A — no visible screen; the change edits the look review's prompt, parser and records.

## Verification

Result: Passed
Evidence: 2026-11-25. Red first: the item 1 tests failed (14) on the code of item 2, the item 4 tests failed (3), the item 5 tests failed (8), each before its code. Then `uv run --frozen pytest -q tests/test_look.py tests/test_look_answer.py tests/test_look_carry.py tests/test_look_proof_kinds.py tests/test_look_px.py`: 125 passed. `check --static --plan-stage Ready --base origin/develop` passed.
E2E: N/A — no user journey of an installed project changes; the real `look` runs are in the `Real service:` line.
Real service: Passed — model reviewer (`look` ran Claude in each run) on an invented seed-shop page, 3 frames (390, 768, 1280 px), captured by `browser capture` in a real browser, known faults: two filled buttons, a repeated status and helper text, a blaming error text, an are-you-sure text, a 13 px text and a 7 px radius outside the tokens. Final code, five runs in five worktrees at one commit (record sha256 prefixes cdad22c5c6c1, 98cca7db32bf, 82fe8838e0c8, 55cd15c48820, 376b8a4eb4cc): the exact Fail set was the same in 2 of 5 runs (rate 0.4; 3 different sets), and the 8 rules Accessibility, Alignment, Design system, Hierarchy, Messages, Mistake-proof (5 of 5), No clutter and Widths failed in all 5; Undo failed in 4 and Spacing in 2, which are judged rules that the fixture shows only half. Earlier batches on earlier code: 4 of 5, then 2 of 5 where 2 runs were `not done` because the reviewer wrote a count note after the verdict, which this change now reads. So the same set in every run is not reached for borderline judged rules; the change makes each reported Fail return as a numbered item. Fix rounds in one worktree after the five runs (10 Fails then): round 1 (record 73722992440f) answered 4 of 4 items `gone` and found one new real fault (a `#ffffff` label); round 2 (f50e1f8cebf3) answered its item `gone` and found one new judgement (a footer that repeats the heading); round 3 after removing the footer was clean (record 1ea748b15840, rechecked `gone`). The reviewer still finds one new item in some rounds, so a set can need more than one fix round here. No fixture text or name belongs to a real project.
Retro: (1) the file-length gate refused `look.py` and `test_look.py` after the change, so the answer reader and its tests moved to `look_answer.py` and `tests/test_look_answer.py` → `tests/test_look_answer.py` holds them; (2) older plans named the moved tests, and the plan check refused them → each older plan now names the new file; (3) three older tests reran at one head and met the new refusal → they commit between runs. None to prevent beyond the push gates.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
