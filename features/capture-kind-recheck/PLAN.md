# Capture asks the document kind again around the screenshot, and the press test stops guessing time

Status: Complete

## Outcome + scope

`browser capture` and `browser measure` ask the browser for the document kind again right before and right after each screenshot. A page that turns into a PDF after the first check keeps no image and no record. The press test of the fetch-wave measure waits on the page, not on a fixed time, so it gives the same result on a slow machine. Non-goals: a PDF proof route, and any change to the fetch-wave limits or the measure itself.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's follow-up of 2026-11-25 after the join of the PDF refusal hotfix.

## Repository context

Owners: `require_readable_document` in `.hooks/browser.py` owns the document kind; `shoot_page` owns the order of the checks around the screenshot. `tests/test_ui_audit_guards.py` owns the fetch-wave tests.
Same cause: the review of the join found that `shoot_page` read the kind once, before the measure, so a client-side redirect to a PDF between that check and the screenshot kept an unmasked image; the earlier plan (`features/pdf-proof/PLAN.md`) declined it as far-fetched, and the coordinator ruled that a protected boundary needs the fix. The same call now runs before and after the screenshot, beside the two `unread_frames` calls. The flaky test has one cause in four tests: each one waited a fixed 0.8 s or 2 s on the clock of the test, while the measure compares the action time with the page's own fetch times. When the page handler ran later than the click command returned, the previous press was less than 500 ms quiet and its waves joined the next press. All four now wait on the page (`settled`).
Single source: `require_readable_document` stays the one owner of the kind and `READABLE_KINDS` the one list; no other reader was added. In the tests, `settled` and `press_clicks` in `tests/test_ui_audit_guards.py` are the one wait; the four copies of `time.sleep` are gone, and `PRESS` records its own start time so the test never uses the time of the click command.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to make Hard Eng correct before the release; the coordinator set this follow-up on 2026-11-25.

## Acceptance + steps

- [x] A page that is HTML at the first check and a PDF before the shoot step keeps no image and no record, and the message names `application/pdf` → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_turns_into_a_pdf[before]`
- [x] A page that turns into a PDF while the screenshot is taken keeps no image and no record → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_turns_into_a_pdf[during]`
- [x] An HTML page is captured as before → `tests/test_browser.py::test_capture_draws_boxes_at_each_width`, `tests/test_browser.py::test_measure_records_an_open_session_state`
- [x] A press whose page answers 600 ms after the click is still measured apart from the load → `tests/test_ui_audit_guards.py::test_each_press_is_measured_apart_from_the_load_when_the_page_answers_late`
- [x] The press test no longer depends on time: 30 runs in a row of the four timing tests pass → `tests/test_ui_audit_guards.py::test_each_press_is_measured_apart_from_the_load`, `tests/test_ui_audit_guards.py::test_a_press_that_starts_a_four_wave_chain_fails_at_that_press`, `tests/test_ui_audit_guards.py::test_a_step_in_a_quiet_gap_that_starts_no_fetch_does_not_split_a_load_waterfall`

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (4b8f3a45) the two kind tests fail (`assert 0 == 1`: capture keeps images) and the late-answer test fails with the CI message `fetch-waterfall, click 1`. The red tests are committed before each fix (commits 9484b715 and 6c7a2613). The `Review declined:` line about this finding in `features/pdf-proof/PLAN.md` is closed by this change. The existing guard and browser tests pass.
Execution: One builder in a worktree off `origin/develop`.

## Risks + recovery

Each screenshot now costs two more `eval` calls of the browser, which are a few milliseconds each. The press tests now wait in the page for a quiet time of 600 ms after the last fetch, so each takes about as long as before on a fast machine and longer only when the page is slow. Recovery: revert the commits.

## ux_reference

N/A — hook code and tests; no visible UI.

## Verification

Result: Passed
Evidence: The two kind tests fail without the fix and pass with it. The late-answer test fails with the CI message before the test change and passes after it. The four timing tests ran 30 times, six at a time on a loaded Mac, and passed every time; the old flake did not show on this Mac in 22 runs, so the red proof is the late-answer test. The browser, document and guard test files pass. Real run with agent-browser and Chrome from an invented server: capture of a PDF route exits 1 with the kind message and writes no file; capture of an HTML page exits 0 and its record has `findings: []`. The Complete check result is below.
E2E: N/A — the change is a check inside the capture command and a test change, proved by the real-browser tests above.
Real service: Passed — agent-browser with Chrome: capture ran one time against a PDF route and one HTML page of a local test server; the PDF was refused with no file and the HTML page kept its records.
Retro: Review finding carried over: a page that becomes a PDF after the first check → `tests/test_browser_documents.py::test_capture_keeps_no_image_of_a_page_that_turns_into_a_pdf`. Flaky test on CI: the fixed waits → `tests/test_ui_audit_guards.py::test_each_press_is_measured_apart_from_the_load_when_the_page_answers_late` (it fails with the old waits) and the 30 runs. Ran too late: the flake showed only on CI because the Mac never starved the page; the late-answer test now makes it show on any machine.

Delivery target: Merge
Delivery: Pending — required remote proof.
