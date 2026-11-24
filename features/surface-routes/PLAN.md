# Ship and the plan check read every route of the Surface line

Status: Complete

## Outcome + scope

A plan whose `Surface:` line names several routes accepts an After capture of any listed route, in `ship` and in the local Complete check. The local check refuses a looked-at capture of an unlisted route, as `ship` does. A `[name]` segment of a listed route matches any one segment of the page path. The CI PR text check and the local check judge screen files by the same plan ownership rule: with several changed plans, a plan that names no screen file is not refused for the screen files of another plan. Non-goals: any other ship rule.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-24 for a client-blocking fault.

## Repository context

Owners: `.hooks/ui_proof.py` (`surface_routes`, `capture_set_problem`) owns the Surface routes and the capture match; `.hooks/local_ui_proof.py` owns the local Complete check.
Same cause: the readers of the Surface route are `ship_problem`, `evidence_problem`, `measured_problem`, `capture_set_problem` and `unchanged_problem` in `ui_proof.py`, and `_local_browser_proof`, `_unchanged_routes`, `_unchanged_plans_problem` and `local_ui_proof_problem` in `local_ui_proof.py`. All now take the list. The ownership rule of several changed plans had two copies, `_plans_reference_problem` in `local_ui_proof.py` and a loop over every plan in `pr_text.py`; both now call `plans_reference_problem` in `ui_proof.py`. `plans.py` only checks that a `Surface:` line exists, and the PR text check and `look` never read the route. The copies under `.agents/skill-sources` belong to other repositories and stay unchanged.
Single source: `surface_routes` in `.hooks/ui_proof.py` returns every route of the Surface line; `off_surface` applies `on_route` to that list; both `ship` and the local check call them. `plans_reference_problem` and `plan_owns_visible` in `.hooks/ui_proof.py` own which plan is judged on which screen files; the PR text check and the local check call them.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to put client unblocking first and to release scoped client fixes to main through every normal gate; this fault blocks a client's merge.

## Acceptance + steps

- [x] An After capture of any route in a comma, "and" or comma-and Surface line passes `ship` → `tests/test_ui_capture_match.py::test_an_after_capture_of_any_route_the_surface_lists_passes_ship`
- [x] A capture of an unlisted route is refused in `ship` and the message names every listed route → `tests/test_ui_capture_match.py::test_an_after_capture_of_a_route_the_surface_does_not_list_names_every_listed_route`
- [x] A long Surface line with seven routes and bracket segments returns exactly its seven routes, and a capture of a bracket route's real path passes while `/work` and `/other` are refused → `tests/test_ui_capture_match.py::test_a_long_surface_line_returns_exactly_its_routes`, `tests/test_ui_capture_match.py::test_a_capture_of_a_listed_bracket_route_passes_and_others_are_refused`
- [x] With two changed plans, the CI PR text check does not refuse a plan with no screen reference that names no screen file, while the plan that owns the screen files has a real reference → `tests/test_ui_plan_ownership.py::test_ci_judges_the_screen_files_by_the_plan_that_owns_them`
- [x] A plan with no screen reference that names a screen file is still refused by the CI PR text check, and by the local check → `tests/test_ui_plan_ownership.py::test_ci_still_refuses_an_na_plan_that_owns_a_screen_file`, `tests/test_local_ui_proof.py::test_local_complete_check_handles_multi_plan_siblings_and_multiple_routes`
- [x] A one-route Surface line refuses another route as before → `tests/test_ui_capture_match.py::test_a_one_route_surface_still_refuses_another_route`
- [x] The local Complete check accepts a capture of any listed route → `tests/test_local_ui_proof.py::test_local_complete_check_accepts_a_capture_of_any_listed_route`
- [x] The local Complete check names every listed route for an unlisted capture and keeps the one-route message → `tests/test_local_ui_proof.py::test_local_complete_check_names_every_listed_route_for_an_unlisted_capture`
- [x] The local Complete check refuses a looked-at capture set of an unlisted route even when another clean set exists, as `ship` does → `tests/test_local_ui_proof.py::test_local_complete_check_refuses_a_looked_at_capture_of_an_unlisted_route`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` (37fc14d9) the new UI tests fail: ship refuses the second listed route, the messages name only the first route, and the local check passes a state that ship refuses. The existing UI tests pass.
Execution: One builder in a hotfix worktree from `main`.

## Risks + recovery

The local check now refuses a state that it accepted: a clean look record of a capture set of an unlisted route, next to a clean set of a listed route. The CI PR text check now skips a plan with no screen reference that names no screen file, where it judged every changed plan on every screen file; `tests/test_plan_parent.py::test_the_pr_text_check_skips_a_parent_plan_beside_its_step` now has the shared parent plan name the screen file, so the linked cases fail when the parent filter is removed (checked by removing it) and the unlinked case is still refused. Recovery: revert the commit. A `[name]` segment matches one path segment, so a capture of `/c/42` now matches `/c/[id]`.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The new route tests fail on `origin/main`, as does `test_ci_judges_the_screen_files_by_the_plan_that_owns_them` (the CI check refuses the two-plan branch that the local check passes); the near-miss test passes there and still passes (ship refuses the second listed route, both messages name one route, and the local check passes a stray looked-at set) and pass after the change. The Ready check ran the full suite with 7750 passed, and the static gates passed. A long Surface line with seven routes and bracket segments returns exactly its seven routes. Real case, read-only: the capture-set check of these hooks ran in a scratch copy of one real project's records (one plan with 7 routes, 3 of them with brackets; 8 capture sets at its head): the old reader refused 6 sets for their route and these hooks pass all 8; the plans of that project with other routes still refuse the sets of other pages. The copy is removed.
E2E: N/A — the change is a pure check of plan text and local capture records, proved by the tests above.
Real service: N/A — no outside service is called.
Retro: Second escaped bug (same cause, two readers judge one rule two ways): the CI PR text check judged every changed plan on every screen file, and the local check judged only the plan that names the file; `tests/test_ui_plan_ownership.py::test_ci_judges_the_screen_files_by_the_plan_that_owns_them` was committed red first and both readers now call `plans_reference_problem`. Escaped bug: `tests/test_ui_capture_match.py::test_an_after_capture_of_any_route_the_surface_lists_passes_ship` and `tests/test_local_ui_proof.py::test_local_complete_check_accepts_a_capture_of_any_listed_route` now cover several routes; the gate that should have caught it was the ship UI evidence test set, which only used one-route Surface lines; the local Complete check ran too late to judge the attached image, because it accepted any one clean capture set while `ship` judges each set that holds an After image, and `tests/test_local_ui_proof.py::test_local_complete_check_refuses_a_looked_at_capture_of_an_unlisted_route` now closes that gap; the failing cases were committed before the fix. Failed check: the types gate flagged an empty list in a test table → `tests/test_local_ui_proof.py::test_local_complete_check_handles_multi_plan_siblings_and_multiple_routes` now types it.

Reader: the changed `checks.md` sentences went to a cold reader in two passes. The first pass asked what "compared as written" was compared with, and that wording was dropped when the bracket rule changed. The second pass ran on the text at the time of this review; it asked whether "starts with a listed route" means a text prefix, whether `[name]` means one or more segments, and what "Its record" points to, so the text now says that the page path is a listed route or a path, query or fragment below it, that `[name]` matches exactly one non-empty segment, and "The record of each After image".
Canary: no flow of `release_canary.py` reaches the new refusal; none of them reads a Surface line or a browser capture.

Delivery target: Merge
Delivery: Pending — `hard-eng` passes on the PR to `main`, the merge on `main`, then the join PR merged into `develop`.
