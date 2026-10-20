# Measure what Hard Eng adds, judge lessons on isolated evidence, and cut stale records

Status: Complete

## Outcome + scope

`tests/agent_checks.py --bare` runs each case with Hard Eng's instructions, skills and hook registrations removed, so results show what they add. HE Learn keeps a lesson only from a fix whose effect the evidence isolates. ADRs can record a rejected idea. Proof goes in the commit that changes the proved code, not in a separate commit. 142 Complete plans that nothing links to are deleted, and `actor-prompt.md` moves to `tests/`. Non-goals: the requirement registry, DECISION.md, AGENTS.md, README, plans.py and the he-plan template (other active work owns them); a skill size test (after the plan-to-test work merges).

## Repository context

Owners: `tests/agent_checks.py` `fixture()` and `main()`; `tests/test_agent_checks.py`; `.agents/skills/he-learn/SKILL.md` and `references/decisions.md`; `.agents/skills/he-build/SKILL.md` Progress line; `AGENTS.override.md` canary rule; `release_canary.py` `SOURCE_ONLY_FILES`. Ideas come from the six-repo study (Harness² edit verdicts, addyosmani with/without-skill evals, Matt Pocock `.out-of-scope/`).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. Abid asked to use the six repos' ideas to improve Hard Eng, to push and open PRs, and to decide pending items without him; PR targets `develop`.

## Acceptance + steps

- [x] `tests/agent_checks.py` stays under 1000 lines → the `check` line-limit gate. A `--bare` fixture has no `AGENTS.md`, `.agents/`, `.claude/`, `.codex/` or pre-push hook, and its `.hooks/hard-eng.py check --plan-stage Ready` still passes; a normal fixture keeps them → `tests/test_agent_checks.py`.
- [x] `results.json` records whether the run was bare → `tests/test_agent_checks.py`.
- [x] HE Learn states the helped / hurt / no effect / confounded verdicts; decisions.md allows Status Rejected → `tests/test_skill_links.py::test_distributed_skill_links_resolve` and `tests/test_skill_routing.py::test_every_request_picks_its_own_skill` pass.
- [x] No remaining link points at a deleted plan → `tests/test_skill_links.py::test_distributed_skill_links_resolve` + `git grep` for `features/` paths.

## Baseline + execution

Result: Passed
Evidence: Starting commit `cf7f1a5` on `develop` passed the full `hard-eng` gate in CI ([run 39397814511](https://github.com/sgaabdu4/hard-eng/actions/runs/39397814511), success). In this container on `cf7f1a5`, `pytest -n auto tests` → 1733 passed, 8 failed; all 8 need tools absent here (`dart`, Xcode `xccov`) or signal timing (`test_interrupted_pre_push_removes_its_snapshot`). Local `hard-eng.py check` stops before its gates: mise cannot list gitleaks, osv-scanner, shellcheck and actionlint releases through this container's GitHub proxy (403).
Execution: One builder; bare arm first, then skill text, then deletions. CI runs the full gate.

## Risks + recovery

A bare run can still read `.hooks/` scripts, so it measures instructions, skills and hooks, not every file. Deleted plans stay in Git history; restore one with `git checkout <rev> -- features/<slug>/PLAN.md`.

## ux_reference

N/A — no visible product change; test runner option and Markdown only.

## Verification

Result: Passed
Evidence: Container run after the change: `pytest -n auto tests` → 1736 passed, the same 8 environment failures as the baseline and no new one. `test_a_bare_fixture_hides_hard_eng_from_the_agent_but_keeps_its_checks` passes for both arms, and the Ready check passes inside the bare fixture. `test_results_record_a_bare_run` passes. ruff format, ruff lint + complexity, pyrefly (0 diagnostics), vulture, jscpd (0 clones) and biome pass. `validate_attribution` and `validate_decisions` against `origin/develop` pass. `git grep` finds no link to a deleted plan. `tests/agent_checks.py` has 989 lines. CI runs gitleaks, osv-scanner, shellcheck and actionlint; they cannot install in this container. Independent review: not done, because Codex is not installed here. No real agent run with `--bare` yet.
E2E: N/A — no user journey; the fixture tests prove the runner option.

Delivery target: PR
Delivery: Pending — hard-eng CI on the PR into develop.
