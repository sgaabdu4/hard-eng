# One branch point and a same-cause line for fixes

Status: Complete

## Outcome + scope

1. One function finds where HEAD left the shipping base. The comment rule, the size rule, the decision rule, the challenge reviewer and CI reuse all use it.
2. A Ready plan or a changed Complete plan needs a `Same cause:` line. A fix names earlier fixes of the same cause and every other place the cause can occur; other work writes `N/A — reason`.

Non-goals: the pre-push ref range, the Stop hook's session scope and `gate_config.initial_base` answer different questions and keep their own code. `initial_base` must use only the remote base, so a first push with no remote base checks everything (`test_new_branch_zero_base_compares_with_default_branch`). `DECISION.md` and `docs/adr/` are not changed here; the requirement registry work owns `DECISION.md`.

## Repository context

Owners: `.hooks/plans.py` `default_branch_point` (kept as the one owner) and `validate_plan`; `.hooks/comments.py` `branch_point` (removed); `.hooks/shipping.py` `passed_branch_point`; `.agents/skills/he-plan/templates/PLAN.md`; `.agents/skills/he-learn/SKILL.md`.
Same cause: The wrong change base was fixed one call site at a time: #181 (pre-push), the updater candidate, #306 and #308 (Stop hook). Before this change `comments.branch_point` and `plans.default_branch_point` found the branch point in two ways; with no shipping policy the comment rule compared with HEAD and missed committed branch changes. Searched `merge-base` in `.hooks/`: pre-push, the Stop hook and `initial_base` answer other questions and stay.

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The user asked on 2026-10-20 to build all three proposed HE Learn fixes, push and open a PR, and to decide the details. Decided: no `DECISION.md` or ADR move in this change.

## Acceptance + steps

- [x] With no shipping policy, the comment rule counts committed branch changes against `main` → `tests/test_comments.py::test_check_without_base_covers_committed_branch_changes`.
- [x] CI reuse still finds the passed branch point → `tests/test_shipping.py::test_branch_point_is_reused_only_after_its_checks_passed`.
- [x] A Ready plan or a changed Complete plan without `Same cause:` fails → `tests/test_plans.py::test_invalid_completion`.
- [x] An unchanged Complete plan without the line still passes → `tests/test_plans.py::test_unchanged_complete_plan_predates_newer_rules`.

## Baseline + execution

Result: Passed
Evidence: `uv run pytest -q tests/test_comments.py tests/test_plans.py tests/test_challenge.py tests/test_decisions.py` on `fbbb031` → 252 passed.
Execution: One builder; failing test first, then the owner change, then the plan rule.

## Risks + recovery

A project with no shipping policy now has its comment rule judge the whole branch against `main`, so older long comment blocks in changed files can fail. That matches the rule's documented scope; revert the commit if a consumer canary shows a false failure.

## ux_reference

N/A — check scripts and plan text with no visual surface.

## Verification

Result: Passed
Evidence: Red/green: `test_check_without_base_covers_committed_branch_changes[False]` and the new `Same cause` cases failed before their fixes and pass after. Full suite after rebase on develop: 1759 passed, 8 failed; the 8 need Dart, Swift or signal timing and fail on the base too. Ruff format, lint, complexity, annotations, pyrefly (0 diagnostics), vulture, deptry and jscpd (0 duplicated lines) pass.
Not checked: `check` stops at tool install in this container. The agent proxy returns 403 for tool release lists, so gitleaks, osv-scanner, shellcheck, actionlint and uv do not install. CI runs those gates.
E2E: N/A — no user journey; the real plan and comment rules run in CI's `hard-eng` check on this PR.

Delivery target: Merge
Delivery: Pending — PR checks and merge.
