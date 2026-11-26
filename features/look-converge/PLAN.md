# Make the look review converge

Status: Complete

## Outcome + scope

`look` aims to give the same Fail list on every run of one image set, so that a set with faults reaches a clean verdict in few fix rounds. The real runs show that this holds for clear faults and not for borderline judged rules (see `Real service:`). In scope, one commit each:
1. The prompt and the parser require every frame and element for each failing rule, and the next run gets each earlier Fail as a numbered item to recheck ("still shown" or "gone", with the frame).
2. An earlier Fail is listed as an earlier finding with no claim that it was fixed.
3. Left out: the reading of a `Fix:` on a continuation line and of a count note after the verdict belong to the hotfix `hotfix/look-forms` (maintainer's scope change, 2026-11-25).
4. A second run at the same head with the same inputs keeps the first clean or findings verdict and is refused.
5. Rules that the measure record can decide (accent count, button groups, edges, secondary text and corner radii against the `DESIGN.md` tokens) become code verdicts that the reviewer cannot overrule.
Out of scope: gaps against spacing tokens (the measure holds arbitrary gaps for `space-between` rows and 0 for touching items) and text sizes against typography tokens (fluid type and a changed root size make a rendered size inexact), so the reviewer keeps both and no truthful code verdict exists; any other `look` change, and any other project.

## Sources + coverage

Sources: N/A — found by real client pull requests that could not finish `look` (the carry reset after a `DESIGN.md` or scope edit, a new genuine Fail in each run, a flip on byte-equal images). The maintainer's evidence logs stay outside this public repository.

## Repository context

Owners: `.hooks/look.py` (prompt, reviewer answer parser, run record), `.hooks/look_records.py` (carried records, earlier findings, owner lines; the proof-kinds owner), `.hooks/ui_measure.py` (measure script, `PROOF_KINDS`, limits), `.hooks/ui_tokens.py` (`DESIGN.md` front matter reading). No second owner is added; the finding-to-rule table sits beside `PROOF_KINDS`, and the token verdict sits in `look_records.py` beside `owner_lines`.
Data flow: `look_command` reads the images, keys each one (`image_keys`), asks `review`, then `with_owner_lines` swaps in the owner lines. Items 1 and 2 change `review`, `judge` and `earlier_findings`; item 4 changes `look_command`; item 5 changes `owner_lines`.
Same cause: items 1 and 2 share one cause, which is that the run keeps no list of earlier Fails and the prompt never says what the earlier Fails were; they stay separate commits in the same two files. Items 4 and 5 have other causes (a record path that a rerun overwrites, and measured values that only the reviewer reads) and other owners.
Single source: one finding-to-rule table beside `PROOF_KINDS` and the `DESIGN.md` tokens read by `ui_tokens.py`; the earlier-findings list and its recheck items come from one function in `look_records.py`.
Any edit of the prompt changes every image key, so each project's clean records stop carrying once after this release. The PR says so.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user asked on 2026-11-24 to make Hard Eng correct before the release; client pull requests cannot finish `look`.

## Acceptance + steps

- [x] A Fail that persists across two heads is listed as an earlier finding, never as fixed → `tests/test_look_carry.py::test_the_prompt_lists_an_earlier_fail_without_calling_it_fixed`.
- [x] A Fail line must name a frame of the run (`image-N.png`) and its element; an answer that names none is refused → `tests/test_look_answer.py::test_a_fail_line_must_name_the_frame_it_shows`.
- [x] The next run holds each earlier Fail as a numbered item, also when the image bytes did not change; the answer must say "still shown" or "gone" for each item with a frame, and "still shown" needs a Fail line for the rule → `tests/test_look_carry.py::test_each_earlier_fail_is_rechecked_one_by_one`.
- [x] A second run at the same head and inputs keeps the first clean or findings record, prints it again and starts no reviewer; a run that ended `not done`, and a run with other inputs, still run → `tests/test_look.py::test_a_second_run_at_the_same_head_keeps_the_first_verdict`.
- [x] A measure finding of a mapped rule (accent count, button groups, edges, secondary text) is a code Fail that the reviewer's Pass cannot overrule; a code Pass never replaces a reviewer Fail → `tests/test_look_proof_kinds.py::test_a_measure_finding_fails_its_judged_rule_in_code`.
- [x] A measured corner radius that no `DESIGN.md` token holds is a code Fail on Design system; a clamped radius, a missing token group, a token that is not a plain length, a text size outside the tokens, an `em` token, and an old record without the clamp field or the root size give no verdict → `tests/test_look_proof_kinds.py::test_a_radius_outside_the_tokens_leaves_design_system_to_the_reviewer`.
- [x] The Fail line of a reviewer that a code Fail replaces stays in the record and is rechecked in the next run → `tests/test_look_proof_kinds.py::test_a_reviewer_fail_that_a_code_fail_replaces_is_still_rechecked_next_run`.
- [x] 5 `look` runs on one frozen invented fixture report the rate of the same Fail set (the reviewer still judges, so 5 of 5 is not promised), each later run holds the earlier Fails as items, and a run after the fixture's faults are fixed is clean → N/A — real model runs, not a test; the records are in the `Real service:` line.

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
Evidence: 2026-11-25. Red first: the item 1 tests failed (14) on the code of item 2, the item 4 tests failed (3), the item 5 tests failed (8), each before its code. Then `uv run --frozen pytest -q tests/test_look.py tests/test_look_answer.py tests/test_look_carry.py tests/test_look_proof_kinds.py tests/test_look_px.py`: 119 passed. `check --plan-stage Complete --base origin/develop` at 8 of 9 groups passed in one run (the tests group timed out at 1800 s twice under a machine load of 250 to 390 from other work), and `--shard 1` to `--shard 6` of that check each passed. 293 tests of the other look readers passed.
E2E: N/A — no user journey of an installed project changes; the real `look` runs are in the `Real service:` line.
Real service: Passed — model reviewer (`look` ran Claude in each run) on two invented seed-shop pages, 3 frames each (390, 768, 1280 px), captured by `browser capture` in a real browser. Brief item 6 is met in form and not in full: the same Fail set in every run was reached on the clear-fault fixture and missed on the first one. Fixture v1 had faults that I did not seed (non-token colours, an 8 px row gap) and an are-you-sure text that the Undo rule reads in two ways; five runs on the final code at one commit gave the exact same Fail set 2 of 5 times (rate 0.4, records cdad22c5c6c1, 98cca7db32bf, 82fe8838e0c8, 55cd15c48820, 376b8a4eb4cc): the six rules that code decides, Messages and Mistake-proof failed in all 5, Undo in 4 and Spacing in 2. Earlier batches on earlier code: 4 of 5, then 2 of 5 where 2 runs were `not done` on a count note after the verdict. Fixture v2 holds only clear seeded faults: two filled buttons, a repeated status and helper text, a blaming error text, a 7 px radius outside the tokens. Five runs gave one identical Fail set 5 of 5 (rate 1.0, records 6e5ba73294ce, 19db6e0bcf5a, 7898acd2d25e, 1bad72c0d696, 90d53657651c): judged Fails Messages and Mistake-proof; code Fails Accessibility, Design system, Hierarchy, No clutter, Widths. Fix round 1 on v2 (record c696454983a2) answered all 5 items `gone` and found one new real fault that my fix had added (a banner that says an order needs a quantity beside an active Approve button); round 2 was clean (record 51188580cdf3, item `gone`). On v1, three fix rounds (records 73722992440f, f50e1f8cebf3, clean 1ea748b15840) each answered its items `gone` and found one new item (a `#ffffff` label, then a footer). So a set still can need more than one fix round when the reviewer sees a new borderline fault. These runs ran with this branch's earlier readers for a `Fix:` on a continuation line and a count note after the verdict, which the hotfix now owns. Codex gave no review (usage limit); every run was Claude. No fixture text or name belongs to a real project.
Retro: (1) the file-length gate refused `look.py` and `test_look.py` after the change, so the answer reader and its tests moved to `look_answer.py` and `tests/test_look_answer.py` → `tests/test_look_answer.py` holds them; (2) older plans named the moved tests, and the plan check refused them → each older plan now names the new file; (3) three older tests reran at one head and met the new refusal → they commit between runs. None to prevent beyond the push gates.
Delivery target: Merge
Delivery: Pending — `hard-eng` and `canary` pass on the PR to develop.
