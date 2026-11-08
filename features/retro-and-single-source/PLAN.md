# Retro and single source in every plan

Status: Complete

## Outcome + scope

Every plan a change edits names the single owner of each rule, value or type it touches and every other copy found; copies are merged in the same change or block the plan. Every Complete plan a change edits records a retro: each failed check or correction in the task and where its prevention went. HE Learn gets a retro route that sorts each item: a mechanical rule gets a check at its owner, a judgement call goes to review, a Hard Eng fault becomes a Hard Eng issue. Non-goals: a checker per incident, hook changes, failed-check recording, consumer checkers.

## Repository context

Owners: `.hooks/plans.py` (`validate_plan`), `.agents/skills/he-plan/templates/PLAN.md`, `.agents/skills/he-learn/SKILL.md`, `.agents/skills/he-plan/SKILL.md`, `tests/test_plans.py`, plan fixtures in `tests/conftest.py` and `tests/agent_fixtures.py`.
Evidence: a reviewer read a consumer's 34 failed CI runs and 187 push attempts since 2026-10-21. Most failed pushes came from checks first run in the push gate; fixes were made by hand and no prevention or Hard Eng issue followed. The consumer wrote about 50 separate single-source scripts, one per past bug, and one of them stopped a push gate at 600 seconds. Hard Eng has no single-source rule in any skill, requirement, plan field or check; jscpd and Fallow catch copied text only.
Same cause: complexity repeats in `gate_schedule.py::run_checks` and `plans.py::validate_plan` share one cause, branches added to a function at its limit; both now call helpers. The last new plan field (`Same cause`, 2026-10-22) failed a consumer's CI on an untouched Ready plan, because the rule applied to every Ready plan. Both new fields apply only to plans the change edits.
Single source: `.hooks/plans.py::validate_plan` owns plan field rules and the template owns field guidance; no other copy of these rules exists (searched `.hooks/` and `.agents/skills/` for `Same cause`).

## Decisions + authorization

Blockers: None
Handoff: Approval
Authority: The maintainer approved on 2026-11-08 ("yes") the retro line, the single-source line, and legacy copies only shrinking, and asked that legacy copies always be removed.
Decision: a copy the change cannot merge is written on `Blockers`, so the plan cannot reach Ready or Complete until that copy is merged. This holds features back behind old copies by design.
Decision: retro content is free text checked for presence, like `Same cause`. Matching it to each failed check waits for failed-check recording that also covers pre-push, which runs in a temporary copy.

## Acceptance + steps

- [x] A changed Ready or Complete plan without `Single source:` fails; an unchanged one still passes → `tests/test_planning_handoffs.py::test_changed_plans_need_single_source_and_retro`.
- [x] A changed Complete plan without `Retro:` fails; a changed Ready plan without it passes → `tests/test_planning_handoffs.py::test_changed_plans_need_single_source_and_retro`.
- [x] The template carries both fields with their guidance, and HE Learn has the retro route → `tests/test_planning_handoffs.py::test_changed_plans_need_single_source_and_retro`.

## Baseline + execution

Result: Passed
Evidence: develop a32afcb2 (the merged Fallow fix) passed the full pre-push check on 2026-11-08.
Execution: This session, one builder; tests first, then `validate_plan`, then template and skill text.

## Risks + recovery

- An active plan edited after the update must add both fields. Recovery: add them, or revert the commit.
- Retro text cannot prove every failure was listed. Named follow-up: record failed checks from every in-checkout and pre-push check, then require the retro to name each one.

## ux_reference

N/A — no app screens change.

## Verification

Result: Passed
Evidence: On 2026-11-08 `uv run pytest -q tests/test_plans.py tests/test_plan_acceptance.py tests/test_planning_handoffs.py` passed; the new test failed first with "DID NOT RAISE ValueError".
E2E: N/A — plan checks with no user journey.
Retro: This session's items, sorted by the new route:
- File length and repeated-code failures first seen at the Complete check → ran too late for the turn-end check, which must stay as fast as it is; the build step's Complete check caught both before push, so none new.
- Plan wording refused at the Complete check twice → ran too late: HE Plan already requires the Ready check before build; this plan ran it before any code, so none new.
- Complexity over the limit three times (`run_checks`, then `validate_plan` twice) → same cause each time: new branches added to a function at the limit, with no focused lint before the turn ended. HE Build already lists focused lint for touched files; the existing lint caught each one at turn end. Fixed by moving the rules into `start`, `blocked_by` and `newer_fields`; none new.
- Fallow failing on coverage that failed tests never wrote → Hard Eng fault, fixed in `tests/test_gate_speed.py::test_a_coverage_reader_is_blocked_not_failed_when_its_tests_fail`.
- This test unticked a Complete plan's boxes → test-writing error, fixed in this change; none new.
- `tests/test_plans.py` over 1000 lines after this test was added, the second file-length failure today → caught at turn end by the existing check; same cause as `tests/test_shipping.py` earlier: appending to a test file near the limit. The test moved to `tests/test_planning_handoffs.py`; none new, because the check already blocks it.
- GitHub 504 errors on downloads → outside cause; none.
Delivery target: Merge
Delivery: Pending — PR into `develop` with `hard-eng` and `canary` green, then release.
