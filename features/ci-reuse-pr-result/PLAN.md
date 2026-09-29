# Reuse a passed PR check on main, drop the tool cache, measure CI minutes and stop rejecting slow passed pushes

Status: Complete

## Outcome + scope

A push to the shipping base branch reuses the merged PR's passed required checks when main now holds exactly the tree that PR tested, so the Hard Eng job succeeds in about a minute instead of repeating every gate. `hard-eng.py ci-usage` reports a repository's billed Actions minutes, rounding, never-started jobs and jobs that run on both push and PR, and the CI guidance asks for that measurement when Hard Eng is adopted or updated, or when CI changes. The generated workflow no longer caches Hard Eng's tool installs, and setup removes the generated cache step from existing copies. A pre-push run whose checks all passed but took longer than `pre_push_seconds` now warns and keeps the push; `pre_push_seconds` still times out each gate.

Non-goals: narrowing affected packages when a Hard Eng update rides in a feature PR (proving the scaffold part means an upstream clone and hooks check on every such PR, which cancels the saving wherever full and affected runs take similar time); new workflow permissions (a reusable caller that grants less than its callee fails at startup); a separate CI skill (the Adapt + repair checks route already owns CI); editing consumers' own workflows, whose cache steps and permissions stay project-owned; changed-line mutation testing in pre-push (measured on this repository's two changed shipping functions with mutmut 3.8.0: it needs a `src/` layout that `.hooks` lacks, and with workarounds about 180 mutants took about 4 minutes and left 82 survivors, nearly all message-string or case mutants and mutants that only survive because tests fake `gh` and `_checks`; one real fixture gap is fixed below, and mutation stays opt-in as `workflow.md` describes).

## Repository context

Owners:
- `.hooks/hard-eng.py` `check`: runs every selected gate on each push to the base branch, including a squash or merge commit whose tree the PR run already passed; `check_scaffold_update` is the existing early return for proven work.
- `.hooks/shipping.py` `_checks`: the delivered-stage proof that every `shipping.checks` name concluded `success` on a revision within `ci_seconds`; `gh` and `git` run the queries.
- `.hooks/ci_setup.py`: owns CI adaptation and the migrations of generated `hard-eng.yml` copies.
- `.github/workflows/hard-eng.yml`: restored a tool cache of 0.4–1 GB before installing. In nine paid-runner runs an exact hit took about 40s against about 38s for a fresh install, misses spent 14–16s saving, and restore-key hits spent 19–41s restoring plus 20–29s saving.
- `.agents/skills/he/references/gates.md`: said CI adaptation is one-time work.
- `.hooks/ship_actions.py` `pre_push`: rejected a push whose gates all passed when the whole run exceeded `pre_push_seconds`; with several agents loading the machine this repository's passed run took 402s against 300s and the push was refused. Its tests gate took 204s idle and 279s loaded, against a per-gate timeout of 300s.
- Measured evidence (30 days, scratch data outside the repository): across the installed private repositories the Hard Eng job billed 5,885 of 16,555 minutes, 2,413 of them on pushes to main; in the sampled merges the PR head already contained main in 23 of 25 and 20 of 25 merges for the two repositories with most merges.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. The user approved implementing the push reuse, the measurement command and the CI guidance in one hard-eng PR, deciding the tool cache from more paid-runner samples, turning the whole-run pre-push budget into a warning, adding everything discussed to this PR, then merging when green.

## Acceptance + steps

- [x] A CI push to the base branch whose single new commit is a squash `(#N)` or merge commit, whose tree equals the PR head's tree, whose previous base commit is an ancestor of that head, and whose head passed every required check returns success without running gates and names the reused revision → `test_push_reuses_passed_pull_request_tree` (squash and merge shapes), `test_reused_pull_request_result_skips_gates`.
- [x] Any failed condition runs the gates as before: a different tree, a base not contained in the PR head, a required check missing, pending or failed, a non-CI or non-push run, another branch, an unrecognised commit subject, uncommitted changes, a push not directly onto the previous base, a merged head without the previous base, or a GitHub query failure → `test_push_runs_checks_when_pull_request_proof_is_missing`, `test_only_ci_pushes_to_the_base_branch_reuse_pull_request_checks`, `test_push_not_directly_onto_the_previous_base_runs_checks`, `test_merge_of_a_head_without_the_previous_base_runs_checks`.
- [x] `ci-usage` bills each started job as whole minutes times its runner multiplier, excludes jobs that never got a runner, and totals rounding, cancelled and failed minutes → `test_ci_usage_bills_started_jobs_in_whole_minutes`.
- [x] `ci-usage` shows a job that ran under both push and pull_request events → `test_ci_usage_reports_jobs_repeated_on_push_and_pull_request`.
- [x] The template has no tool cache; a generated copy with the cache step migrates to the template and a project-owned cache step is kept → `test_generated_tool_cache_is_removed_from_existing_workflows`, updated migration tests.
- [x] gates.md tells agents to measure with `ci-usage` when adopting, updating or changing CI and names the measured waste patterns → review of the diff.
- [x] A pre-push run whose checks passed but exceeded `pre_push_seconds` in total prints a warning and returns success → `test_pre_push_over_budget_warns_and_keeps_the_passed_push`.
- [x] The squash fixture carries a commit body like GitHub's squash merges, so reading the whole message instead of the subject is caught → `test_push_reuses_passed_pull_request_tree[squash]`.
- [x] This repository's per-gate `pre_push_seconds` is 600, so its loaded tests gate (279s) is not killed near the old 300s limit → `hard-eng.gates.json`.

## Baseline + execution

Result: Passed
Evidence: main `1b0cdd96` passed the Hard Eng workflow on push (run 36596712641).
Execution: One builder on branch `ci-reuse-pr-result`; engine reuse first, then the measurement command, cache removal and guidance.

## Risks + recovery

The latest required check-run on the PR head could come from a PR against a different base branch; closed PRs are no longer listed on check-runs, so this rare case is accepted. A token or query failure falls back to the full run, so the saving can silently not apply; the first merge of this PR must show the reuse line on main. Recovery is reverting this branch.

## ux_reference

N/A — CI engine behaviour, a CLI report and guidance text; no product appearance.

## Verification

Result: Passed
Evidence: `python3 .hooks/hard-eng.py check --base origin/main --plan-stage Complete` passed all 18 gates (1148 tests, 90.27% line coverage). The ancestry, cache-removal, over-budget and squash-body tests failed with their conditions removed. `hard-eng.py ci-usage --days 3` against this repository listed 242 billed minutes and the Hard Eng job on both push (110 min) and pull_request (122 min). Codex adversarial review (gpt-6-astra): round 1 found that a still-running job aborted `ci-usage`; running jobs are now reported separately (`test_ci_usage_bills_started_jobs_in_whole_minutes`); rounds 2 and 3, the latter covering the budget warning, approved with no findings.
E2E: N/A — the journey is a GitHub push-to-main run, proven after merge by hard-eng's own main run printing the reuse line and `ship --stage delivered` accepting it.

Delivery target: Merge
Delivery: Pending — PR checks, squash merge and the main run reusing the PR result.
