# Class Fallow 3.46 inlineThresholdOverrides and refuse inline threshold override comments

Status: Complete

## Outcome + scope

Classify Fallow 3.46's new `health.inlineThresholdOverrides` setting as `free` in `.hooks/fallow_table.py` so projects can leave it at its default (`true`) or turn inline overrides off (`false`), and refuse Fallow inline threshold-override comments in both `.hooks/comments.py` (`SCRIPT_OFF`) and `.hooks/fallow_report.py` (`validate_complexity`). Non-goals: changing Fallow's health ceilings or other settings tables.

## Sources + coverage

Sources: N/A — Fallow v3.46.0 tool release note only; no external project specification.

## Repository context

Owners: `.hooks/fallow_table.py` (`FALLOW_KEYS`), `.hooks/comments.py` (`SCRIPT_OFF`), `.hooks/fallow_report.py` (`validate_complexity`), `tests/test_settings_tables.py`, `tests/switch_off_forms.py`, and `tests/test_strict_refusals.py`.
Same cause: Fallow 3.46.0 introduced per-function inline threshold-override comments controlled by `health.inlineThresholdOverrides` (default `true`) and reported under `inline_threshold_overrides`; without classifying the key and blocking the comment form, `test_every_setting_that_fallow_prints_has_a_class` failed and projects could raise health limits inline under `HE-NO-SWITCH-OFF`.
Single source: `.hooks/fallow_table.py` owns Fallow setting classes, `.hooks/comments.py` owns inline suppression patterns, and `.hooks/fallow_report.py` owns Fallow JSON health report checks.

## Decisions + authorization

Blockers: None.
Handoff: Approval
Authority: Autonomous maintenance — authorized to keep CI green and enforce `HE-NO-SWITCH-OFF` for new tool settings.

## Acceptance + steps

- [x] `health.inlineThresholdOverrides` is classed in `.hooks/fallow_table.py` and allows turning inline threshold overrides off (`false`) → `tests/test_settings_tables.py::test_every_setting_that_fallow_prints_has_a_class` and `tests/test_settings_tables.py::test_fallow_3_46_inline_threshold_overrides_has_a_class_and_report_rejects_it`.
- [x] Inline threshold-override comments and non-empty `inline_threshold_overrides` health reports are refused under `HE-NO-SWITCH-OFF` → `tests/test_strict_refusals.py::test_old_switch_offs_anywhere_in_the_project_fail` and `tests/test_settings_tables.py::test_fallow_3_46_inline_threshold_overrides_has_a_class_and_report_rejects_it`.

## Baseline + execution

Result: Passed
Evidence: On `origin/develop` (`a2410e8b`), `test_every_setting_that_fallow_prints_has_a_class` failed with `AssertionError: class these settings: ['health.inlineThresholdOverrides']` against Fallow 3.46.0.
Execution: Single builder in a linked worktree off `origin/develop`.

## Risks + recovery

A future Fallow release could rename `inline_threshold_overrides` in JSON output; the diff-level check in `.hooks/comments.py` still catches the comment syntax independently. Recovery: revert the commit.

## ux_reference

N/A — Python hook tables, comment regex, and report validation only; no visible UI.

## Verification

Result: Passed
Evidence: `uv run pytest tests/test_settings_tables.py tests/test_strict_refusals.py -q` and `python3 .hooks/hard-eng.py check --quick --base origin/develop --plan-stage Complete` passed.
Review declined: string literals mentioning inline threshold overrides in `.js`, `.jsx`, and `.tsx` files :: `.hooks/source_scan.py` intentionally lists `.js`, `.jsx`, `.tsx`, and `.swift` in `UNMASKED` for every `SCRIPT_OFF` directive (`eslint-disable`, `@ts-ignore`, `biome-ignore`) because the lightweight scanner does not parse JSX text; adding a JSX parser is out of scope for classifying Fallow 3.46's setting.
Review declined: JSDoc prose containing a backticked `//` example of an inline threshold override inside a block comment :: `SCRIPT_OFF` is a single-line regex (identical to `eslint-disable` and `biome-ignore` handling); parsing markdown/backticks inside JSDoc comments is out of scope.
E2E: N/A — hook unit tests cover the config table, diff scan, and JSON report check.
Real service: N/A — runs local `bunx fallow@latest config` and unit fixtures only.
Retro: When a scanner adds an inline threshold-raising comment alongside a config toggle, classify the config key and refuse both the inline comment syntax and its report array together.

Delivery target: Merge
Delivery path: PR into develop.
Delivery: Pending — PR checks green and merged into develop.
