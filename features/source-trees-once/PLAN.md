# Fetch the Hard Eng source trees once per run

Status: Complete

## Outcome + scope

One `hard-eng.py check` run fetches the source and previous trees of a verified Hard Eng update once, however many checks need them. Before this, the scaffold proof ran in `proven_elsewhere`, again to narrow the packages, again to skip freshness, and the plan-size proof fetched once more; each round cloned Hard Eng and both skill-source submodules for both trees. A CI log of a real app showed three such rounds, 51 s in total, before the first gate. The trees are the same as before: the update's revision and its previous revision, submodules at their pins, clean. Non-goals: the update flows in `update.py` that install a release (each fetches once per run), and a persistent cache across runs (see Decisions).

## Repository context

Callers of `fetch_sources`: `release_installed` (reached from `check_scaffold_update` and `installed_update_paths`), `update_written` in `change_size.py`, and the three update flows `repair_current_hook`, `repair_installation` and `update`. All proof rounds in one run use the same pair (update revision, previous revision) from `update_in_diff`, so one pair serves all of them. The install flows run once per process and keep their own temporary directory.
Proof rounds only read the trees: `update_plan`, `scaffold_files`, `setup_written` and `validate_gates` do not write into them. The Python cache they may create is ignored by the repository's `.gitignore`.

Same cause: `impact_outputs` also calls `proven_elsewhere`, but it runs as its own process in CI, so it fetches once for itself; the shared pair is per process. The three update flows each run once per process and fetch once.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The owner approved this CI and pre-push speed work on 2026-10-31, including editing, pushing, opening the PR and merging it after checks pass.
Decisions:
- New `.hooks/source_trees.py` holds one pair per (repository, revision, previous revision) for the rest of the process and removes it at exit. `update.shared_sources` is the one entry point for the proof rounds.
- A held tree is used again only if its `HEAD` is still the revision and `git status` shows nothing changed, submodules included; otherwise the pair is fetched again. A round that wrote into a tree can therefore never feed the next round.
- Different revision pairs are never merged. A failed fetch is not remembered.
- No persistent cache of Hard Eng's repository. After this change a run fetches once. A cache would save only that one fetch, and only on a runner whose cache directory survives between jobs; it adds a lock and a corruption path. Decision recorded with the numbers in the PR text.

## Acceptance + steps

- [x] One run that needs the trees in every proof round fetches them once, and the trees are at the right revisions and clean → `tests/test_source_trees.py::test_every_round_of_one_run_takes_the_trees_from_the_first_fetch` (red before: 5 fetches).
- [x] A tree a round changed is fetched again → `tests/test_source_trees.py::test_a_tree_a_round_changed_is_fetched_again`.
- [x] Different revision pairs get their own trees → `tests/test_source_trees.py::test_different_revisions_are_not_merged`.
- [x] The scaffold-only update proof still accepts a verified update and refuses an edited one → `tests/test_scaffold_replay.py::test_update_that_restores_edited_skill_files_is_proven` and `tests/test_scaffold_replay.py::test_update_still_refuses_an_edited_skill_file` (the update, runner, replay and selection suites also pass unchanged).
- [x] Time of the check start to the end of the last tree fetch, three runs before and three after → N/A — a timing, not a behavior; the numbers are in the PR text.

## Baseline + execution

Result: Passed
Evidence: Starting tree `07f6aee`; the new test failed with the old code (5 fetches, 1 expected).
Execution: Single session.

## Risks + recovery

A round that changed a held tree could feed a wrong result to the next round. The check of `HEAD` and `git status` before every reuse prevents it, and a test covers it. Recovery is reverting this change.

## ux_reference

N/A — no visible interface.

## Verification

Result: Passed
Evidence: Focused tests pass (219). Throwaway project with a real Hard Eng update commit and an extra source change, network on, same project and base, old code against new: fetches 5, 5, 5 against 1, 1, 1; wall time from check start to the failed plan check (the last point that fetches trees) 52.6, 43.5, 47.9 s before and 13.4, 15.2, 12.7 s after.
E2E: N/A — the tests drive the real proof functions against real Git repositories, and the timing runs the real `check` entry point.

Delivery target: Merge
Delivery: Pending — CI `hard-eng` check on the PR to `develop`, then merge.
