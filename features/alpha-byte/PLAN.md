# Read a see-through colour's alpha as the browser stored it

Status: Complete

## Outcome + scope

A colour with 10 % opacity counts as a colour again, as it did before the accent opacity hotfix. A channel outside the colour range reads as the nearest value inside it. The accent rule, the limit of 2 and the set of colours the rules skip stay as they were. Non-goals: counting tints of one hue as one accent; any new limit.

## Sources + coverage

Sources: a review finding on the join of the accent opacity hotfix into `develop`, read in full, and the browser strings for out-of-range colours, probed in a real browser. `.hooks/ui_measure.py` (`COLOUR_JS`), read in full.
Reviewer: N/A — a one-function fix with stated cases that must keep failing.
Deliverables: None

- A 10 % tint of a third hue counts as an accent colour: In scope — A 10 % tint of a third hue counts as an accent colour
- A tint under 10 % stays skipped: In scope — A tint under 10 % stays skipped
- A channel outside the colour range reads inside it: In scope — A channel outside the colour range reads inside it

## Repository context

Owners: `.hooks/ui_measure.py` (`COLOUR_JS`, the `rgb` function) owns every colour read, so one fix covers `fill`, `opaque`, `hue`, contrast and the accent set.
Same cause: searched `rgb(` and `> 0.1` in `.hooks`; the callers `fill` and `opaque` keep a colour when its alpha is above 0.1, and no other file reads alpha. The canvas stored alpha as a byte, so a colour at 10 % read as 26/255 (0.102) and passed that test. The first hotfix took alpha from the string, so 10 % read as exactly 0.1 and failed it. `rgb` now rounds alpha to a byte on both paths. A probe showed that Chromium keeps out-of-range values, for example `color(srgb -0.604034 0.838685 -0.326954 / 0.7)` from a colour mix, so the string path clamps each channel to 0 to 255, as the canvas did.
Single source: the one `byte` helper inside `rgb`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] A 10 % tint of a third hue counts as an accent colour in `rgba()`, `oklab()` and `color(srgb)` forms → `tests/test_ui_accent_block.py::test_a_ten_percent_tint_of_a_third_hue_still_counts`
- [x] A tint under 10 % stays skipped → `tests/test_ui_accent_block.py::test_a_tint_under_ten_percent_stays_skipped`
- [x] A channel outside the colour range reads inside it → `tests/test_ui_accent_block.py::test_a_channel_outside_the_colour_range_reads_as_the_nearest_inside_it`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` at 7e366949, the three 10 % rows and the clamp row fail in a real browser (red commit `e357b800`, exit 1); the under-10 % rows pass there and keep passing.
Execution: Tests first, then the one function.

## Risks + recovery

A colour that the canvas cannot parse still reads as transparent, as before. The page script measures 4.55 to 4.60 ms per run on both versions (50 runs, two rounds), so the fix adds no time. Recovery: revert the commits.
Not checked: a real installed project page.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Red first: the three 10 % rows and the clamp row failed on `main` code at `e357b800`, then passed with the fix at `99e41790`; all 19 accent block tests pass in a real browser. The Ready check, the review and the Complete check run on the final head; the CI runs of the PR follow.
E2E: N/A — the proof is the real-browser capture tests above; no journey of an app is changed.
Real service: N/A — no outside service is called.
Retro: (1) Fault on the base branch, found by the review of the join of the first hotfix: a colour at exactly 10 % opacity stopped counting, because alpha was taken from the string and the canvas rounded it up to a byte before → `tests/test_ui_accent_block.py::test_a_ten_percent_tint_of_a_third_hue_still_counts`. (2) The first hotfix read out-of-range channels without the clamp that the canvas applied → `tests/test_ui_accent_block.py::test_a_channel_outside_the_colour_range_reads_as_the_nearest_inside_it`. (3) The first hotfix tested only the case it fixed; this fix adds the boundary rows on both sides of 10 % → `tests/test_ui_accent_block.py::test_a_tint_under_ten_percent_stays_skipped`.

Delivery target: Merge
Delivery: Pending — CI, the merge into `main`, then the update of the join of `main` into `develop`.
