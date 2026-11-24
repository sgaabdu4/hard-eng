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
- Every colour reads as the old canvas reader read it: In scope — Every colour reads as the old canvas reader read it

## Repository context

Owners: `.hooks/ui_measure.py` (`COLOUR_JS`, the `rgb` function) owns every colour read, so one fix covers `fill`, `opaque`, `hue`, contrast and the accent set.
Same cause: searched `rgb(` and `[3]` in `.hooks`; only `ui_measure.py` reads colours, through the one `rgb`. Each place that compares alpha or channels, with the check of `tests/test_ui_colour_reader.py::test_every_colour_reads_as_the_canvas_reader_read_it_before_the_string_reader` that covers it: (1) `fill` in the decoration script, alpha above 0.1 (`threshold` check); (2) `apart` in the decoration script, the luminance of the colour and of the layer behind it, which reads channels (`channels` check); (3) `opaque`, alpha above 0.1 (`threshold` check), used by (4) `competing-buttons`, which also takes the hue from channels (`channels` check), (5) the `accent-colours` set, which keys each colour by its channels (`channels` check) and also uses `opaque` and the hue, (6) `framed` in the shared-edge rule, and (7) `chip` in the extra-text rule, both through `opaque` (`threshold` check). The canvas stored alpha as a byte, so a colour at 10 % read as 26/255 (0.102) and passed the alpha test. The first hotfix took alpha from the string, so 10 % read as exactly 0.1 and failed it. `rgb` now rounds alpha to a byte on both paths. A probe showed that Chromium keeps out-of-range values, for example `color(srgb -0.604034 0.838685 -0.326954 / 0.7)` from a colour mix, so the string path clamps each channel to 0 to 255, as the canvas did. The sameness test runs the reader of `fa99bf3c` and the new reader in one real browser on 10 opaque colours (named, hex, `rgb()`, `color(srgb)`, out of range, `oklab`, `oklch`, `hsl`, `display-p3`, a colour mix) and 7 hex and 63 see-through colours at alpha 0.05, 0.09, 0.1, 0.11, 0.5, 0.7 and 0.99: the channels equal the channels of the colour's opaque twin, the alpha byte equals the colour's own alpha byte (the old canvas differed by one in `color(srgb 1.2 -0.1 0.5 / 0.7)`), and the answer to `> 0.1` equals the old answer for every colour.
Single source: the one `byte` helper inside `rgb`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] A 10 % tint of a third hue counts as an accent colour in `rgba()`, `oklab()` and `color(srgb)` forms → `tests/test_ui_accent_block.py::test_a_tint_of_a_third_hue_counts_from_ten_percent_up`
- [x] A tint under 10 % stays skipped → `tests/test_ui_accent_block.py::test_a_tint_of_a_third_hue_counts_from_ten_percent_up`
- [x] Every colour reads as the old canvas reader read it: channels of the opaque twin, own alpha byte, same answer to `> 0.1` → `tests/test_ui_colour_reader.py::test_every_colour_reads_as_the_canvas_reader_read_it_before_the_string_reader`
- [x] A channel outside the colour range reads inside it → `tests/test_ui_accent_block.py::test_a_channel_outside_the_colour_range_reads_as_the_nearest_inside_it`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` at 7e366949, the three 10 % rows and the clamp row fail in a real browser (red commit `e357b800`, exit 1); the under-10 % rows pass there and keep passing. The sameness test also fails with the reader of `7e366949` (the 10 % colour and the out-of-range colour differ from the old reader) and passes with the fix.
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
Retro: (1) Fault on the base branch, found by the review of the join of the first hotfix: a colour at exactly 10 % opacity stopped counting, because alpha was taken from the string and the canvas rounded it up to a byte before → `tests/test_ui_accent_block.py::test_a_tint_of_a_third_hue_counts_from_ten_percent_up`. (2) The first hotfix read out-of-range channels without the clamp that the canvas applied → `tests/test_ui_accent_block.py::test_a_channel_outside_the_colour_range_reads_as_the_nearest_inside_it`. (3) The first hotfix tested only the case it fixed; this fix adds the boundary rows on both sides of 10 % → `tests/test_ui_accent_block.py::test_a_tint_of_a_third_hue_counts_from_ten_percent_up`.

Delivery target: Merge
Delivery: Pending — CI, the merge into `main`, then the update of the join of `main` into `develop`.
