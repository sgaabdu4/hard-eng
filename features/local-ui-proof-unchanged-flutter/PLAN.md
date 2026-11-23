# Skip Flutter meetsGuideline check on unchanged local UI proof

Status: Complete

## Outcome + scope

Align `.hooks/local_ui_proof.py` with `.hooks/ui_proof.py` `ship_problem()` so `local_ui_proof_problem()` validates `N/A — unchanged:` capture pairs before running `guideline_problem()` on changed Flutter files. An unchanged-only Flutter refactor with clean matching Before/After web captures passes local Complete-stage verification instead of failing on `meetsGuideline` for every touched Dart file, while visual Flutter changes still require `meetsGuideline` and `look`. Non-goals: weakening `guideline_problem()`, altering web proof rules, or changing `ship_problem()`.

## Sources + coverage

Sources: N/A — bug found on base branch where `local_ui_proof_problem()` rejected an `N/A — unchanged:` Flutter refactor that `ui_proof.ship_problem()` accepts.
Deliverables: None

## Repository context

Owners:
- `.hooks/local_ui_proof.py` runs fast local Complete-stage UI proof checks (`local_ui_proof_problem()`).
- `.hooks/ui_proof.py` defines `ship_problem()` and `guideline_problem()`.
- `tests/test_local_ui_proof.py` tests `local_ui_proof_problem()`.

Same cause: Checked every `guideline_problem()` call site in `.hooks/` (`ui_proof.py:578` and `local_ui_proof.py:464`). `ui_proof.ship_problem()` already returns early after `unchanged_problem()` before calling `guideline_problem()`; only `local_ui_proof_problem()` placed `guideline_problem()` above the `if unchanged:` return.
Single source: `.hooks/ui_proof.py` owns `guideline_problem()` and `unchanged_problem()`; `.hooks/local_ui_proof.py` mirrors `ship_problem()`'s order.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: Autonomous. Bugfix discovered during maintainer-authorized rollout verification.

## Acceptance + steps

- [x] `local_ui_proof_problem()` accepts an `N/A — unchanged:` Flutter refactor with a clean matching Before/After capture pair without demanding `meetsGuideline` widget tests, while still refusing when `ux_reference` is visual → `tests/test_local_ui_proof.py::test_local_complete_check_skips_flutter_guideline_for_unchanged_pair`.
- [x] Existing local UI proof and full Hard Eng checks stay green → N/A — `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` is the proof.

## Baseline + execution

Result: Passed
Evidence: Before the fix, `test_local_complete_check_skips_flutter_guideline_for_unchanged_pair` failed on `origin/develop` (`d5ee8ba7`) with `the Flutter screen app/lib/ui/card.dart changed, but no widget test imports it and calls meetsGuideline; add one`. Moving `guideline_problem()` below the `if unchanged: ... if not visual_plans: return None` return makes the test pass while keeping the visual-plan assertion failing with `meetsGuideline`.
Execution: Single builder in an isolated worktree: add failing regression test in `tests/test_local_ui_proof.py`, reorder `guideline_problem()` in `.hooks/local_ui_proof.py`, run tests, full checks, and independent challenge.

## Risks + recovery

Visual Flutter changes (and mixed branches with any visual plan) still execute `guideline_problem()` and `_local_look_problem()`, matching `ship_problem()`. Recovery: revert the merge commit on `develop`.

## ux_reference

N/A — local UI proof Python hook logic has no user interface.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_local_ui_proof.py tests/test_ui_quality.py` passed, and full `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` plus `challenge --host agy` ran on the committed branch.
E2E: N/A — CLI/hook proof check has no interactive user journey; the regression test exercises real git commits and browser records in a temporary Flutter repo fixture.
Real service: N/A — local Python hook logic makes no network or external service calls.
Retro: Escaped bug on base branch (`local_ui_proof_problem` called `guideline_problem` ahead of the `unchanged` return, diverging from `ship_problem`) → captured by `tests/test_local_ui_proof.py::test_local_complete_check_skips_flutter_guideline_for_unchanged_pair` and fixed in `.hooks/local_ui_proof.py`.
Delivery target: PR
Delivery: Pending — checks, challenge, PR to `develop`, CI, and merge.
