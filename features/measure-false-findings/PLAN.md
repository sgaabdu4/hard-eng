# Stop the browser measure from reporting content that is not on the screen, repeat requests and nested text as faults

Status: Complete

## Outcome + scope

`browser measure` and `browser capture` stop four false findings. A control that the browser hides (a closed `details`, `hidden="until-found"`, `content-visibility: hidden`, `inert`) is not measured. When the page has an open modal, only the topmost modal is measured. A request that repeats an earlier finished request of the same part adds no fetch wave. Text inside an inline element nested in a line that already counts is not a second line. Non-goals: other measured rules, the limits in `LIMITS`, the vendored skill package copies, and a request key that reads or copies a body.

## Sources + coverage

Sources: the maintainer's request of 2026-11-27 with three faults and its added fourth fault (the page behind an open modal), read in full. An investigator reproduced the first three in headless Chrome against the real measure script.
Reviewer: N/A — four small faults, each with a stated fix and a stated set of cases that must keep failing.
Deliverables: None

- Closed `details` content is not measured, and the same markup open still is: In scope — A long label in a closed narrow `details` gives no `wrapped-label` and no `tap-size`; with `open` it keeps both
- Other hidden states of the same cause: In scope — Each other hidden state gives no finding
- A repeat request adds no wave: In scope — A repeat request adds no wave
- A chain to one address with a new body each time still fails: In scope — A chain with a new body each time still fails
- A polling page still splits parts at a press, and a poll that carries on into a press adds no wave to it: In scope — A polling page still splits parts at a press; a poll that carries on into a press adds no wave to it
- A tab opened again after another tab is its own step: In scope — A tab opened again after another tab is its own step
- A nested inline element is not a second line: In scope — A nested inline element is not a second line, and a small inline element in a body-size line still is
- The page behind an open modal is not measured: In scope — Only the topmost open modal is measured, and a hidden or non-modal element does not change the page
- A modal wrapper with no box of its own still covers the page: In scope — A modal wrapper with no box of its own still covers the page
- Axe findings behind a modal are dropped: In scope — A low-contrast line and an unlabelled field behind a modal give no finding
- A control that only screen readers reach is still reported: In scope — A control that only screen readers reach is still reported
- A closed modal does not blank the page: In scope — A closed modal that is collapsed, clipped or faded does not blank the page
- A click that opens a polling view is its own step: In scope — A click that opens a polling view is its own step
- Two requests at once are no poll: In scope — Two requests at once for one address are no poll, and a slow poll does not keep the page from going quiet

## Repository context

Owners: `.hooks/ui_measure.py` owns the page script (`SHOWN_JS`, `MEASURE_SCRIPT`, `HOLD_SCRIPT`, `behind_script`). `.hooks/browser.py` calls `measure_page`, which now drops each axe finding on an element that `shown` rejects.
Same cause: Content that the page does not show was measured. One rule, `shown`, now answers it for every caller of `visible` and for the direct icon check: it also requires `el.checkVisibility()` with its opacity option (so an element under an ancestor with opacity 0 is not measured, and below-the-fold `content-visibility: auto` stays measured), no `[inert]` ancestor, and, when the page has an open modal, that the element is inside the modal. `checkVisibility()` covers the closed `details`, `hidden="until-found"` and ancestor `content-visibility: hidden` cases; the `dialog` that is not open already had `display: none`; `inert` and the modal need their own checks. Axe findings (contrast, label, link size and the rest) did not pass through `visible`, so `measure_page` drops each axe finding whose element is inside `[inert]` or outside the open modal; a visually hidden control on a page with no modal is still reported, as before. The topmost modal is the last element in document order that is a `dialog` that matches `:modal` or has `aria-modal="true"`, and is open: it is not hidden, inert or faded out (the element or an ancestor has opacity 0), and it is drawn or, when it does not clip its content, one of its descendants is drawn. So a wrapper with no box of its own and fixed children counts, and a collapsed, clipped or faded closed modal does not. Waves: `__heRequests` is read only by the measure script. A key is a poll when a request repeats an earlier one that had already finished, with no recorded step between them; two requests at the same time for one address are no poll. The quiet check ignores every request of a poll, and the reaction check ignores each request of a poll except its first, so a click that opens a polling view still starts its own part, and a page that polls is not "never quiet", and a poll that continues into a later part adds no wave there. A key with a step between each pair of requests, such as a tab opened again, is no poll. An inline-level element (`inline`, `inline-block`, `inline-flex`) nested in a counted line is not a second line. Searched `visible`, `shown`, `__heRequests`, `lineOf` and `ownText` in `.hooks` and `tests`; no other copy.
Single source: One `SHOWN_JS` text feeds the measure script and the axe filter. The request key lives once in `HOLD_SCRIPT`.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the coordinator merges through ship; the user's standing rule is to merge each task PR once its checks pass.

## Acceptance + steps

- [x] A long label in a closed narrow `details` gives no `wrapped-label` and no `tap-size`; with `open` it keeps both → `tests/test_ui_hidden_content.py::test_a_control_the_browser_hides_is_not_measured`, `tests/test_ui_hidden_content.py::test_the_same_control_in_an_open_details_is_measured`
- [x] Each other hidden state gives no finding → `tests/test_ui_hidden_content.py::test_a_control_the_browser_hides_is_not_measured`
- [x] A repeat request adds no wave → `tests/test_ui_request_keys.py::test_a_poll_that_repeats_after_the_load_adds_no_wave`
- [x] A chain with a new body each time still fails → `tests/test_ui_request_keys.py::test_a_chain_to_one_address_with_a_new_body_each_time_still_fails`
- [x] A polling page still splits parts at a press; a poll that carries on into a press adds no wave to it → `tests/test_ui_request_keys.py::test_a_polling_page_still_measures_each_press_apart_from_the_load`, `tests/test_ui_request_keys.py::test_a_poll_that_carries_on_into_a_press_adds_no_wave_to_it`
- [x] A tab opened again after another tab is its own step → `tests/test_ui_request_keys.py::test_a_tab_opened_again_after_another_tab_is_measured_as_its_own_step`
- [x] A nested inline element is not a second line, and a small inline element in a body-size line still is → `tests/test_ui_variants.py::test_real_patterns_that_look_like_faults_are_not_findings`, `tests/test_ui_variants.py::test_real_variants_of_each_field_and_text_fault_are_found`
- [x] Only the topmost open modal is measured, and a hidden or non-modal element does not change the page → `tests/test_ui_hidden_content.py::test_only_the_open_modal_is_measured`, `tests/test_ui_hidden_content.py::test_with_two_modals_only_the_last_one_in_the_page_is_measured`, `tests/test_ui_hidden_content.py::test_a_hidden_element_marked_modal_does_not_blank_the_page`, `tests/test_ui_hidden_content.py::test_the_page_behind_a_dialog_that_is_not_modal_is_still_measured`, `tests/test_ui_hidden_content.py::test_a_page_with_no_modal_is_measured_as_before`
- [x] A modal wrapper with no box of its own still covers the page → `tests/test_ui_hidden_content.py::test_a_modal_wrapper_with_no_box_of_its_own_still_covers_the_page`
- [x] A low-contrast line and an unlabelled field behind a modal give no finding → `tests/test_ui_hidden_content.py::test_a_low_contrast_line_behind_a_modal_gives_no_finding`, `tests/test_ui_hidden_content.py::test_an_unlabelled_field_behind_a_modal_gives_no_finding`
- [x] A control that only screen readers reach is still reported → `tests/test_ui_hidden_content.py::test_an_unlabelled_field_that_only_screen_readers_reach_is_still_reported`
- [x] A closed modal that is collapsed, clipped or faded does not blank the page → `tests/test_ui_hidden_content.py::test_a_closed_modal_that_is_collapsed_or_faded_does_not_blank_the_page`
- [x] A click that opens a polling view is its own step → `tests/test_ui_request_keys.py::test_a_click_that_opens_a_polling_view_is_measured_as_its_own_step`
- [x] Two requests at once for one address are no poll, and a slow poll does not keep the page from going quiet → `tests/test_ui_request_keys.py::test_two_requests_at_once_for_one_address_are_no_poll`, `tests/test_ui_request_keys.py::test_a_slow_poll_does_not_keep_the_page_from_going_quiet`

## Baseline + execution

Result: Passed
Evidence: Before any edit, the new request, hidden content and variant tests ran on `origin/develop` code: 12 failed (the faults) and 54 passed (the near misses).
Execution: One builder, test first: the red tests, then `.hooks/ui_measure.py`.

## Risks + recovery

A modal is picked by document order, not by stacking order, so two modals that sit in a different order on the screen measure the later one. A page that sets `aria-modal="true"` on a drawn element, or `inert` on a part, turns off the measure for the rest of the page; the maintainer's rule is that such a page is not part of the screen. A repeat request adds no wave even when it belongs to a real chain with the same body; a chain must change its body or URL to count, as the tests with a changing body show. A poll that never has a recorded step between two of its requests is background in every part; a poll with one request in each part and a step before each counts in each part. A request with a stream, `FormData`, `Blob` or a `Request` body always counts. Recovery: revert the commits.
Not checked: browsers other than the one that `agent-browser` starts; a modal that a page draws with its own focus trap and neither `:modal` nor `aria-modal`.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Red first: on `origin/develop` code the first set of new tests gave 12 failed (the faults) and 54 passed (the near misses); the tests for each later review finding were red on the code before its fix (6 of 6, then 3 of 3 failed). Focused after the last change: 251 passed across `tests/test_ui_request_keys.py`, `tests/test_ui_hidden_content.py`, `tests/test_ui_variants.py`, `tests/test_ui_audit_guards.py`, `tests/test_browser.py`, `tests/test_ui_pages.py`, `tests/test_ui_accent_block.py`, `tests/test_browser_documents.py`, `tests/test_browser_init_scripts.py` and `tests/test_ui_gap_and_init_script.py`, which include the older `CHAIN`, `GAP_CHAIN` and `XHR_CHAIN` tests unchanged. Static gates (ruff format, lint, complexity, annotations, pyrefly, vulture) and the semgrep security scan passed; `hot-paths` gave 0 findings. Mutation checks: with the body left out of the request key, the two string-body chain tests fail; with the carried-poll rule removed, the carry test fails; with the first poll request kept in the quiet check, the slow poll test fails. Full check: the `check --plan-stage Complete` run on the final head and the CI runs of the PR.
Reviews: four `challenge` rounds. Round 1 found a repeat that broke a tab opened again, a poll carried into a press, axe findings behind a modal, a modal wrapper with no box, a nested `inline-flex` line and plan lines; round 2 found an axe filter that was too wide, a collapsed closed modal, a faded closed modal, two requests at once read as a poll and a slow poll; round 3 found an ancestor with opacity 0 and a click that opens a polling view. Each is fixed with a red test first. Round 4 on 96ee121a was clean.
E2E: N/A — the proof is the real-browser tests above, which drive `browser.browser_command` and a real page; no journey of an app is changed.
Real service: N/A — no outside service is called; the test pages are served from a local folder.
Retro: (1) Fault on the base branch, content the browser hides and the page behind an open modal were measured → `tests/test_ui_hidden_content.py::test_a_control_the_browser_hides_is_not_measured`. (2) Fault on the base branch, a repeated poll counted as a fetch wave → `tests/test_ui_request_keys.py::test_a_poll_that_repeats_after_the_load_adds_no_wave`. (3) Fault on the base branch, a nested inline element counted as a second line → `tests/test_ui_variants.py::test_real_patterns_that_look_like_faults_are_not_findings`. (4) The first axe filter dropped real findings on controls that only screen readers reach → `tests/test_ui_hidden_content.py::test_an_unlabelled_field_that_only_screen_readers_reach_is_still_reported`.

Delivery target: Merge
Delivery: Pending — CI, then the guarded merge into `develop` by the coordinator.
