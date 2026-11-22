# Ignore Hard Eng Ring Outlines and Support Plan Scope in Look Review

Status: Complete

## Outcome + scope

Fix the two `.hooks/look.py` and `No clutter` usability defects reported in `sgaabdu4/hard-eng#693` without slowing down `look`, weakening unannotated border checks, or leaking builder verdicts:
1. Record confirmed `--ring` full-page pixel boxes (`ring_boxes`: `{x, y, w, h}`) in `.hard-eng/browser/<name>-<width>.json` via `.hooks/browser.py` and `.hooks/ui_measure.py`, and instruct the `look` image reviewer in `.hooks/look.py` `PROMPT` to ignore `3px solid red` review outlines ONLY at those exact confirmed boxes (so unannotated screenshots and stray red borders elsewhere in a ringed capture are still flagged).
2. Clarify in `.agents/skills/he-plan/references/ux.md` (`No clutter`) and `.hooks/look.py` `PROMPT` that `0 removed` is a valid `Pass` when every visible element serves the user's task, and never to list unneeded removals or ask to hide required data or columns in toggles.
3. Add an optional `--plan <plan file>` flag to `hard-eng.py look` (documented in `ux.md`, `checks.md`, `e2e/SKILL.md`, and `review.md`) that validates the path is a committed, unmodified (respecting `core.autocrlf`), non-symlink repository plan (`PLAN.md` or `features/.../PLAN.md`), extracts only its `## Outcome + scope` section through Hard Eng's single-source `plans.plan_sections` parser (refusing malformed plans and disguised nested `##` heading lines so builder verdicts in `## ux_reference` can never leak), bounds it to 4,000 UTF-8 bytes, passes it fenced as data-only `Screen scope`, records `plan` and committed blob `plan_sha256` in the local look record, and verifies in `.hooks/ui_proof.py` during `ship` that any scoped look record matches a committed plan changed by the PR.

Non-goals: altering `Look review:` PR block format, reading builder `Pass` lines into `look`, adding extra reviewer turns, or capturing duplicate un-ringed images.

## Sources + coverage

Sources: `sgaabdu4/hard-eng#693` and the user's direct instruction in chat on 2026-11-22, read in full.
Reviewer: N/A — one small bug report (`sgaabdu4/hard-eng#693`) with two explicit defects.
Deliverables: None

- Issue #693 bug 1, ignore Hard Eng `--ring` red review outlines in `look.py`: In scope — ignore `3px solid red` `--ring` review outlines
- Issue #693 bug 2, allow `0 removed` Pass for `No clutter`: In scope — treat `0 removed` as a valid `Pass` when every visible element serves the user's task
- Issue #693 bug 2, support `--plan` scope in `look`: In scope — `look --plan <plan file>` passes only `## Outcome + scope`
- User instruction, release Hard Eng `main`: Later — user, chat instruction on 2026-11-22 (separate `develop` to `main` release PR immediately after this PR merges to `develop`)

## Repository context

Owners:
- `.hooks/ui_measure.py` and `.hooks/browser.py` own `.hard-eng/browser/*.json` capture records including recorded `--ring` selectors.
- `.hooks/look.py` owns the `look` CLI, `PROMPT`, `RING_NOTE`, `has_confirmed_ring`, `extract_outcome_scope`, `plan_scope`, `prompt_for`, and look records.
- `.hooks/ui_proof.py` owns `browser_records`, `look_record_problem`, `ui_evidence`, and committed plan-digest verification during `ship`.
- `.hooks/plans.py` owns `is_plan_path`, `plan_sections`, and `usability_lines` (reused directly by `.hooks/look.py`).
- `.agents/skills/he-plan/references/ux.md` owns the `No clutter` usability rule text and `Look review` guidance.
- `.agents/skills/he-ship/references/checks.md`, `.agents/skills/e2e/SKILL.md`, and `.agents/skills/code-review/references/review.md` document the `hard-eng.py look` command invocation.

Same cause: `look` evaluated ringed PR After captures with no notice that `--ring` outlines are review annotations, while `No clutter (count: kept, removed)` gave no `0 removed` Pass guidance and no way to pass committed `Outcome + scope`. Searched `.hooks/` and `.agents/skills/` for every `look`, `write_record`, and `No clutter` owner; updated `.hooks/ui_measure.py`, `.hooks/browser.py`, `.hooks/look.py`, `.hooks/ui_proof.py`, `ux.md`, `checks.md`, `e2e/SKILL.md`, and `review.md` together.
Single source: `ux.md` owns `No clutter` (read via `plans.usability_lines()`), `plans.py` owns `is_plan_path` and `plan_sections`, `ui_measure.py` owns capture record writing, `ui_proof.py` owns `browser_records` and ship-time plan binding, and `look.py` owns `PROMPT`, `RING_NOTE`, `SCOPE_SECTION`, `extract_outcome_scope`, and `plan_scope`.

## Decisions + authorization

Blockers: None
Handoff: None
Authority: User directly instructed fixing `sgaabdu4/hard-eng#693` and releasing `main` in chat on 2026-11-22.
Review declined: Live Claude CLI run for `look` :: Local Claude CLI authentication on this machine is expired (`Failed to authenticate: this login reached its time limit`), so live verification used Codex CLI (`--host agy`); Claude CLI invocation and stream parsing are untouched and covered by `tests/test_look.py`.
Review declined: CommonMark code fences or HTML comments containing literal `##` headings inside `## Outcome + scope` :: `.hooks/` has no third-party CommonMark parser dependency, and Hard Eng's own plan validator (`.hooks/plans.py:plan_sections`) already defines section boundaries with `^## +` without CommonMark block parsing; reusing `plans.plan_sections` as the single source and refusing nested `#` or `##` heading lines inside `Outcome + scope` eliminates all verdict-leak paths in 10 lines instead of maintaining a bespoke CommonMark parser, and plans passed to `look --plan` use `###` subheadings or inline backticks inside `Outcome + scope`.

## Acceptance + steps

- [x] `look` prompt tells the reviewer to ignore `3px solid red` `--ring` review outlines only for confirmed `--ring` captures in `.hard-eng/browser` (leaving unannotated captures unchecked by any red-outline exemption) and to treat `0 removed` as a valid `Pass` when every visible element serves the user's task, and `ux.md` states the same `0 removed` rule without leaking forbidden prompt tokens → `tests/test_look.py::test_look_prompt_ignores_ring_outlines_only_for_confirmed_ring_captures` and `tests/test_look.py::test_look_prompt_holds_only_images_and_rules`.
- [x] `look --plan <plan file>` passes only `## Outcome + scope` from the committed `HEAD` plan via `plans.plan_sections` (honouring `core.autocrlf`, refusing malformed plans and nested `##` headings inside scope, bounded to 4,000 UTF-8 bytes) fenced as data-only `Screen scope`, never leaks `## ux_reference` or builder verdicts, records `plan` and `plan_sha256`, verifies matching committed PR-changed plan binding in `ui_proof.ship_problem`, and appears in `look --help` → `tests/test_look.py::test_look_plan_option_passes_only_committed_outcome_and_scope_as_data`, `tests/test_look.py::test_ship_and_autocrlf_verify_committed_pr_plan_scope`, and `tests/test_look.py::test_the_look_command_is_listed_in_the_runner_help`.
- [x] `look --plan` refuses non-plan files, out-of-repo paths, symlinks, untracked/uncommitted/missing files, and plans lacking a filled `## Outcome + scope` section → `tests/test_look.py::test_look_plan_option_refuses_invalid_missing_symlink_and_empty_plans`.
- [x] Skill and reference links and size limits pass after updating `ux.md`, `checks.md`, `e2e/SKILL.md`, and `review.md` → `tests/test_skill_links.py::test_distributed_skill_links_resolve` and `tests/test_skill_links.py::test_distributed_skills_fit_the_codex_skill_limit`.

## Baseline + execution

Result: Passed
Evidence: Clean worktree created from `origin/develop` (`60096580`); added 4 failing reproduction tests in `tests/test_look.py` first (`uv run pytest tests/test_look.py -q` exited 1 with 4 failures before the fix, proving the escaped base-branch defect).
Execution: Updated `.hooks/look.py`, `ux.md`, `checks.md`, `e2e/SKILL.md`, `review.md`, and `tests/test_look.py`; verified with focused tests, Writing Great Skills prose reader, live Codex `look` run on a two-ring 6-column KPI capture, full `check --plan-stage Complete`, and `challenge`.

## Risks + recovery

Prompt text could weaken genuine visual checks if overly broad; mitigated by scoping the ring exception strictly to exact confirmed `ring_boxes` pixel rectangles from `.hard-eng/browser` and fencing `Screen scope` explicitly as data-only that never overrides visual quality rules. Known limit: `look --plan` reuses Hard Eng's `plans.plan_sections` parser and rejects nested `#` or `##` heading lines inside `Outcome + scope` rather than implementing a bespoke CommonMark block parser (use `###` subheadings or inline backticks inside `Outcome + scope`). Recovery: revert the commits on `develop`.

## ux_reference

N/A — Hard Eng is a CLI and hook toolkit with no visual application UI.

## Verification

Result: Passed
Evidence: Added 4 failing reproduction tests in `tests/test_look.py` on `origin/develop` (`60096580`, 4 failed before the fix), then verified with `uv run pytest tests/test_look.py tests/test_skill_links.py` (29 passed), an independent Writing Great Skills prose reader check (all three quoted sentences tightened across `ux.md` and `checks.md`), `ruff`, `pyrefly`, `hot-paths`, live `browser capture --ring` + `look --plan` runs, full `python3 .hooks/hard-eng.py check --base origin/develop --plan-stage Complete` (7,538 passed, 93.23% line coverage, 0 findings), and independent `challenge`.
E2E: N/A — Hard Eng CLI/hook fix is verified by subprocess/fixture tests and live `browser capture --ring` + `look --plan` runs.
Real service: Passed — ran real `browser capture --ring '#summary-panel' --ring '#kpi-panel'` + `look --host agy --plan features/kpi-board/PLAN.md` (live Codex CLI) on a 6-column KPI dashboard with two bright 3px solid red review outlines; observed `OUTCOME: clean` (`LOOK_RC: 0`) with `Hierarchy: Pass` (ignoring the two red `--ring` boxes) and `No clutter: Pass — 31 kept, 0 removed`, while a deliberately misaligned layout variant still returned `OUTCOME: findings` (proving genuine visual checks remain intact). Local Claude CLI auth is expired on this host (see `Review declined:`).
Retro: Escaped base-branch bug (`sgaabdu4/hard-eng#693`): `tests/test_look.py` checked only prompt exclusions and never verified `--ring` annotation handling, `0 removed` guidance, or committed `--plan` scope isolation and ship verification → `tests/test_look.py::test_look_prompt_ignores_ring_outlines_only_for_confirmed_ring_captures`, `tests/test_look.py::test_look_plan_option_passes_only_committed_outcome_and_scope_as_data`, and `tests/test_look.py::test_look_plan_option_refuses_invalid_missing_symlink_and_empty_plans`.

Delivery target: Merge
Delivery: Pending — full check, challenge, PR to `develop`, CI, merge, and `develop` to `main` release.
