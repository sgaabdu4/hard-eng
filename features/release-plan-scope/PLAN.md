# Feature checks see the plans the release will check

Status: Complete

## Outcome + scope

A feature PR into develop now validates every plan changed since the release base (main), not only the plans changed since develop. So a new plan rule fails on the PR that adds it, not first on the develop-to-main release PR. This PR also fixes the develop plans that still broke the acceptance rule and turned release PR #327 red; `node-shim-flag-values` was fixed separately on develop (b415619). Non-goals: re-checking unchanged legacy plans, new rules or files.

## Repository context

Owners: `.hooks/plans.py` `validate_plans` and `plan_tests`, which reuse `default_branch_point` (shipping base merge-base) and `changed_files`. Cause: #330 passed against develop, but the release PR diffs against main, where develop-edited plans count as changed and get the new rule.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: Abid asked the agent to own this and decide open choices. Only plan files join the changed set, so size and planning-only verdicts keep their PR scope. The `skill-repo-ideas` plan fix matches #335 line for line, so either merge order works.

## Acceptance + steps

- [x] A plan edited on develop, without test references, fails a feature PR whose own diff is code only → `tests/test_plan_acceptance.py::test_feature_check_sees_plans_the_release_will_check`; it did not raise before the fix.
- [x] `develop-release-gate` and `skill-repo-ideas` plans pass against main → N/A — plan text edits, proved by `validate_plans` against origin/main in Verification.

## Baseline + execution

Result: Passed
Evidence: On develop 2c24999, `validate_plans` per plan against origin/main failed on `develop-release-gate`, `node-shim-flag-values` and `skill-repo-ideas`; the new test failed with "DID NOT RAISE".
Execution: Single session; failing test first, then the fix.

## Risks + recovery

A feature PR can now fail on a develop plan that another PR edited. That is the intended early signal; fix that plan in the same or a separate PR. Recovery: revert the commit.

## ux_reference

N/A — developer tooling, no visible interface.

## Verification

Result: Passed
Evidence: `pytest -n auto` → 1774 passed, 8 failed; the same 8 fail on develop (no Dart, Swift or signal timing support in this container). `validate_plans` against origin/develop and origin/main both return Complete. Ruff format/lint/complexity/annotations, pyrefly, vulture and jscpd pass. CI ran gitleaks, osv-scanner, shellcheck and actionlint; this container could not install them. A stale local `origin/main` no longer counts the release branch's own plans as changed (`tests/test_ship_actions.py::test_initial_push_uses_current_remote_base_and_exact_revision`). Independent review not done: `challenge` needs the Codex CLI, which this container lacks.
E2E: N/A — the behavior is plan validation over Git history; the test builds a real main, develop and feature branch history.

Delivery target: Merge
Delivery: Pending — PR into develop with the hard-eng CI check green; then release PR #327 re-runs green.
