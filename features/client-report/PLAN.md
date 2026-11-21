# Client report skill

Status: Complete

## Outcome + scope

A `client-report` skill makes a client change report as a PDF from one approved, tracked template, with live-site pictures, and a script refuses a report whose CSS differs from the template or whose text holds codes. Non-goals: a PDF library, a report generator script, changes to `browser`, `look` or the e2e skill.

## Sources + coverage

Sources: N/A — the request is the maintainer's queued note passed on by another thread (2026-11-20), including its late update; read in full.

## Repository context

Owners: new skill `.agents/skills/client-report/` (SKILL.md, two references, one starter asset, one script); picture commands stay with `.hooks/browser.py` and `.agents/skills/e2e/references/browser.md`; routing proof in `tests/test_skill_routing.py`; script gates in `hard-eng.gates.json`.
Same cause: N/A — new capability. The cause it prevents (an agent lost an agreed format after a context reset) had no earlier Hard Eng fix.
Single source: the red outline style, the 600 ms wait and the picture window size have one owner, `references/pictures.md`. The report CSS has one owner, the project's `docs/client-report/template.html`, and `assets/starter.html` is only the first copy. `browser --ring` draws a 3 px box; the 4 px outline with offset 4 px is not in `browser.py`, so the skill injects it with one `eval`. Decision: the hook is not changed, because the ring is the right tool for UI proof and the report needs a different mark.
Why not `diff` and `grep` alone: the check compares CSS after whitespace changes, reads only text a reader sees (not CSS, file names or tags), and refuses `style` attributes and stylesheet links. A plain `grep [A-Z][0-9]` also hits `MP4`, `A4` in CSS and names such as `B2.png`; the check uses word edges and skips those.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous. The launcher's brief fixes the design: own skill, template in the project, reuse `browser`, smallest check. Delivery is a draft PR to `develop`, no merge.
Decision: PDF by Chrome `--print-to-pdf` as the brief names it. The browser tool has a `pdf` step, but it was not tried. Page images: `pdftoppm` where it exists, else one `uv run --with pymupdf` command (run and proven on the sample). No new tool is added to `tool_setup.py`.

## Acceptance + steps

- [x] A report whose CSS differs from the template is refused → `tests/test_client_report.py::test_a_report_with_other_css_is_refused`.
- [x] A `style` attribute or a stylesheet link is refused → `tests/test_client_report.py::test_a_report_that_sets_style_in_a_tag_or_links_a_sheet_is_refused`.
- [x] A missing template is refused, not passed → `tests/test_client_report.py::test_a_missing_template_is_refused`.
- [x] Codes such as A1 in text or in a picture description are refused → `tests/test_client_report.py::test_codes_in_the_text_are_refused_with_their_place`.
- [x] The same CSS with other spacing, and words such as `MP4`, `Stage 1`, `4 December`, a CSS class `A1` and `B2.png`, pass → `tests/test_client_report.py::test_a_report_with_the_same_css_and_plain_words_is_accepted` and `::test_code_like_words_in_css_and_file_names_are_not_text`.
- [x] The command prints each problem and exits 1, or prints nothing and exits 0 → `tests/test_client_report.py::test_the_command_exits_with_the_problems`.
- [x] Sample requests pick `client-report`, and no two descriptions are too alike → `tests/test_skill_routing.py::test_every_request_picks_its_own_skill` and `::test_no_two_descriptions_are_too_alike`.
- [x] The skill links resolve and the files stay under the size limit → `tests/test_skill_links.py::test_distributed_skill_links_resolve`, `::test_distributed_skills_call_scripts_by_path_from_any_folder` and `::test_distributed_skills_fit_the_codex_skill_limit`.
- [x] The starter makes a readable multi-page PDF with no blank gap, cut picture or unreadable text → N/A — a page look is a human check; the sample run is under Verification.

## Baseline + execution

Result: Passed
Evidence: 2026-11-21, `origin/develop` 8c9b8b2a: no `client-report` skill existed; `tests/test_client_report.py` failed at import (`No module named 'check_report'`) before the script was written, then 7 passed.
Execution: One builder, this session. No subagent.

## Risks + recovery

N/A — a new optional skill, one script and one test file; a revert restores the earlier state.

## ux_reference

N/A — skill text, a script and a document template; no screen of this product changes. The sample report is shown under Verification.

## Verification

Result: Passed
Evidence: `tests/test_client_report.py` 12 passed; `tests/test_skill_routing.py` and `tests/test_skill_links.py` passed; static gates (format, lint, complexity, annotations, types, dead-code, biome, duplicates, security, secrets) passed. The full test run passed 7287 of 7289; one failure was this branch's (bytecode written into the skill folder by the test import, fixed with `sys.dont_write_bytecode`), and `tests/test_tidy.py::test_session_start_tidies_in_the_background_and_reports_at_the_next_start` failed once under a load average above 600 and passed when run alone.
Reader: not run by a second agent, because the builder brief forbids subagents. The independent Codex review read the skill and reference text twice (085604ae, b3ccaaf9); each finding on that text was fixed, including picture height and path quoting. A Reader pass by a second agent stays open as a stated limit.
Review: the independent review at 085604ae found nine items. Fixed: missing `override` decorators, changed selector and `media` attribute not seen, `rel` spelling, a code split by inline tags, picture height guidance, unquoted path, first-report wording, plan record. Not run as a separate item: none.
Review declined: spacing around `=`, `+` and a custom property colon in the approved CSS :: the report is a copy of the template and the skill says change text only, so nobody retypes the CSS; a refusal on a respaced copy only sends the agent back to the exact template, which is the aim.
Review declined: `title` text printed through `content: attr(title)` :: the starter has no such rule, and a changed CSS is refused first; no template prints titles.
Review declined: the 1,200 px picture limit :: a rough guide, and the page look step finds any picture that does not fit.
Review: the review at 7bc825cb found the test helper hid a checker crash and lost in-process coverage; the helper imports the checker in process again (no bytecode written) and the command test keeps the exit code check.
Review declined: the Reader pass :: the builder brief forbids subagents, so no second reader could run here; the maintainer's reader step stays open for the PR review.
E2E: Passed — sample report from invented data (an invented plant shop, a manager and a clerk role) on a local static page. Pictures: `browser measure` at width 560 with an injected 4 px outline, offset 4 px, no transition, 600 ms wait; the order list emails showed as `[hidden]`. Chrome printed a 4 page A4 PDF. Every page was rendered to an image (`pdftoppm`, and `pymupdf` as the fallback) and looked at. Page 1: title, stages box, correction box, first rows of the live table; no gap. Page 2: the table end row, then both before and after pictures side by side, red lines visible, captions under each; empty space under them because the next block (the clerk picture) did not fit, which is the intended no-cut behaviour. Page 3: clerk picture with its red line, the "no live copy" note, checks, not checked, our team list, first question box. Page 4: remaining questions, lists, undo steps; end half empty. No cut-off picture, no unreadable text, no heading alone at a page foot. The first run at width 800 gave tall pictures with blank space in them; width 560 fixed it.
Full check: Pending — CI on the draft PR; Verification is Passed only for the local checks listed here until CI passes. Local runs: every gate except the full test suite passed at head c046f500 in the pre-push check (the suite hit its 1800 s limit under a load average above 300); an earlier full suite run passed 7287 of 7289, and the two failures were fixed (one) or unproven (one, passed alone).
Real service: N/A — no outside service is called; the sample used a local static page by design.
Retro: (1) The full test run found a bytecode file that the new test wrote into a copied skill folder -> `sys.dont_write_bytecode` in the test; no rule change, the existing setup test caught it. (2) The review found the check weaker than its claim (selector and media changes passed) -> tests added first; None for the rules.

Delivery target: PR
Delivery: Pending — draft PR into develop; no merge until develop is open.
