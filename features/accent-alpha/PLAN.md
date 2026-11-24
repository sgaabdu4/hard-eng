# Count one ink at two opacities as one accent colour

Status: Ready

## Outcome + scope

The `accent-colours` rule counts one text ink drawn at full strength and at a lower strength as one colour, so a page no longer goes over the limit of 2 because of the browser's rounding. The limit and the rule's meaning stay the same. Non-goals: a new limit; a change to which colours the rule skips; counting tints of one hue as one accent (a separate planned change).

## Sources + coverage

Sources: the maintainer's request of 2026-11-24 to fix this fault as a hotfix, read in full. `.hooks/ui_measure.py` (`COLOUR_JS`, the `accent-colours` block), read in full.
Reviewer: N/A — a one-function fix with a stated set of cases that must keep failing.
Deliverables: None

- One ink at full and at 70 % strength counts as one colour: In scope — One ink at full and at 70 % strength counts as one colour
- One ink in two colour forms counts as one colour: In scope — One ink in two colour forms counts as one colour
- Two truly different inks still count as two colours: In scope — Two truly different inks still count as two colours

## Repository context

Owners: `.hooks/ui_measure.py` (`COLOUR_JS`, the `rgb` function) owns every colour read of the page script and of the decoration script.
Same cause: searched `rgb(` in `.hooks`; the `fill`, `lum`, `apart`, `opaque`, `hue` and `accent-colours` readers all call the one `rgb`, so one fix covers them. The canvas stored a translucent colour with premultiplied channels, so a read-back channel was off by one or two (for example `rgba(160, 59, 38, 0.7)` read back as `160, 58, 38`).
Single source: the browser's computed colour string is the exact value; `rgb` parses `rgb()`, `rgba()` and `color(srgb ...)` from it. Other forms (`oklab`, `oklch`, `color(display-p3 ...)`) keep their own form in the computed string, so `rgb` reads the alpha from the string and draws the colour without its alpha on the canvas, so the canvas has no premultiply loss.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user asked on 2026-11-23 to fix every Hard Eng fault found in the rollout; standing rule: merge each task PR once its checks pass.

## Acceptance + steps

- [x] One ink at full and at 70 % strength counts as one colour → `tests/test_ui_accent_block.py::test_one_ink_at_two_strengths_counts_as_one_colour`
- [x] One ink in two colour forms counts as one colour → `tests/test_ui_accent_block.py::test_one_ink_in_two_colour_forms_counts_as_one_colour`
- [x] A different ink in another colour form still counts → `tests/test_ui_accent_block.py::test_a_different_ink_in_another_colour_form_still_counts_as_a_colour`
- [x] Two truly different inks still count as two colours → `tests/test_ui_accent_block.py::test_two_different_inks_still_count_as_two_colours`
- [x] The existing accent cases still count as before → `tests/test_ui_accent_block.py::test_accent_colours_around_a_button_group_still_count`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` at fa99bf3c, the new test fails in a real browser at all three widths with one `accent-colours` finding (red commit `1edc88d3`, exit 1); the page script measured 3 colours for the one ink and one accent.
Execution: Test first, then the one function.

## Risks + recovery

A colour in a wide space such as `color(display-p3 ...)` is converted to 8-bit sRGB by the canvas, so two forms of one colour could still differ by one in a channel at a rounding edge; the tests cover the oklab form of one ink against its `rgb()` and `color(srgb ...)` forms. The page script measures about 4.6 to 4.7 ms per run after the fix against 4.9 to 5.5 ms before (50 runs each, two rounds), so the fix adds no time. Recovery: revert the commits.
Not checked: a real installed project page.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending the Ready check and the review.
E2E: N/A — the proof is the real-browser capture tests above; no journey of an app is changed.
Real service: N/A — no outside service is called.
Retro: Pending

Delivery target: Merge
Delivery: Pending — CI, the merge into `main`, then the join of `main` into `develop`.
