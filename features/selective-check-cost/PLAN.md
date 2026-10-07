# Check one tree once, keep notes out of package scope, run more checks at once, lighten pre-push and merge by rebase only

Status: Complete

## Outcome + scope

- A push to the base branch reuses a merged PR's passed required checks whenever the pushed tree equals that PR head's tree, for merge, squash and rebase merges alike.
- Markdown in any folder counts as documentation unless a package's `impact_inputs` claims it or it sits below the root of a JavaScript package, where sites build from Markdown (user choice 2026-10-07).
- `check` runs up to one parallel-safe check per CPU instead of two.
- Pre-push checks only the packages that own changed files; CI still adds their dependents.
- A Dart Decimate dead-code gate covers import boundaries whatever order its arguments take.
- `ship --stage merge` merges by rebase only and refuses squash and merge commits.
- The Hard Eng workflow grants `pull-requests: read`, which the PR lookup needs in private repositories; setup adds it to existing generated copies (user approval 2026-10-07).

Non-goals (user decision 2026-10-07): skipping checks that passed before, a package exclude list, tool-specific related-test runs, conflict declarations between checks. Mutation stays in pre-push: it already covers only changed lines, never blocks and runs nowhere else.

## Repository context

Owners:
- `.hooks/shipping.py` `_pull_request_head`, `reused_pull_request`: reuse needs one commit onto the old base named as a merge or `(#N)`, so rebase merges never match.
- `.hooks/plans.py` `is_documentation`: counts only top-level Markdown; `.hooks/gate_config.py` `packages_for` checks `impact_inputs` consumers first.
- `.hooks/hard-eng.py` `check`: `ThreadPoolExecutor(max_workers=2)` and a drain at two pending.
- `.hooks/ship_actions.py` `pre_push`, `.hooks/gate_config.py` `affected_groups`, `.hooks/dependency_graph.py` `expand_dependents`.
- `.hooks/gate_config.py` `dart_scan_includes_boundaries`: matches two exact argument orders.
- `.hooks/ship_actions.py` `run`, `.hooks/hard-eng.py` `--merge-method`, `.agents/skills/he-ship/references/checks.md`: accept merge, squash or rebase.
- Evidence: issue #238; the user's 2026-10-07 replies on Dart Decimate argument order and rebase-only merging. `gh api repos/<repo>/commits/<sha>/pulls` returns the merged PR with `head.sha`, `base.ref` and `merged_at` for a squash merge on this repository.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked to fix the open issues, chose these changes on 2026-10-07, added rebase-only merging the same day, and asked for an adversarial review loop before opening the PR.

## Acceptance + steps

- [x] A base-branch push of several rebased commits whose tree equals the merged PR head's tree, with passed required checks, reuses that result → new rebase case in `tests/test_shipping.py`; squash and merge cases keep passing.
- [x] A different tree, no merged PR, more than one merged PR, a PR into another base, or a failed or missing required check runs the gates → existing and updated refusal cases.
- [x] `docs/notes/x.md` alone selects only the secret scan; the same file under a package's `impact_inputs` selects that package; `site/content/post.md` in a JavaScript package selects it → `tests/test_affected_selection.py`.
- [x] `check` keeps up to `os.cpu_count()` parallel checks in flight → runner test.
- [x] Pre-push passes the owner-only scope; `check` with it selects changed packages without dependents while ancestor installs and shared checks stay → `tests/test_ship_actions.py`, `tests/test_affected_selection.py`.
- [x] A Decimate gate with `--format json --threshold 0 --strict` covers boundaries; one with an extra `--no-boundary-violations` does not → `tests/test_setup.py`.
- [x] An installed workflow without `pull-requests: read` gains it on update and then matches the template → `tests/test_ci_setup.py`.
- [x] `ship --stage merge` calls `gh pr merge --rebase`; `squash` or `merge` is refused before any GitHub call → `tests/test_ship_actions.py`.
- [x] Full gate passes → `python3 .hooks/hard-eng.py check --plan-stage Complete` exits 0.

## Baseline + execution

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --plan-stage Draft` on unchanged `6b5d3481` plus this plan → exit 0, 1213 tests passed.
Execution: One builder in this worktree.

## Risks + recovery

A change that breaks a dependent package now fails in CI instead of pre-push, costing one CI round. A non-JavaScript package whose Markdown is build input must list that folder in `impact_inputs`. A JavaScript workspace whose root `.` is itself a package still checks that root for nested notes such as `docs/adr/x.md`. More parallel checks use more memory at once. A failed GitHub query falls back to the full run. Another workflow that calls the Hard Eng workflow must also grant `pull-requests: read`, or it fails to start. Recovery is reverting this branch.

## ux_reference

N/A — check selection and CI behaviour; no visual surface.

## Verification

Result: Passed
Evidence: Focused suites for shipping, selection, runner, pre-push, CI setup and Dart config pass. Failure of the new tests against the old code was reasoned from the old conditions, not run. `gh api repos/<repo>/commits/<sha>/pulls` returned the merged PR with `head.sha`, `base.ref` and `merged_at` for a squash merge here and for the tip of a rebase-only repository, whose PR head tree matched. Codex adversarial review (gpt-6-astra), five rounds: round 1 found owner-only pre-push dropping a Fallow cycle partner and older pushed runners rejecting the new flag (both fixed, `test_cross_package_fallow_coverage_owner_must_be_selected_with_its_consumer`, `test_pre_push_keeps_the_passed_push_over_budget_or_after_mutation_fails`); round 2 found Markdown site content losing its build check (user chose to keep nested Markdown in JavaScript packages selecting them); round 3 found the PR lookup needs `pull-requests: read` in private repositories (user approved adding it with a migration); round 4 found the migration could duplicate an existing grant (fixed, `test_workflow_holds_one_pr_permission`); round 5 found no code defect.
Gate: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` → exit 0, 1226 tests passed, 90.24% line coverage.
E2E: N/A — the main-branch reuse is a GitHub push run, proven after merge when main prints the reuse line; the pre-push journey is covered by `test_pre_push_tests_committed_code`, which pushes through the real hook.

Delivery target: Merge
Delivery: Pending
