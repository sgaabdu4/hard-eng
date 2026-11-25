# The page's own text colour is not an accent

Status: Complete

## Outcome + scope

The accent count of `browser capture` and `browser measure` leaves out the page's base text colour. That colour is the computed `color` of `body` and, when `main` is on the page, of `main`. It is left out as a text colour only: a fill or a border in that same colour still counts. A block with body text, one kind tile and one primary button no longer counts 3 colours. Non-goals: the floors of `hue()`, any grouping by hue family, and every other measure rule.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's hotfix brief of 2026-11-25. It was first added to the look-forms hotfix; that PR was already merged, so this change has its own PR.

## Repository context

Owners: `.hooks/ui_measure.py` (`MEASURE_SCRIPT`, the block loop that fills `colours`); `tests/test_ui_accent_block.py`.
Evidence: a warm near-black text colour such as `rgb(43, 27, 23)` has lightness about 0.13 and saturation about 0.30. It passes the floors of `hue()` (saturation 0.25, lightness 0.12), so it counted as an accent. No person sees a third accent there: the text colour is the page's ink. `origin/main` is `0729fee6`.
Same cause: develop holds the same count in the same loop of `ui_measure.py`, at a later line. The join keeps both new cases green on develop's side. Searched `.hooks` for another reader of accent colours: only `ui_measure.py` holds the count; `ui_quality` tests and `ux.md` name the limit, not the count. Not checked: the `building-flutter-apps` copy of the hooks.
Single source: `MEASURE_SCRIPT` stays the one owner of the accent count; the page ink is read once per page in that script.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to put client unblocking first and to release scoped client fixes to main through every normal gate; this false finding blocks a client's merge.

## Acceptance + steps

- [x] A list row and a panel whose only third colour is the page's text colour give no accent finding → `tests/test_ui_accent_block.py::test_the_page_ink_text_is_not_an_accent`
- [x] A block with three real accents plus body text, a block whose text uses a hued colour that is not the page ink, and a block with a fill in the page ink still give the finding → `tests/test_ui_accent_block.py::test_accent_colours_around_a_button_group_still_count`
- [x] Two different inks still count as two colours when neither is the page ink → `tests/test_ui_accent_block.py::test_two_different_inks_still_count_as_two_colours`

Steps:

1. Commit this plan.
2. Add the red tests and see the two new cases fail on `main`.
3. Leave the page ink out of the count in `MEASURE_SCRIPT`. Run the focused tests.
4. Run the static gates, `check --plan-stage Ready --base origin/main`, `challenge` until clean for the exact head, then `check --plan-stage Complete --base origin/main` once. If the local test gate hits its limit under load with no failing test, run it as the CI shards.
5. Open the PR to `main`, run `pr-text`, wait for CI, run `ship --stage ready`, merge with the exact head, run `ship --stage delivered`, then join `main` into `develop`.

## Baseline + execution

Result: Passed
Evidence: `tests/test_ui_accent_block.py` passes on `origin/main` at `0729fee6`.
Execution: One builder in the worktree of the earlier hotfix, on a new branch off `origin/main`. A fresh reviewer runs `challenge` on the candidate head before the Complete check.

## Risks + recovery

1. A page whose real accent has the page ink's exact colour as a text colour loses that one count. A fill or border in that colour still counts, and the three-accent near miss still fails.
2. Recovery: revert the merge on `main` with a new hotfix PR.
Not checked: any installed project.

## ux_reference

N/A — measure script and tests; no visible UI.

## Verification

Result: Passed
Evidence: Red first on `main`: `list-row` and `panel` fail with `accent-colours` at 390 px; the three near misses already hold. Green after the fix: 97 tests of `test_ui_accent_block.py`, `test_ui_quality.py` and `test_ui_pages.py`. One existing case, two different inks, used the page ink as one of its two inks; it now uses two other hued colours and still expects the finding.
E2E: Passed — `browser capture` on three local invented pages with the real browser, three widths each. The list-row page: 0 findings at 390, 768 and 1280 px. The panel page: 0 findings at each width. The near miss (blue button, red badge, green tile, page ink): `accent-colours` with `colours: 3` at each width.
Real service: N/A — no outside service is called.
Retro: (1) Fault on `main`: the base text colour passed the floors of `hue()` and counted as an accent → `tests/test_ui_accent_block.py::test_the_page_ink_text_is_not_an_accent`. (2) One existing test used the page ink as a test colour and had to change with the fix → the same file.

Delivery target: Merge
Delivery: Pending — `hard-eng` passes on the PR to `main`, the merge on `main`, then the join PR merged into `develop`.
