# Measure what Hard Eng adds, judge lessons on isolated evidence, and cut stale records

Status: Complete

## Outcome + scope

`tests/agent_checks.py --bare` runs each case with Hard Eng's instructions, skills and hook registrations removed, so results show what they add. HE Learn keeps a lesson only from a fix whose effect the evidence isolates. ADRs can record a rejected idea. Proof goes in the commit that changes the proved code, not in a separate commit. 142 Complete plans that nothing links to are deleted, and `actor-prompt.md` moves to `tests/`. Non-goals: the requirement registry, DECISION.md, AGENTS.md, README, plans.py and the he-plan template (other active work owns them); a skill size test (after the plan-to-test work merges).

## Repository context

Owners: `tests/agent_checks.py` `fixture()` and `main()`; `tests/test_agent_checks.py`; `.agents/skills/he-learn/SKILL.md` and `references/decisions.md`; `.agents/skills/he-build/SKILL.md` Progress line; `AGENTS.override.md` canary rule; `release_canary.py` `SOURCE_ONLY_FILES`. Ideas come from the six-repo study (Harness² edit verdicts, addyosmani with/without-skill evals, Matt Pocock `.out-of-scope/`).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Autonomous. Abid asked to use the six repos' ideas to improve Hard Eng; build locally on `claude/project-thread-de5yd6`, ask before push or PR.

## Acceptance + steps

- [x] A `--bare` fixture has no `AGENTS.md`, `.agents/`, `.claude/`, `.codex/` or pre-push hook, and its `.hooks/hard-eng.py check --plan-stage Ready` still passes; a normal fixture keeps them → `tests/test_agent_checks.py`.
- [x] `results.json` records whether the run was bare → `tests/test_agent_checks.py`.
- [x] HE Learn states the helped / hurt / no effect / confounded verdicts; decisions.md allows Status Rejected → skill link and routing tests pass.
- [x] No remaining link points at a deleted plan → `tests/test_skill_links.py`, `grep`.

## Baseline + execution

Result: Passed
Evidence: Starting commit `fbbb031` passed the full `hard-eng` gate in CI ([run 39054549201](https://github.com/sgaabdu4/hard-eng/actions/runs/39054549201), success). In this container `pytest -n auto tests` → 1725 passed, 9 failed; all 9 need tools absent here (`dart`, Xcode `xccov`) or signal timing (`test_interrupted_pre_push_removes_its_snapshot`, `test_a_step_past_its_limit_stops_every_process_it_started`). Local `hard-eng.py check` stops before its gates: mise cannot list gitleaks, osv-scanner, shellcheck and actionlint releases through this container's GitHub proxy (403).
Execution: One builder; bare arm first, then skill text, then deletions. CI runs the full gate.

## Risks + recovery

A bare run can still read `.hooks/` scripts, so it measures instructions, skills and hooks, not every file. Deleted plans stay in Git history; restore one with `git checkout <rev> -- features/<slug>/PLAN.md`.

## ux_reference

N/A — no visible product change; test runner option and Markdown only.

## Verification

Result: Passed
Evidence: Container run after the change: `pytest -n auto tests` → 1728 passed, the same 9 environment failures as the baseline and no new one. `test_a_bare_fixture_hides_hard_eng_from_the_agent_but_keeps_its_checks` passes for both arms, and the Ready check passes inside the bare fixture. `test_results_record_a_bare_run` passes. ruff format, ruff lint + complexity, pyrefly (0 diagnostics), vulture and semgrep `p/python` on the changed Python pass. `git grep` finds no link to a deleted plan. Not run here: gitleaks, osv-scanner, shellcheck, actionlint, biome and jscpd (mise cannot reach their release lists); CI runs them. No real agent run with `--bare` yet.
E2E: N/A — no user journey; the fixture tests prove the runner option.
