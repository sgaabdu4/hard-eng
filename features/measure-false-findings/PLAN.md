# Stop the browser measure from reporting content that is not on the screen, repeat requests and nested text as faults

Status: Ready

## Outcome + scope

`browser measure` and `browser capture` stop four false findings. A control that the browser hides (a closed `details`, `hidden="until-found"`, `content-visibility: hidden`, `inert`) is not measured. When the page has an open modal, only the topmost modal is measured. A request that repeats an earlier finished request of the same part adds no fetch wave. Text inside an inline element nested in a line that already counts is not a second line. Non-goals: other measured rules, the limits in `LIMITS`, the vendored skill package copies, and a request key that reads or copies a body.

## Sources + coverage

Sources: the maintainer's request of 2026-11-27 with three faults and its added fourth fault (the page behind an open modal), read in full. An investigator reproduced the first three in headless Chrome against the real measure script.
Reviewer: N/A — four small faults, each with a stated fix and a stated set of cases that must keep failing.
Deliverables: None

- Closed `details` content is not measured, and the same markup open still is: In scope — A long label in a closed narrow `details` gives no `wrapped-label` and no `tap-size`; with `open` it gives both
- Other hidden states of the same cause: In scope — `hidden="until-found"`, an ancestor with `content-visibility: hidden`, a closed `dialog` and `inert` give no finding
- A repeat request adds no wave: In scope — 3 load requests with a poll repeated every 300 ms give no finding, for fetch and XHR, with no body, a string body and a `URLSearchParams` body
- A chain to one address with a new body each time still fails: In scope — 4 requests to one URL with a different string body each time, and with `FormData`, `Blob` and `Request` bodies, still give `fetch-waterfall`; the older chain tests still fail as before
- A polling page still splits parts at a press: In scope — a page that polls every 300 ms gives no finding for 3 presses that each post then load
- A nested inline element is not a second line: In scope — a 13 px `p` with an inner `strong` gives no `extra-text`; a body-size `p` with a small `small` and one more small line still does
- The page behind an open modal is not measured: In scope — a `showModal()` dialog and an `aria-modal` sheet over a page with a card heading stack give no finding from the page behind; a short control inside the modal still gives `tap-size`; a low-contrast line behind the modal gives no `contrast`
- A dialog that is not modal, a hidden `aria-modal` element and a page with no modal keep the page measured: In scope — each still gives its findings

## Repository context

Owners: `.hooks/ui_measure.py` owns the page script (`SHOWN_JS`, `MEASURE_SCRIPT`, `HOLD_SCRIPT`, `decoration_script`). `.hooks/browser.py` calls `measure_page` and needs no change.
Same cause: Content that the page does not show was measured. One rule, `shown`, now answers it for every caller of `visible` and for the direct icon check: it also requires `el.checkVisibility()` (no options, so below-the-fold `content-visibility: auto` stays measured), no `[inert]` ancestor, and, when the page has an open modal, that the element is inside the modal. `checkVisibility()` covers the closed `details`, `hidden="until-found"` and ancestor `content-visibility: hidden` cases; the `dialog` that is not open already had `display: none`; `inert` and the modal need their own checks. Axe contrast findings did not pass through `visible`, so the contrast skip in `decoration_script` also drops an element that `shown` rejects. The topmost modal is the last element in document order that is drawn and is a `dialog` that matches `:modal` or has `aria-modal="true"`. Waves: `__heRequests` is read only by the measure script. The quiet and reaction checks also ignore a request that repeats an earlier one, so a page that polls is not "never quiet". Searched `visible`, `shown`, `__heRequests`, `lineOf` and `ownText` in `.hooks` and `tests`; no other copy.
Single source: One `SHOWN_JS` text feeds the measure script and the contrast skip. The request key lives once in `HOLD_SCRIPT`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the coordinator merges through ship; the user's standing rule is to merge each task PR once its checks pass.

## Acceptance + steps

- [ ] A long label in a closed narrow `details` gives no `wrapped-label` and no `tap-size`; with `open` it keeps both → `tests/test_ui_hidden_content.py::test_a_control_the_browser_hides_is_not_measured`, `tests/test_ui_hidden_content.py::test_the_same_control_in_an_open_details_is_measured`
- [ ] Each other hidden state gives no finding → `tests/test_ui_hidden_content.py::test_a_control_the_browser_hides_is_not_measured`
- [ ] A repeat request adds no wave → `tests/test_ui_request_keys.py::test_a_poll_that_repeats_after_the_load_adds_no_wave`
- [ ] A chain with a new body each time still fails → `tests/test_ui_request_keys.py::test_a_chain_to_one_address_with_a_new_body_each_time_still_fails`
- [ ] A polling page still splits parts at a press → `tests/test_ui_request_keys.py::test_a_polling_page_still_measures_each_press_apart_from_the_load`
- [ ] A nested inline element is not a second line, and a small inline element in a body-size line still is → `tests/test_ui_variants.py::test_real_patterns_that_look_like_faults_are_not_findings`, `tests/test_ui_variants.py::test_real_variants_of_each_field_and_text_fault_are_found`
- [ ] Only the topmost open modal is measured, and a hidden or non-modal element does not change the page → `tests/test_ui_hidden_content.py::test_only_the_open_modal_is_measured`, `tests/test_ui_hidden_content.py::test_with_two_modals_only_the_last_one_in_the_page_is_measured`, `tests/test_ui_hidden_content.py::test_a_hidden_element_marked_modal_does_not_blank_the_page`, `tests/test_ui_hidden_content.py::test_the_page_behind_a_dialog_that_is_not_modal_is_still_measured`, `tests/test_ui_hidden_content.py::test_a_page_with_no_modal_is_measured_as_before`
- [ ] A low-contrast line behind a modal gives no `contrast` → `tests/test_ui_hidden_content.py::test_a_low_contrast_line_behind_a_modal_gives_no_finding`

## Baseline + execution

Result: Passed
Evidence: Before any edit, the new request, hidden content and variant tests ran on `origin/develop` code: 12 failed (the faults) and 54 passed (the near misses).
Execution: One builder, test first: the red tests, then `.hooks/ui_measure.py`.

## Risks + recovery

A modal is picked by document order, not by stacking order, so two modals that sit in a different order on the screen measure the later one. A page that sets `aria-modal="true"` on a drawn element, or `inert` on a part, turns off the measure for the rest of the page; the maintainer's rule is that such a page is not part of the screen. A repeat request adds no wave even when it belongs to a real chain with the same body; a chain must change its body or URL to count, as the tests with a changing body show. A request with a stream, `FormData`, `Blob` or a `Request` body always counts. Recovery: revert the commits.
Not checked: browsers other than the one that `agent-browser` starts; a modal that a page draws with its own focus trap and neither `:modal` nor `aria-modal`.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending

Delivery target: Merge
Delivery: Pending — CI, then the guarded merge into `develop` by the coordinator.
