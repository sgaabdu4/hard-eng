# Capture refuses a document it cannot mask

Status: Ready

## Outcome + scope

`browser capture` and `browser measure` refuse a document that the page script cannot read to hide emails and phones, such as a PDF, and keep no image and no record; an HTML page behaves as before. Non-goals: a PDF proof route (page images, a measure record and the title and language of the file). It is a planned item and needs a PDF library, so it gets its own plan.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-24 for a client-blocking fault, and its follow-up that chose this narrow fix after a probe.

## Repository context

Owners: `.hooks/browser.py` (`shoot_page`) owns the capture and the measure of a page; `.hooks/browser.py` (`PAGE_SCRIPT`) owns the hiding of emails and phones.
Same cause: The viewer of Chrome draws a PDF in an embedded object outside the page, so `PAGE_SCRIPT` hides nothing in it and `FRAME_CHECK` counts `object` and `embed` elements inside the page only and finds none. Probe on `origin/main` (4b75d2c0) with a real PDF: capture kept images at all three widths, with the phone number of the file in clear. The readers that take a page image are `capture_page` and `measure`; both call `shoot_page`, so one check covers both. `ui_proof.py` and `look` read only the records and images that `shoot_page` writes, so a refused document gives them nothing to read. No earlier fix of this cause exists.
Single source: `require_readable_document` in `.hooks/browser.py` owns the document kind: it asks the browser for `document.contentType` and never reads the URL text or the plan. `READABLE_KINDS` is the one list of kinds that the page script reads. Searched `.hooks`, `tests` and `.agents/skills` for another reader of the content type of a page: none (`check_attachment` in `ui_proof.py` reads the type of a GitHub attachment, a different subject).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to put client unblocking first and to release scoped client fixes to main through every normal gate; this fault blocks a client's merge of a PDF-only change. The coordinator chose the narrow fix on 2026-11-24 after the probe found no installed tool that gives the text of a PDF with positions, and ruled out a new dependency for a hotfix.

## Acceptance + steps

- [ ] Capture of a URL whose response is `application/pdf` (served at a path with no `.pdf`) fails, names `application/pdf`, says no image was kept, and leaves no image and no record → `tests/test_browser.py::test_capture_keeps_no_image_of_a_pdf_it_cannot_mask`
- [ ] Measure of an open session on a PDF fails the same way and writes nothing → `tests/test_browser.py::test_measure_keeps_no_image_of_a_pdf_in_an_open_session`
- [ ] An HTML page is captured and measured as before: same records, same findings, same hiding → `tests/test_browser.py::test_capture_draws_boxes_at_each_width`, `tests/test_browser.py::test_measure_records_an_open_session_state`, `tests/test_browser.py::test_capture_places_fixed_bars_once_at_their_edge`
- [ ] A failing check after the screenshot still keeps no image → `tests/test_browser.py::test_capture_keeps_no_image_when_the_frame_check_fails`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` (4b75d2c0) the new capture test fails (`assert 0 == 1`: capture of the PDF succeeds and keeps three images). The existing browser, look and local UI tests pass on the branch with the fix: 95 tests, 93 first run, then the two that use a fake browser tool pass after the fake answers the content type.
Execution: One builder in a hotfix worktree from `main`; the failing tests are committed before the fix.

## Risks + recovery

A capture of a document that is not HTML, XHTML or plain text now fails, where it kept an image before: a PDF, an image file, JSON or XML opened as the page. Those images could show personal data that the page script cannot reach for a PDF or an image, and none of the other kinds is a screen to prove. Recovery: revert the commit. The PDF proof route (page images rendered from the file, a measure record from the file) stays open; a PDF-only change still cannot pass a visible-change proof until it lands.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Pending
Evidence: Pending the final gate.
E2E: N/A — the change is a check inside the capture command, proved by the tests above, which drive the real browser tool.
Real service: Required — agent-browser with Chrome: the changed capture ran one time against a real PDF and one HTML page served by a local test server.
Retro: Required on Complete plans.

Delivery target: PR
Delivery: Pending — required remote proof.
