# Capture refuses a document it cannot mask

Status: Complete

## Outcome + scope

`browser capture` and `browser measure` refuse a document that the page script cannot read to hide emails and phones, such as a PDF, and keep no image and no record; an HTML page behaves as before. Non-goals: a PDF proof route (page images, a measure record and the title and language of the file). It is a planned item and needs a PDF library, so it gets its own plan.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-24 for a client-blocking fault, and its follow-up that chose this narrow fix after a probe.

## Repository context

Owners: `.hooks/browser.py` (`shoot_page`) owns the capture and the measure of a page; `.hooks/browser.py` (`PAGE_SCRIPT`) owns the hiding of emails and phones.
Same cause: The viewer of Chrome draws a PDF in an embedded object outside the page, so `PAGE_SCRIPT` hides nothing in it and `FRAME_CHECK` counts `object` and `embed` elements inside the page only and finds none. Probe on `origin/main` (4b75d2c0) with a real PDF: capture kept images at all three widths, with the phone number of the file in clear. The readers that take a page image are `capture_page` and `measure`; both call `shoot_page`, so one check covers both. A same-origin frame that shows a PDF is the same cause: `watchFrame` marked any frame with a body as read, and `FRAME_CHECK` then counted nothing in it (found by the independent review); both now ask the kind of the frame document. `ui_proof.py` and `look` read only the records and images that `shoot_page` writes, so a refused document gives them nothing to read. No earlier fix of this cause exists.
Single source: `require_readable_document` in `.hooks/browser.py` owns the document kind: it asks the browser for `document.contentType` and never reads the URL text or the plan. `READABLE_KINDS` is the one list of kinds that the page script reads; the page script (`watchFrame`) and `FRAME_CHECK` take it from there for the document of each same-origin frame. Searched `.hooks`, `tests` and `.agents/skills` for another reader of the content type of a page: none (`check_attachment` in `ui_proof.py` reads the type of a GitHub attachment, a different subject).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to put client unblocking first and to release scoped client fixes to main through every normal gate; this fault blocks a client's merge of a PDF-only change. The coordinator chose the narrow fix on 2026-11-24 after the probe found no installed tool that gives the text of a PDF with positions, and ruled out a new dependency for a hotfix.

## Acceptance + steps

- [x] Capture of a URL whose response is `application/pdf` (served at a path with no `.pdf`) fails, names `application/pdf`, says no image was kept, and leaves no image and no record → `tests/test_browser.py::test_capture_keeps_no_image_of_a_pdf_it_cannot_mask`
- [x] Measure of an open session on a PDF fails the same way and writes nothing → `tests/test_browser.py::test_measure_keeps_no_image_of_a_pdf_in_an_open_session`
- [x] A PDF in a same-origin frame of an HTML page is replaced by the grey frame box and `FRAME_CHECK` counts no unread frame → `tests/test_browser.py::test_capture_replaces_a_pdf_in_a_same_origin_frame`
- [x] An HTML page is captured and measured as before: same records, same findings, same hiding → `tests/test_browser.py::test_capture_draws_boxes_at_each_width`, `tests/test_browser.py::test_measure_records_an_open_session_state`, `tests/test_browser.py::test_capture_places_fixed_bars_once_at_their_edge`
- [x] A failing check after the screenshot still keeps no image → `tests/test_browser.py::test_capture_keeps_no_image_when_the_frame_check_fails`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` (4b75d2c0) the new capture test fails (`assert 0 == 1`: capture of the PDF succeeds). The failing tests are commit fd3b1094, before the fix. At the final head the Complete check passed every static gate. Its tests gate hit its 1800 s limit three times, because a load average near 300 from other work slowed the Mac, so shard 1 of 6 ran alone and passed (1201 tests); CI runs all six shards. The five test files of the capture, the look and the local UI proof, which hold every changed or new test, ran together on the final code and passed (96 tests), including the rewritten frame test. The full suite passed on earlier heads: 7752 tests in the Ready check, and 7753 in a Complete run before the last test helper change.
Execution: One builder in a hotfix worktree from `main`; the failing tests are committed before the fix.

## Risks + recovery

A frame whose document is not HTML, XHTML or plain text is now greyed like a frame from another site. A capture of a document that is not HTML, XHTML or plain text now fails, where it kept an image before: a PDF, an image file, JSON or XML opened as the page. Those images could show personal data that the page script cannot reach for a PDF or an image, and none of the other kinds is a screen to prove. Recovery: revert the commit. The PDF proof route (page images rendered from the file, a measure record from the file) stays open; a PDF-only change still cannot pass a visible-change proof until it lands.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The three new tests fail without the fix and pass with it; the frame test was run once with the fix reverted (the frame stays an `IFRAME`). The browser, look and local UI test files pass with the fix. At the final head the Complete check passed every static gate. Its tests gate hit its 1800 s limit three times, because a load average near 300 from other work slowed the Mac, so shard 1 of 6 ran alone and passed (1201 tests); CI runs all six shards. The five test files of the capture, the look and the local UI proof, which hold every changed or new test, ran together on the final code and passed (96 tests), including the rewritten frame test. The full suite passed on earlier heads: 7752 tests in the Ready check, and 7753 in a Complete run before the last test helper change. In the frame test the real Chrome reports a kind outside `READABLE_KINDS` for the document of a same-origin PDF frame, as the fix greys that frame. Real run with agent-browser 0.43.0 and Chrome 158, from an invented two-page PDF and an invented HTML page served by a local test server: `browser capture` of the PDF exits 1 with `the document is application/pdf, which capture cannot read to hide emails and phones, so no image was kept` and writes no file; `browser measure` on an open session of the PDF prints the same and writes no file; `browser capture` of the HTML page exits 0, writes three images, and the record of the 390 px image holds `findings: []`, `route: /page` and `width: 390`. Before the fix the same PDF capture kept three images whose page showed the phone number in clear.
E2E: N/A — the change is a check inside the capture command, proved by the tests above, which drive the real browser tool.
Real service: Passed — agent-browser with Chrome: the changed capture and measure ran one time against a real PDF and one HTML page served by a local test server; the PDF was refused with no file, the HTML page kept its records.
Retro: Review finding: a PDF in a same-origin frame kept its emails and phones in clear, as `watchFrame` and `FRAME_CHECK` trusted any frame with a body → `tests/test_browser.py::test_capture_replaces_a_pdf_in_a_same_origin_frame` (it fails without the fix: the frame stays an `IFRAME`). Escaped bug: a PDF page image with emails and phones in clear, because `FRAME_CHECK` counts embeds inside the page and the viewer sits outside it → `tests/test_browser.py::test_capture_keeps_no_image_of_a_pdf_it_cannot_mask`, `tests/test_browser.py::test_measure_keeps_no_image_of_a_pdf_in_an_open_session` (committed red first); the gate that should have caught it was the capture tests, which served HTML only. Failed check: two fake-tool tests failed after the fix because the fake did not answer the content type → `tests/test_browser.py::test_capture_keeps_no_image_when_the_frame_check_fails` now answers it. Hard Eng fault: a change that only edits a generated PDF still cannot pass a visible-change proof → the planned PDF proof route, which needs a PDF library and its own plan.

Delivery target: PR
Delivery: Pending — required remote proof.
