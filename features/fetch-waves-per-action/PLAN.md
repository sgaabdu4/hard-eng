# Count fetch waves for each input step, and keep a tab bar's accent colours to its own row

Status: Complete

## Outcome + scope

`browser measure` applies the fetch-wave limit to the page load and to each later input step on its own, so a screen that signs in before its data and then posts and loads the result can pass. It also counts accent colours for a button group that sits directly in the page container over that group's own row, so status colours in a list below a tab bar stop counting against the tab bar. Non-goals: other measured rules, the layout-shift limit, a project list of status tokens, and changes to the vendored skill package copies.

## Sources + coverage

Sources: the maintainer's request of 2026-11-23, with its five holes and its added scope for the issue `sgaabdu4/hard-eng#705` (the issue text was read too), read in full.
Reviewer: N/A — two small faults, each with a stated fix and a stated set of cases that must keep failing.
Deliverables: None

- Per-step fetch waves, the load and each input step measured apart: In scope — A page with one parallel load wave and three presses that each post then load has no finding
- A step that changes nothing must not split a waterfall: In scope — A `hover` in a quiet gap, and a `click body` while a fetch is in flight, do not split a 4-wave load
- A recorded step with no fetch after it must not split a waterfall: In scope — A `hover` or a `click body` in a 5-second quiet gap of a load, with no fetch starting after it, does not split the 4-wave load
- The page must not fake action times: In scope — An `eval` step, and the page itself, add no action; a real press adds one line
- Verb parsing fails closed: In scope — Each verb of the request is marked, each other or misread step is not
- Recording an action never fails or changes the step and prints nothing: In scope — A file that cannot be written leaves the step running and prints nothing
- The test helper `plain_step` must go through `browser.dispatch`: In scope — `plain_step` runs the real command path: a `click` through it leaves a line in the session's file
- Issue 705, the tab bar in the page container: In scope — The issue's tab bar page has no finding at any width, `shared-edge` included
- Issue 705, a wrapper must not hide colours: In scope — A card with a button pair and 3 accents, a tab bar with 3 accents of its own, and many colours inside a `div` or `section` wrapper still fail with `accent-colours`
- Issue 705, status words, dot size and a project list of status tokens: Later — user, the added scope for `sgaabdu4/hard-eng#705` rejects them; the list is an allowlist
- Page-level container reading for the accent block: Proposal — `body`, `main` and an element that holds the page's first `h1` count as the page, so the block shrinks to the group's own row; the limit of 2 stays, and the base text colour still counts; yes — user, AGENTS.md ("This codebase is yours: what it's for and how it's built are your call") and the Hierarchy line of `features/ui-quality-enforcement/PLAN.md` ("at most 2 accent colours per block")

## Repository context

Owners: `.hooks/ui_measure.py` (`MEASURE_SCRIPT`, `LIMITS`, `measure_script`) owns the measured limits and the page script. `.hooks/browser.py` owns the session steps, so it owns the action file. `.agents/skills/he-ship/references/checks.md` and `.agents/skills/e2e/references/browser.md` own the wording for agents.
Same cause: Issue 705: `shared-edge` reads the same `parent.parentElement` block. The issue's page gives no `shared-edge` finding (the test for it expects no finding at all), so it stays as it is. Fetch waves: searched `fetch_waves`, `fetch-waterfall` and `waterfall` in `.hooks`, `tests` and the skills; one owner, no other copy of the count. `layout-shift` reads the whole page life, and the browser already leaves out shifts that follow input, so it stays.
Single source: The limit stays in `LIMITS` (`fetch_waves`), and the new quiet time sits in the same table (`action_quiet_ms`). The set of verbs that commit input lives once in `.hooks/browser.py`. The vendored skill package copies under `.agents/skill-sources` hold an older `ui_measure.py` with no fetch-wave rule, so no copy of this rule exists there.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous — the user's standing rule: merge each task PR once its checks pass; an installed project's capture of a press-then-result screen cannot pass today.

## Acceptance + steps

- [x] A page with one parallel load wave and three presses that each post then load has no finding → `tests/test_ui_audit_guards.py::test_each_press_is_measured_apart_from_the_load`
- [x] A 4-wave load still fails at `load`, even when an older action sits in the session file → `tests/test_ui_audit_guards.py::test_a_four_wave_load_still_fails_after_an_older_action_in_the_session`
- [x] A press that starts a 4-wave chain fails at that press → `tests/test_ui_audit_guards.py::test_a_press_that_starts_a_four_wave_chain_fails_at_that_press`
- [x] A `hover` in a quiet gap, and a `click body` while a fetch is in flight, do not split a 4-wave load → `tests/test_ui_audit_guards.py::test_a_click_while_a_fetch_is_in_flight_does_not_split_a_load_waterfall`
- [x] A `hover` or a `click body` in a 5-second quiet gap of a load, with no fetch starting after it, does not split the 4-wave load → `tests/test_ui_audit_guards.py::test_a_step_in_a_quiet_gap_that_starts_no_fetch_does_not_split_a_load_waterfall`
- [x] An `eval` step, and the page itself, add no action; a real press adds one line → `tests/test_ui_audit_guards.py::test_an_eval_step_and_the_page_cannot_add_an_action`
- [x] Each verb of the request is marked, each other or misread step is not, and `--session=S` reads like `--session S` → `tests/test_ui_audit_guards.py::test_a_step_that_commits_input_is_marked`, `tests/test_ui_audit_guards.py::test_any_other_step_is_not_marked`, `tests/test_ui_audit_guards.py::test_a_misread_step_is_not_marked`
- [x] A file that cannot be written leaves the step running and prints nothing; unreadable lines are skipped → `tests/test_ui_audit_guards.py::test_recording_an_action_never_fails_the_step_or_prints`
- [x] `plain_step` runs the real command path: a `click` through it leaves a line in the session's file → `tests/test_ui_audit_guards.py::test_an_eval_step_and_the_page_cannot_add_an_action`
- [x] The issue's tab bar page has no finding at any width, `shared-edge` included → `tests/test_ui_accent_block.py::test_a_tab_bar_in_the_page_container_does_not_count_the_whole_page`
- [x] A card with a button pair and 3 accents, a tab bar with 3 accents of its own, and many colours inside a `div` or `section` wrapper still fail with `accent-colours` → `tests/test_ui_accent_block.py::test_accent_colours_around_a_button_group_still_count`
- [x] The `checks.md` bullet and the `browser.md` lines say that each input step has its own fetch limit and that a button group in the page container counts its own row → N/A — prose; `tests/test_skill_links.py` checks the links and the file size
- [x] A plain step costs no more than a fraction of a millisecond, and the measure script runs as fast as before → N/A — a timing result, recorded in Verification

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` at 9bf7d49a, the `Hard Eng` and `Canary` runs concluded success. Locally, `uv run pytest tests/test_browser.py::test_measure_records_an_open_session_state` passed (1 passed) before any edit.
Execution: One builder, test first: the two red commits of tests, then `.hooks/browser.py` and `.hooks/ui_measure.py`, then the two doc lines.

## Risks + recovery

A step starts a new part only when the page was quiet for 500 ms before it and a fetch starts within 1000 ms after it. A waterfall with a gap of 500 ms or more is split only by an input step that is followed by a fetch within 1000 ms, which is the last second of the gap; that step started new work after a quiet time. A step whose verb the tool reads in a form this code does not know records nothing, so the old single count applies. Recovery: revert the commits.
Not checked: browsers other than the one that `agent-browser` starts; a remote browser on another machine, whose clock may differ from the clock of the action file.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: Red first: at the red commit the new tests failed on develop code (the press page gave `fetch-waterfall` at `page`; the issue page gave `accent-colours` with 4 colours; 51 of the new fetch tests failed, most for the missing `action_mark`). Focused after the change: `tests/test_ui_audit_guards.py` 64 passed, `tests/test_ui_accent_block.py` 5 passed, `tests/test_skill_links.py` and `tests/test_ui_text_rows.py` 20 passed. Ready check on 0c14696f: the full suite 7764 passed, and every native check passed. Static gates (ruff format, lint, complexity, annotations, pyrefly, vulture, deptry, jscpd, security) passed. Mutation checks: with the quiet test removed, the in-flight test fails; with the origin filter removed, the older-action test fails; with the reaction test removed, the quiet-gap click test fails. Timing, compiled modules, two runs each, develop against this branch: one plain `click` step through `dispatch` took 0.033 ms and 0.033 ms before, 0.063 ms and 0.062 ms after (one line appended to a file), and the import took 18.9 and 15.6 ms before, 16.1 and 15.1 ms after; the measure script on a 5 KB page and on a large public page took a median of 1.0 and 5.4 ms before and 1.0 and 5.3 ms after. Full check: the `check --plan-stage Complete` run on the final head and the CI runs of the PR.
Review declined: a recorded `click` in the last second of a quiet gap in a load, when a load fetch follows within 1000 ms, still splits that load :: it needs a quiet time of 500 ms and a fetch within 1000 ms after the step, the rule that the request set; a reaction check on the page itself would need page-side telemetry that the request did not ask for, and the miss lets a 4-wave load pass only when an agent times a click.
Review declined: the `hover` run of the quiet-gap test cannot fail through the cut logic :: `hover` is never recorded by design; that run guards the verb table, and the `click` run guards the cut logic.
Review declined: a card that holds the page's first `h1` counts as page level :: the request defines the page-level container as an element that holds the page's `h1`, and a block that holds the page heading is the whole screen in a real page.
Reviews: two fresh Opus review sessions read the diff (the outside reviewers could not run: one is over its usage limit and one rejects the call). The first found a click in a long quiet gap splitting a load, a hover test that proves nothing alone, and the h1 choice; the first is fixed with the reaction test. The second found the same click timing (declined above), an older-action test that could not fail for its reason, and part labels that counted the wrong steps; both are fixed with a red test first. After the rebase on the develop that holds the fallback, `challenge` ran a fresh claude session on fd78432a. It found that the docs did not state the quiet and reaction conditions, no tool comparison and no Reader check on record; the docs now state both conditions and the cure, and the next two lines record the other two.
Parser comparison: 53 steps ran through the real `agent-browser` on a page that logs input events (click, dblclick, mousedown, mouseup, input, change, keydown, keyup, beforeinput, dragstart, drop). For each step the harness compared "an event fired" with "`action_mark` marks the step". The first run agreed on 47 of 53: the tool also accepts `tap`, `key`, `keydown` and `keyup`, which fire those events, so they are verbs now (a red row in the verb table first); the second run agreed on 51 of 53. The 2 differences are steps the tool refused (`find placeholder Mail type y` and `find testid none click` exit 1, so no event fired): the action file notes a step before the tool runs it, so a refused step is marked. A refused step needs a quiet page and a fetch within 1 s after it to start a part, so the limit stays as stated in Risks.
Reader check: a fresh Opus reader compared the old and new prose of `browser.md` and `checks.md` and quoted four sentences: the accent block with no verb, the fetch limit with no word for a wave and a bare "passes", the wait cure that omitted the 1 s rule and the same session, and "after `wait --load networkidle`", which read as a wait that follows the step. Each is reworded: the block is the row of that group, a wave is fetches that run at the same time, a step "can pass", the wait runs before each step in the same session, and the 1 s rule is stated.
Doc correction: the last review noted that the advice to run `wait --load networkidle` before a step was never tested. A run against the real tool, with a button that starts a 3-second fetch, showed that `wait --load networkidle` after the click returned in 1.25 s, before the fetch ended. The docs now say to wait for the result of the step before it, then `wait 600`, and a fresh reader read the new sentences. It quoted four: `600 ms` against the 500 ms rule with the 1 s rule missing, what to wait for after the page load, "the earlier count" and "a press". Each is reworded.
E2E: N/A — the proof is the real-browser tests above, which drive `browser.browser_command` and a real page; no journey of an app is changed.
Real service: N/A — no outside service is called; the test pages are served from a local folder.
Retro: (1) Fault on the base branch, a press-then-result screen could never pass the fetch limit → `tests/test_ui_audit_guards.py::test_each_press_is_measured_apart_from_the_load`. (2) Fault on the base branch, a tab bar in the page container counted the whole page → `tests/test_ui_accent_block.py::test_a_tab_bar_in_the_page_container_does_not_count_the_whole_page`. (3) A review found a no-op click splitting a load → `tests/test_ui_audit_guards.py::test_a_step_in_a_quiet_gap_that_starts_no_fetch_does_not_split_a_load_waterfall`. (4) A newer Fallow release printed a setting, `keepExportTags`, that no table classed, so the Complete check failed on develop code; it is classed `equal` as its own commit → `tests/test_settings_tables.py::test_every_setting_that_fallow_prints_has_a_class`. (5) Two chain test pages did not read response bodies, so waves merged and the check failed once under load; they read the bodies now and the timing tests passed 15 of 15 runs → `tests/test_ui_audit_guards.py::test_a_step_in_a_quiet_gap_that_starts_no_fetch_does_not_split_a_load_waterfall`.

Delivery target: Merge
Delivery: Pending — CI, the guarded merge into `develop`, then the hotfix PR into `main`.
