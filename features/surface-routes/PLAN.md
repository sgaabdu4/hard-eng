# Ship and the plan check read every route of the Surface line

Status: Complete

## Outcome + scope

A plan whose `Surface:` line names several routes accepts an After capture of any listed route, in `ship` and in the local Complete check. The local check refuses a looked-at capture of an unlisted route, as `ship` does. Non-goals: matching `[id]` bracket segments against real page paths; any other ship rule.

## Sources + coverage

Sources: N/A — the request is the only source: the coordinator's brief of 2026-11-24 for a client-blocking fault.

## Repository context

Owners: `.hooks/ui_proof.py` (`surface_routes`, `capture_set_problem`) owns the Surface routes and the capture match; `.hooks/local_ui_proof.py` owns the local Complete check.
Same cause: the readers of the Surface route are `ship_problem`, `evidence_problem`, `measured_problem`, `capture_set_problem` and `unchanged_problem` in `ui_proof.py`, and `_local_browser_proof`, `_unchanged_routes`, `_unchanged_plans_problem` and `local_ui_proof_problem` in `local_ui_proof.py`. All now take the list. `plans.py` only checks that a `Surface:` line exists, and the PR text check and `look` never read the route. The copies under `.agents/skill-sources` belong to other repositories and stay unchanged.
Single source: `surface_routes` in `.hooks/ui_proof.py` returns every route of the Surface line; `off_surface` applies `on_route` to that list; both `ship` and the local check call them.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous: the user asked on 2026-11-24 to put client unblocking first and to release scoped client fixes to main through every normal gate; this fault blocks a client's merge.

## Acceptance + steps

- [x] An After capture of any route in a comma, "and" or comma-and Surface line passes `ship` → `tests/test_ui_capture_match.py::test_an_after_capture_of_any_route_the_surface_lists_passes_ship`
- [x] A capture of an unlisted route is refused in `ship` and the message names every listed route → `tests/test_ui_capture_match.py::test_an_after_capture_of_a_route_the_surface_does_not_list_names_every_listed_route`
- [x] A one-route Surface line refuses another route as before → `tests/test_ui_capture_match.py::test_a_one_route_surface_still_refuses_another_route`
- [x] The local Complete check accepts a capture of any listed route → `tests/test_local_ui_proof.py::test_local_complete_check_accepts_a_capture_of_any_listed_route`
- [x] The local Complete check names every listed route for an unlisted capture and keeps the one-route message → `tests/test_local_ui_proof.py::test_local_complete_check_names_every_listed_route_for_an_unlisted_capture`
- [x] The local Complete check refuses a looked-at capture set of an unlisted route even when another clean set exists, as `ship` does → `tests/test_local_ui_proof.py::test_local_complete_check_refuses_a_looked_at_capture_of_an_unlisted_route`

## Baseline + execution

Result: Passed
Evidence: On `origin/main` (37fc14d9) the new UI tests fail: ship refuses the second listed route, the messages name only the first route, and the local check passes a state that ship refuses. The existing UI tests pass.
Execution: One builder in a hotfix worktree from `main`.

## Risks + recovery

The local check now refuses a state that it accepted: a clean look record of a capture set of an unlisted route, next to a clean set of a listed route. Recovery: revert the commit. A `[id]` segment is compared literally, so a capture of `/c/42` does not match `/c/[id]`; list another route or capture the literal path.

## ux_reference

N/A — no screen changes; Hard Eng has no app UI.

## Verification

Result: Passed
Evidence: The six new tests fail on `origin/main` (ship refuses the second listed route, both messages name one route, and the local check passes a stray looked-at set) and pass after the change. The Ready check ran the full suite with 7740 passed, and the static gates passed. A `[id]` segment is compared literally; this is a stated limit.
E2E: N/A — the change is a pure check of plan text and local capture records, proved by the tests above.
Real service: N/A — no outside service is called.
Retro: Escaped bug: `tests/test_ui_capture_match.py::test_an_after_capture_of_any_route_the_surface_lists_passes_ship` and `tests/test_local_ui_proof.py::test_local_complete_check_accepts_a_capture_of_any_listed_route` now cover several routes; the gate that should have caught it was the ship UI evidence test set, which only used one-route Surface lines; the local Complete check ran too late to judge the attached image, because it accepted any one clean capture set while `ship` judges each set that holds an After image, and `tests/test_local_ui_proof.py::test_local_complete_check_refuses_a_looked_at_capture_of_an_unlisted_route` now closes that gap; the failing cases were committed before the fix. Failed check: the types gate flagged an empty list in a test table → `tests/test_local_ui_proof.py::test_local_complete_check_handles_multi_plan_siblings_and_multiple_routes` now types it.

Delivery target: PR
Delivery: Pending — required remote proof.
